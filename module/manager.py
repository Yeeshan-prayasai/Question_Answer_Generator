import os
import time
import asyncio
import pypdf
import uuid
from google import genai
from typing import List, Optional, Any

try:
    from .planner import PlannerAgent
    from .generator import GeneratorAgent
    from .translator import TranslatorAgent
    from .archivist import ArchivistAgent
    from .researcher import ResearcherAgent
    from .models import Question, TestPaper
    from .utils import calculate_total_usage
except ImportError:
    from planner import PlannerAgent
    from generator import GeneratorAgent
    from translator import TranslatorAgent
    from archivist import ArchivistAgent
    from researcher import ResearcherAgent
    from models import Question, TestPaper
    from utils import calculate_total_usage

class QuestionManager:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API Key is required")

        os.environ['GEMINI_API_KEY'] = api_key

        try:
            self.client = genai.Client()
            # We delay async client creation to execution time to avoid loop binding issues
        except Exception as e:
            print(f"Error initializing Gemini Client: {e}")
            raise e

        self.planner = PlannerAgent(self.client)
        self.researcher = ResearcherAgent(self.client)
        # Agents initialized with placeholders or sync client if compatible
        # But Generator and Translator use async client.
        # We will update their client reference at runtime.
        self.generator = GeneratorAgent(None)
        self.translator = TranslatorAgent(None)
        self.archivist = ArchivistAgent()

        self.global_token_usage = []

    async def _per_question_execution(self, plan_tuple):
        """
        Executes generation and translation for a single question plan.
        plan_tuple is (index, plan_string, subject, start_number)
        """
        try:
            index, plan_text, subject, start_number = plan_tuple
            # The sequential number is start_number + index
            q_num = start_number + index

            subject = plan_text.split('Subject:')[-1].strip().split('\n')[0] if 'Subject:' in plan_text else subject

            print(f'Running Iteration for Q{q_num}')

            que = await self.generator.generate_question(plan_text, self.global_token_usage)

            # Strip reference material from blueprint before storing (saves DB space)
            clean_blueprint = plan_text.split('\n\n--- REFERENCE MATERIAL')[0] if '--- REFERENCE MATERIAL' in plan_text else plan_text

            que_hindi = None
            if que:
                try:
                    que_hindi = await self.translator.translate_question(que.question, que.options, self.global_token_usage)
                except Exception as e:
                    print(f"⚠️ Translation failed for Q{q_num}: {str(e)}")
                    # Continue without Hindi translation
                    pass

            out = None
            if que and que_hindi:
                out = Question(
                    id=q_num, # Display ID
                    db_uuid=str(uuid.uuid4()), # Assign unique ID immediately
                    question_number=q_num, # Sequential number
                    question_english=que.question,
                    options_english=que.options,
                    question_hindi=que_hindi.question,
                    options_hindi=que_hindi.options,
                    answer=que.answer,
                    question_blueprint=clean_blueprint,
                    subject=subject,
                    topic=None,  # Will be set during review/tagging
                    subtopic=None,  # Will be set during review/tagging
                    month=None,  # Will be set during review
                    year=None,  # Will be set during review
                    test_type=None,  # Will be set during review
                    prone_to_silly_mistakes=None,  # Will be set during review
                    pattern=None,  # Will be set during review
                    content_type=None,  # Will be set during review
                    is_selected=False # Default to False
                )
            return out
        except Exception as e:
            print(f"⚠️ Error generating question at index {plan_tuple[0] if plan_tuple else 'unknown'}: {str(e)}")
            return None

    async def _collate_questions(self, plans: List[str], subject: str = "General", start_number: int = 1) -> TestPaper:
        try:
            print('Request initiated for num of plans:', len(plans))
            # Pass start_number logic to tasks
            modified_plans = [(ind, p, subject, start_number) for ind, p in enumerate(plans)]
            final_data = []
            chunk_jump = 15

            for chunk in range(0, len(modified_plans), chunk_jump):
                try:
                    # Create a list of async tasks (coroutines)
                    tasks = [self._per_question_execution(plan)
                                for plan in modified_plans[chunk:chunk+chunk_jump]]
                    print('tasks--- ', len(tasks))
                    all_data = await asyncio.gather(*tasks, return_exceptions=True)

                    # Filter out exceptions and log them
                    for i, result in enumerate(all_data):
                        if isinstance(result, Exception):
                            print(f"⚠️ Task {chunk + i} failed: {str(result)}")
                        else:
                            final_data.append(result)
                except Exception as e:
                    print(f"⚠️ Error processing chunk {chunk}: {str(e)}")
                    # Continue with next chunk
                    continue

            # Filter out None results
            final_data = [i for i in final_data if i]

            # Sort by question number just in case
            final_data.sort(key=lambda x: x.question_number)

            print('Request completed for num of question:', len(final_data))

            response = TestPaper(questions=final_data)
        except Exception as e:
            print(f"⚠️ Error in _collate_questions: {str(e)}")
            response = TestPaper(questions=[])
        
        return response

    async def generate_questions(self,
                               source_text: Optional[str],
                               uploaded_pdf: Any,
                               topic_input: Optional[str],
                               question_distribution: List[dict],
                               start_question_number: int = 1):

        start = time.perf_counter()
        num_questions = sum(item['count'] for item in question_distribution)
        print('Request coming for number of question: ', num_questions)

        # Initialize Async Client for this run
        try:
            # Create a fresh async client that will use the current running loop
            async_client = genai.Client().aio
            self.generator.client = async_client
            self.translator.client = async_client
        except Exception as e:
            print(f"Error creating async client: {e}")
            raise e

        # Process Context
        context = ""
        if uploaded_pdf is not None:
            # Check if uploaded_pdf is file-like or path
            if isinstance(uploaded_pdf, str):
                 try:
                     reader = pypdf.PdfReader(uploaded_pdf)
                     for page in reader.pages:
                        context += page.extract_text() + "\n"
                 except Exception as e:
                     print(f"Error reading PDF path: {e}")
            elif hasattr(uploaded_pdf, 'read'):
                 try:
                     reader = pypdf.PdfReader(uploaded_pdf)
                     for page in reader.pages:
                        context += page.extract_text() + "\n"
                 except Exception as e:
                     print(f"Error reading PDF stream: {e}")
        
        if source_text:
            context += source_text + "\n"

        # Auto Web Research (if topic/context needs recent information)
        research_sources = []
        research_context_text = ""
        has_topic = topic_input and topic_input.strip()
        has_context = context.strip()
        if has_topic or has_context:
            try:
                classify_topic = topic_input if has_topic else ""
                classify_context = context if has_context else ""
                if self.researcher.needs_web_search(classify_topic, classify_context, self.global_token_usage):
                    print("ResearcherAgent: Topic/context needs web research, searching...")
                    # Use topic if available, otherwise derive search query from context
                    search_topic = topic_input if has_topic else context[:300]
                    research_result = self.researcher.research_topic(
                        topic=search_topic,
                        context_hint=context[:500] if has_context and has_topic else "",
                        global_token_usage=self.global_token_usage
                    )
                    if research_result['context']:
                        research_context_text = research_result['context']
                        context += "\n\n=== SUPPLEMENTARY WEB RESEARCH ===\n"
                        context += research_context_text
                        context += "\n=== END WEB RESEARCH ===\n"
                        research_sources = research_result['sources']
                        print(f"ResearcherAgent: Found {len(research_sources)} sources")
                    else:
                        print("ResearcherAgent: No results found, proceeding without web context")
                else:
                    print("ResearcherAgent: Topic/context does not need web research")
            except Exception as e:
                print(f"ResearcherAgent: Web research failed, continuing without: {e}")

        # Planner Step
        print(f"[Manager] Context for planner: {len(context)} chars")

        plans_response = None

        if context.strip():
            if topic_input:

                plans_response = self.planner.plan_with_context_and_topic(
                    context=context,
                    topic=topic_input,
                    question_distribution=question_distribution,
                    global_token_usage=self.global_token_usage
                )
            else:

                plans_response = self.planner.plan_with_context(
                    context=context,
                    question_distribution=question_distribution,
                    global_token_usage=self.global_token_usage
                )
        elif topic_input:
            plans_response = self.planner.plan_with_topic(
                topic=topic_input,
                question_distribution=question_distribution,
                global_token_usage=self.global_token_usage
            )
        else:
            plans_response = self.planner.plan_general(
                question_distribution=question_distribution,
                global_token_usage=self.global_token_usage
            )

        if not plans_response or not plans_response.questions:
            print("Planning failed or returned no questions.")
            return TestPaper(questions=[]), calculate_total_usage(self.global_token_usage), research_sources

        # Attach web research context to each blueprint so the generator has the facts
        if research_sources and research_context_text:
            enriched_plans = []
            for plan in plans_response.questions:
                enriched_plan = (
                    f"{plan}\n\n"
                    f"--- REFERENCE MATERIAL (from web research, use these facts) ---\n"
                    f"{research_context_text}\n"
                    f"--- END REFERENCE MATERIAL ---"
                )
                enriched_plans.append(enriched_plan)
            plans_response.questions = enriched_plans
            print(f"[Manager] Attached web research context to {len(enriched_plans)} blueprints")

        # Determine subject
        current_subject = "General"
        if topic_input:
            current_subject = topic_input
        elif uploaded_pdf or source_text:
             current_subject = "Custom Content"
             
        questions_result = await self._collate_questions(
            plans_response.questions, 
            subject=current_subject,
            start_number=start_question_number
        )
        
        token_usage = calculate_total_usage(self.global_token_usage)

        end = time.perf_counter()
        elapsed = end - start
        print(f"Overall Time: {elapsed:.1f} seconds.")

        return questions_result, token_usage, research_sources

    async def regenerate_question(self, blueprint: str) -> Optional[Question]:
        """Regenerates a single question based on blueprint."""
        try:
            async_client = genai.Client().aio
            self.generator.client = async_client
            self.translator.client = async_client

            que = await self.generator.generate_question(blueprint, self.global_token_usage)
            if que:
                que_hindi = await self.translator.translate_question(que.question, que.options, self.global_token_usage)
                if que_hindi:
                    # Return partial Question object (caller handles ID etc)
                    return Question(
                        id=0, question_number=0, # Placeholder
                        question_english=que.question,
                        options_english=que.options,
                        question_hindi=que_hindi.question,
                        options_hindi=que_hindi.options,
                        answer=que.answer,
                        question_blueprint=blueprint,
                        is_selected=False
                    )
            return None
        except Exception as e:
            print(f"Regenerate error: {e}")
            return None

    async def translate_single_question(self, text: str, options: List[str]):
        try:
            async_client = genai.Client().aio
            self.translator.client = async_client
            return await self.translator.translate_question(text, options, self.global_token_usage)
        except Exception as e:
            print(f"Translate error: {e}")
            return None
