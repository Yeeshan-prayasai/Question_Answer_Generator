import os
import io
import time
import asyncio
import pypdf
import uuid
from google import genai
from google.genai import types as gtypes
from typing import List, Optional, Any, Tuple

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

    def extract_pdf_context(self, pdf_bytes: bytes, filename: str = "document.pdf",
                            page_range: Optional[Tuple[int, int]] = None) -> str:
        """
        Upload PDF to Gemini File API and extract structured content for UPSC question generation.
        Falls back to pypdf on error. Returns extracted text.
        """
        try:
            print(f"[PDFExtractor] Uploading PDF to Gemini File API ({len(pdf_bytes)//1024}KB)...")
            uploaded_file = self.client.files.upload(
                file=io.BytesIO(pdf_bytes),
                config={"mime_type": "application/pdf", "display_name": filename},
            )
            print(f"[PDFExtractor] Uploaded: {uploaded_file.uri}")

            page_instruction = ""
            if page_range:
                start_pg, end_pg = page_range
                page_instruction = f"\n\nFocus ONLY on pages {start_pg} to {end_pg} of the document."

            prompt = (
                f"You are extracting content from this document for UPSC Prelims question generation.{page_instruction}\n\n"
                f"STRICTLY IGNORE the following — do NOT include them in output:\n"
                f"- Any URLs, website links, domain names (upscpdf.com, telegram.me, t.me, pdfnotesco, etc.)\n"
                f"- Watermarks, repeated headers/footers, page numbers, download links\n"
                f"- Any overlay text that repeats across pages (these are watermarks)\n\n"
                f"Extract ONLY the actual educational/factual content. Include:\n"
                f"- Key facts, statistics, data points, dates, numbers\n"
                f"- Government schemes, policies, laws, acts, articles\n"
                f"- International agreements, summits, organizations\n"
                f"- Important events, appointments, awards\n"
                f"- Scientific discoveries, technologies\n"
                f"- Historical facts, geographical data, constitutional provisions\n\n"
                f"Format: Organize by topic/section with clear headings. Use bullet points. "
                f"Be comprehensive and preserve all numerical data exactly. "
                f"If a page contains only watermarks/URLs and no real content, skip it silently."
            )

            resp = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    gtypes.Part.from_uri(file_uri=uploaded_file.uri, mime_type="application/pdf"),
                    gtypes.Part.from_text(text=prompt),
                ],
                config=gtypes.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=32000,
                ),
            )

            extracted = resp.text.strip() if resp.text else ""
            print(f"[PDFExtractor] Extracted {len(extracted)} chars from PDF")

            if hasattr(resp, "usage_metadata"):
                self.global_token_usage.append(resp.usage_metadata)

            # Clean up uploaded file
            try:
                self.client.files.delete(name=uploaded_file.name)
            except Exception:
                pass

            return extracted

        except Exception as e:
            print(f"[PDFExtractor] Gemini extraction failed: {e}, falling back to pypdf")
            try:
                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                pages = reader.pages
                if page_range:
                    start_pg, end_pg = page_range
                    pages = reader.pages[max(0, start_pg - 1):end_pg]
                return "\n".join(p.extract_text() or "" for p in pages)
            except Exception as e2:
                print(f"[PDFExtractor] pypdf fallback also failed: {e2}")
                return ""

    def _add_section_markers(self, text: str, num_sections: int) -> str:
        """Split extracted text into N labelled sections so the planner distributes questions evenly."""
        if num_sections <= 1 or not text.strip():
            return text
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) < num_sections:
            return text  # Not enough content to split meaningfully
        chunk_size = max(1, len(paragraphs) // num_sections)
        sections = []
        for i in range(num_sections):
            start = i * chunk_size
            end = start + chunk_size if i < num_sections - 1 else len(paragraphs)
            chunk = '\n\n'.join(paragraphs[start:end])
            sections.append(f"=== SECTION {i+1} of {num_sections} ===\n{chunk}")
        return '\n\n'.join(sections)

    def get_pdf_page_count(self, pdf_bytes: bytes) -> int:
        """Returns page count of a PDF using pypdf (lightweight, no API call)."""
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            return len(reader.pages)
        except Exception:
            return 0

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
            topic = plan_text.split('Topic:')[-1].strip().split('\n')[0] if 'Topic:' in plan_text else None
            subtopic = plan_text.split('Subtopic:')[-1].strip().split('\n')[0] if 'Subtopic:' in plan_text else None
            pattern = plan_text.split('Format:')[-1].strip().split('\n')[0] if 'Format:' in plan_text else None

            print(f'Running Iteration for Q{q_num}')

            que = await self.generator.generate_question(plan_text, self.global_token_usage)

            # Strip reference material from blueprint before storing (saves DB space)
            clean_blueprint = plan_text.split('\n\n--- REFERENCE MATERIAL')[0] if '--- REFERENCE MATERIAL' in plan_text else plan_text

            # Extract difficulty from blueprint and map to 1-5 scale
            difficulty = None
            source_passage = None
            difficulty_map = {'Easy': 2.0, 'Moderate': 3.0, 'Difficult': 4.0}
            in_passage = False
            passage_lines = []
            for line in clean_blueprint.split('\n'):
                stripped = line.strip()
                if stripped.startswith('Difficulty:'):
                    raw_difficulty = stripped.replace('Difficulty:', '').strip()
                    difficulty = difficulty_map.get(raw_difficulty, 3.0)
                if stripped.startswith('Source Passage:'):
                    passage_val = stripped.replace('Source Passage:', '').strip()
                    if passage_val and passage_val not in ('[copy the exact', 'N/A', ''):
                        passage_lines = [passage_val]
                    in_passage = True
                elif in_passage:
                    # Multi-line passage: continue until next key: field
                    if ':' in stripped and stripped.split(':')[0].replace(' ', '').isalpha() and len(stripped.split(':')[0]) < 25:
                        in_passage = False
                    else:
                        if stripped:
                            passage_lines.append(stripped)
            if passage_lines:
                source_passage = ' '.join(passage_lines).strip()

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
                    explanation=que.explanation if hasattr(que, 'explanation') else None,
                    question_blueprint=clean_blueprint,
                    subject=subject,
                    topic=topic,
                    subtopic=subtopic,
                    difficulty=difficulty,
                    source_passage=source_passage,
                    month=None,
                    year=None,
                    test_type=None,
                    prone_to_silly_mistakes=None,
                    pattern=pattern,
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
                               start_question_number: int = 1,
                               pdf_extracted_context: Optional[str] = None,
                               pdf_source: Optional[str] = None):

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

        # Build context — prefer pre-extracted PDF context over raw PDF bytes
        context = ""
        if pdf_extracted_context:
            context += pdf_extracted_context + "\n"
        elif uploaded_pdf is not None:
            # Fallback: use Gemini extraction or pypdf on the raw file object
            pdf_bytes = None
            if isinstance(uploaded_pdf, (str, os.PathLike)):
                try:
                    with open(uploaded_pdf, "rb") as f:
                        pdf_bytes = f.read()
                except Exception as e:
                    print(f"Error reading PDF path: {e}")
            elif hasattr(uploaded_pdf, "read"):
                try:
                    uploaded_pdf.seek(0)
                    pdf_bytes = uploaded_pdf.read()
                except Exception as e:
                    print(f"Error reading PDF stream: {e}")

            if pdf_bytes:
                fname = getattr(uploaded_pdf, "name", "document.pdf")
                context += self.extract_pdf_context(pdf_bytes, filename=fname) + "\n"

        if source_text:
            context += source_text + "\n"

        # Auto Web Research (if topic/context needs recent information)
        research_sources = []
        research_context_text = ""
        has_topic = topic_input and topic_input.strip()
        has_context = context.strip()
        if has_topic or has_context:
            try:
                # For PDF content, use the pdf_source (filename) as an additional topic hint
                # so the researcher can correctly identify current-affairs sections
                classify_topic = topic_input if has_topic else (pdf_source or "")
                classify_context = context[:800] if has_context else ""
                if self.researcher.needs_web_search(classify_topic, classify_context, self.global_token_usage):
                    print("ResearcherAgent: Topic/context needs web research, searching...")
                    # Use topic if available; for PDF-only, derive search query from first 300 chars of extracted content
                    search_topic = topic_input if has_topic else (pdf_source or context[:300])
                    research_result = self.researcher.research_topic(
                        topic=search_topic,
                        context_hint=context[:500] if has_context and (has_topic or pdf_source) else "",
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

        # Split context into sections so the planner draws questions from across the document
        total_questions = sum(item.get('count', 1) for item in question_distribution)
        if context.strip() and total_questions > 1:
            context = self._add_section_markers(context, total_questions)
            print(f"[Manager] Context split into {total_questions} sections for even distribution")

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

        # Stamp PDF source on every generated question
        if pdf_source and questions_result.questions:
            for q in questions_result.questions:
                q.pdf_source = pdf_source

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
