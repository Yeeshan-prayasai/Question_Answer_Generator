from google.genai import types
import time
try:
    from .models import QuestionPlan
    from .utils import load_prompt_file
except (ImportError, KeyError):
    from models import QuestionPlan
    from utils import load_prompt_file

class PlannerAgent:
    def __init__(self, client):
        self.client = client
        self.model = "gemini-3-pro-preview"

        # Load static prompt content
        self.planner_guidelines = load_prompt_file('planner_guidelines.txt')
        # Deferred import to avoid circular dependency (archivist → manager → planner → archivist)
        try:
            from .archivist import ArchivistAgent
        except (ImportError, KeyError):
            from archivist import ArchivistAgent
        self.archivist = ArchivistAgent()
        self.past_blueprints = self.archivist.get_all_questions()
        # Load taxonomy names so the planner uses exact DB names
        tax = self.archivist.get_taxonomy_names(env='dev')
        self.taxonomy_topics = tax.get(2, [])
        self.taxonomy_subtopics = tax.get(3, [])

    def _taxonomy_reference(self) -> str:
        """Return a formatted taxonomy reference block for injection into system prompts."""
        if not self.taxonomy_topics and not self.taxonomy_subtopics:
            return ""
        lines = [
            "---",
            "## Taxonomy Reference [HARD RESTRICTION]",
            "When writing Topic and Subtopic fields in each blueprint, you MUST use ONLY the exact names listed below.",
            "Do NOT invent new names. Pick the closest match from the list.",
            "",
        ]
        if self.taxonomy_topics:
            lines.append("**Available Topics (use exactly):**")
            lines.append(", ".join(self.taxonomy_topics))
            lines.append("")
        if self.taxonomy_subtopics:
            lines.append("**Available Subtopics (use exactly):**")
            lines.append(", ".join(self.taxonomy_subtopics))
            lines.append("")
        return "\n".join(lines)

    def _generate_content(self, user_prompt, system_prompt, global_token_usage):
        fallback_models = ["gemini-2.5-pro", "gemini-2.5-flash"]
        models_to_try = [self.model] + [m for m in fallback_models if m != self.model]
        for model in models_to_try:
            try:
                resp = self.client.models.generate_content(
                    model=model,
                    contents=[user_prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=65000,
                        response_mime_type="application/json",
                        response_schema=QuestionPlan,
                        system_instruction=system_prompt,
                    ),
                )
                if hasattr(resp, 'usage_metadata'):
                    global_token_usage.append(resp.usage_metadata)
                if model != self.model:
                    print(f"[PlannerAgent] Used fallback model: {model}")
                return resp.parsed
            except Exception as e:
                print(f"Error in PlannerAgent ({model}): {e}")
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    print(f"[PlannerAgent] {model} unavailable, trying next...")
                    time.sleep(2)
                    continue
                return None
        print("[PlannerAgent] All models failed.")
        return None

    def _format_requirements(self, distribution):
        req_str = "### Detailed Question Requirements Table:\n"
        req_str += "**CRITICAL: Every question MUST be directly relevant to the specified topic. Questions that deviate from the topic will be rejected.**\n\n"
        total_q = 0
        for i, item in enumerate(distribution):
            count = item['count']
            total_q += count
            topic_str = f"Topic: {item['topic']}" if item['topic'] else "Topic: Use Main Topic/Context"
            req_str += f"{i+1}. Generate **{count} questions** with attributes: [{topic_str}, Pattern: {item['pattern']}, Cognitive: {item['cognitive']}, Difficulty: {item['difficulty']}]\n"
            req_str += f"   → RELEVANCE REQUIREMENT: Question MUST include keywords/concepts directly related to: {item['topic'] if item['topic'] else 'Main Topic'}\n"

        req_str += f"\n**Total Questions to Generate: {total_q}**"
        req_str += f"\n**VALIDATION: Before finalizing each blueprint, verify it contains topic-specific terms and concepts.**"
        return req_str, total_q

    def plan_with_context_and_topic(self, context, topic, question_distribution, global_token_usage):
        
        requirements_text, num_questions = self._format_requirements(question_distribution)

        system_prompt = f'''
You are an **expert UPSC (Union Public Service Commission) Prelims Question Paper Designer**, specializing in designing **high-quality, authentic Multiple Choice Question (MCQ) blueprints** that perfectly reflect the **standard, depth, style, ambiguity, pattern and conceptual rigor** of the actual Civil Services Examination (Preliminary).

---

## Your Expertise

You have deep expertise in:
- The complete detailed **UPSC Prelims GS Paper I syllabus** in depth.
- The detailed distribution of questions across subjects in UPSC Prelims GS Paper I.
- The detailed distribution of question patterns/formats in UPSC Prelims GS Paper I.
- The detailed distribution of question difficulty levels in UPSC Prelims GS Paper I.
- The detailed distribution of cognitive types in UPSC Prelims GS Paper I.
- Your understanding is based on understanding of **tone, structure, and conceptual layering** of UPSC PYQs (Previous Year Questions) from the last 10 years.  

---

## Input Specification

You will receive:
  
1. **`Context`** → A specific report, document, event, or news item.
2. **`Topic`** → It can be a subject name or topic in a subject or subtopic etc.
3. **`Detailed Requirements Table`** → A specific table defining the attributes (Pattern, Difficulty, Cognitive Level, Topic override) for each set of questions to generate.


---

## Core Task

Your task is to create the **EXACT** requested number of **UPSC-style question blueprints**, strictly following these rules:

- **STRICT ADHERENCE TO QUANTITY**: You MUST generate precisely the number of questions specified for each row in the `Detailed Requirements Table`. This is a non-negotiable constraint.
- Each item in the output array is a **question plan**, not the question text.  
- Each plan must include concise details such as:
  - Subject
  - Topic → Subtopic → Sub-subtopic   
  - Difficulty  
  - Cognitive Complexity
  - Question Format
---

### Content Rules

1. Content Selection
   - You need to FOCUS on USER PROVIDED TOPIC while analyzing CONTEXT.
   - You need to Identify underlying conceptual topics/subtopics from the CONTEXT but ONLY from the LENS of USER PROVIDED TOPIC.
   - You need to Ensure every question connects directly to that CONTEXT (conceptually or factually) but ONLY from the LENS of USER PROVIDED TOPIC.
   - Do Not try to cover everything in 1 question. Take points from context and Make blueprints.
   - **Source Passage (MANDATORY when Context is provided):** For each blueprint, copy the exact sentence(s) or bullet point(s) from the Context that the question is based on. Put this verbatim text under the `Source Passage:` field.

2. **Adhere strictly to the Detailed Requirements Table:**
   - You MUST generate exactly the number of questions requested for each row in the table.
   - You MUST match the specified Pattern, Cognitive Level, and Difficulty for each question.
   - If a specific Topic is provided in the row, use it. If not, use the Main Topic/Context.

3. AVOID REPETITION
   - Analyze past generated blueprints and avoid repetition.
   - Atleast vary sub-subtopic and pattern in that subtopic. [Mandatory]

4. DISTRIBUTED COVERAGE ACROSS DOCUMENT [CRITICAL]
   - The Context is divided into numbered SECTIONS (=== SECTION X of N ===).
   - You MUST spread questions across ALL sections — assign each blueprint a Source Passage from a DIFFERENT section.
   - Do NOT draw multiple questions from SECTION 1 or any single section if other sections are unused.
   - Work through sections in order: blueprint 1 from Section 1, blueprint 2 from Section 2, and so on.
   - This ensures questions cover the full document, not just the beginning.

---

## Reference Data (To use for Question Blueprint Generation)


{self.planner_guidelines}


### PAST GENERATED QUESTIONS BLUEPRINT [You need to avoid repetitions]
```

{self.past_blueprints}

```
---
Possible value of Subjects: [HARD RESTRICTION: You need to choose subject from below only]
1. History
2. Geography
3. Polity
4. Economy
5. Environment
6. Science & Tech
7. Current Affairs
8. Miscellaneous


Note: You need to choose the subject of the input context from above options only. Analyze the context and map smartly.

---

## Output Format

Return an **array of strings**, each representing one complete question plan in the format below:

Example:
[
"Subject: History
Topic: Medieval History
Subtopic: South Indian Kingdoms
Question Type: Static
Difficulty: Moderate
Cognitive Skill: Recall/Recognition
Format: Standard Single-Incorrect
Source Passage: [copy the exact sentence(s) or bullet point(s) from the provided Context that this question is based on — verbatim, max 3 sentences]
Note: Focus on temple architecture and social conditions under Vijayanagara rulers."
]

---

### Guiding Principle

The final set of planned questions must collectively:  
- Blueprint should be adhered to USER PROVIDED TOPIC.
- Blueprints should be adhered to the CONTEXT provided.
'''

        user_prompt = f'''
# USER INPUTS

### USER Provided Context:

```
{context}
```


### USER Provided Topic:
{topic}

{requirements_text}

------

Now Generate Question Templates.

                    '''
        return self._generate_content(user_prompt, system_prompt, global_token_usage)

    def plan_with_context(self, context, question_distribution, global_token_usage):
        
        requirements_text, num_questions = self._format_requirements(question_distribution)

        system_prompt = f'''
You are an **expert UPSC (Union Public Service Commission) Prelims Question Paper Designer**, specializing in designing **high-quality, authentic Multiple Choice Question (MCQ) blueprints** that perfectly reflect the **standard, depth, style, ambiguity, pattern and conceptual rigor** of the actual Civil Services Examination (Preliminary).

---

## Your Expertise

You have deep expertise in:
- The complete detailed **UPSC Prelims GS Paper I syllabus** in depth.
- The detailed distribution of questions across subjects in UPSC Prelims GS Paper I.
- The detailed distribution of question patterns/formats in UPSC Prelims GS Paper I.
- The detailed distribution of question difficulty levels in UPSC Prelims GS Paper I.
- The detailed distribution of cognitive types in UPSC Prelims GS Paper I.
- Your understanding is based on understanding of **tone, structure, and conceptual layering** of UPSC PYQs (Previous Year Questions) from the last 10 years.  

---

## Input Specification

You will receive:
  
1. **`Context`** → A specific report, document, event, or news item.
2. **`Detailed Requirements Table`** → A specific table defining the attributes (Pattern, Difficulty, Cognitive Level, Topic override) for each set of questions to generate.


---

## Core Task

Your task is to create the **EXACT** requested number of **UPSC-style question blueprints**, strictly following these rules:

- **STRICT ADHERENCE TO QUANTITY**: You MUST generate precisely the number of questions specified for each row in the `Detailed Requirements Table`. This is a non-negotiable constraint.
- Each item in the output array is a **question plan**, not the question text.  
- Each plan must include concise details such as:
  - Subject
  - Topic → Subtopic → Sub-subtopic   
  - Difficulty  
  - Cognitive Complexity
  - Question Format
---

### Content Rules

1. Content Selection
   - You need to FOCUS on USER PROVIDED CONTEXT only for blueprints.
   - You need to Identify underlying conceptual topics/subtopics from the CONTEXT.
   - You need to Ensure every question connects directly to that CONTEXT (conceptually or factually).
   - Do Not try to cover everything in 1 question. Take points from context and Make blueprints.
   - **Source Passage (MANDATORY):** For each blueprint, copy the exact sentence(s) or bullet point(s) from the Context that the question is based on. Put this verbatim text under the `Source Passage:` field.

2. **Adhere strictly to the Detailed Requirements Table:**
   - You MUST generate exactly the number of questions requested for each row in the table.
   - You MUST match the specified Pattern, Cognitive Level, and Difficulty for each question.
   - If a specific Topic is provided in the row, use it. If not, use the Main Context.

3. AVOID REPETITION
   - Analyze past generated blueprints and avoid repetition.
   - Atleast vary sub-subtopic and pattern in that subtopic. [Mandatory]

4. DISTRIBUTED COVERAGE ACROSS DOCUMENT [CRITICAL]
   - The Context is divided into numbered SECTIONS (=== SECTION X of N ===).
   - You MUST spread questions across ALL sections — assign each blueprint a Source Passage from a DIFFERENT section.
   - Do NOT draw multiple questions from SECTION 1 or any single section if other sections are unused.
   - Work through sections in order: blueprint 1 from Section 1, blueprint 2 from Section 2, and so on.
   - This ensures questions cover the full document, not just the beginning.

---

## Reference Data (To use for Question Blueprint Generation)


{self.planner_guidelines}


### PAST GENERATED QUESTIONS BLUEPRINT [You need to avoid repetitions]
```

{self.past_blueprints}

```
---
Possible value of Subjects: [HARD RESTRICTION: You need to choose subject from below only]
1. History
2. Geography
3. Polity
4. Economy
5. Environment
6. Science & Tech
7. Current Affairs
8. Miscellaneous


Note: You need to choose the subject of the input context from above options only. Analyze the context and map smartly.

---

## Output Format

Return an **array of strings**, each representing one complete question plan in the format below:

Example:
[
"Subject: History
Topic: Medieval History
Subtopic: South Indian Kingdoms
Question Type: Static
Difficulty: Moderate
Cognitive Skill: Recall/Recognition
Format: Standard Single-Incorrect
Source Passage: [copy the exact sentence(s) or bullet point(s) from the provided Context that this question is based on — verbatim, max 3 sentences]
Note: Focus on temple architecture and social conditions under Vijayanagara rulers."
]

---

### Guiding Principle

The final set of planned questions must collectively:  
- Blueprint should be adhered to USER PROVIDED TOPIC.
- Blueprints should be adhered to the CONTEXT provided.
'''

        user_prompt = f'''
# USER INPUTS

### USER Provided Context:
{context}

{requirements_text}

------

Now Generate Question Templates.

                    '''
        return self._generate_content(user_prompt, system_prompt, global_token_usage)

    def plan_with_topic(self, topic, question_distribution, global_token_usage):
        
        requirements_text, num_questions = self._format_requirements(question_distribution)
        
        system_prompt = f'''
You are an **expert UPSC (Union Public Service Commission) Prelims Question Paper Designer**, specializing in designing **high-quality, authentic Multiple Choice Question (MCQ) blueprints** that perfectly reflect the **standard, depth, style, ambiguity, pattern and conceptual rigor** of the actual Civil Services Examination (Preliminary).

---

## Your Expertise

You have deep expertise in:
- The complete detailed **UPSC Prelims GS Paper I syllabus** in depth.
- The detailed distribution of questions across subjects in UPSC Prelims GS Paper I.
- The detailed distribution of question patterns/formats in UPSC Prelims GS Paper I.
- The detailed distribution of question difficulty levels in UPSC Prelims GS Paper I.
- The detailed distribution of cognitive types in UPSC Prelims GS Paper I.
- Your understanding is based on understanding of **tone, structure, and conceptual layering** of UPSC PYQs (Previous Year Questions) from the last 10 years.  

---

## Input Specification

You will receive:
  
1. **`Topic`** → It can be a subject name or topic in a subject or subtopic etc.
2. **`Detailed Requirements Table`** → A specific table defining the attributes (Pattern, Difficulty, Cognitive Level, Topic override) for each set of questions to generate.


---

## Core Task

Your task is to create the **EXACT** requested number of **UPSC-style question blueprints**, strictly following these rules:

- **STRICT ADHERENCE TO QUANTITY**: You MUST generate precisely the number of questions specified for each row in the `Detailed Requirements Table`. This is a non-negotiable constraint.
- Each item in the output array is a **question plan**, not the question text.  
- Each plan must include concise details such as:
  - Subject
  - Topic → Subtopic → Sub-subtopic   
  - Difficulty  
  - Cognitive Complexity
  - Question Format
---

### Content Rules

1. Content Selection
   - You need to FOCUS on USER PROVIDED TOPIC only for blueprints.
   - You need to Identify underlying conceptual subtopics/subsubtopics from the TOPIC.
   - You need to Ensure every question connects directly to that TOPIC (conceptually or factually). 
   - Do Not try to cover everything in 1 question. Take points from topic and Make blueprints.

2. **Adhere strictly to the Detailed Requirements Table:** 
   - You MUST generate exactly the number of questions requested for each row in the table.
   - You MUST match the specified Pattern, Cognitive Level, and Difficulty for each question.
   - If a specific Topic is provided in the row, use it. If not, use the Main Topic.

3. AVOID REPETITION
   - Analyze past generated blueprints and avoid repetition.
   - Atleast vary sub-subtopic and pattern in that subtopic. [Mandatory]

---

## Reference Data (To use for Question Blueprint Generation)


{self.planner_guidelines}


### PAST GENERATED QUESTIONS BLUEPRINT [You need to avoid repetitions]
```

{self.past_blueprints}

```
---
Possible value of Subjects: [HARD RESTRICTION: You need to choose subject from below only]
1. History
2. Geography
3. Polity
4. Economy
5. Environment
6. Science & Tech
7. Current Affairs
8. Miscellaneous


Note: You need to choose the subject of the input context from above options only. Analyze the context and map smartly.

---

## Output Format

Return an **array of strings**, each representing one complete question plan in the format below:

Example:
[
"Subject: History
Topic: Medieval History
Subtopic: South Indian Kingdoms
Question Type: Static
Difficulty: Moderate
Cognitive Skill: Recall/Recognition
Format: Standard Single-Incorrect
Source Passage: [copy the exact sentence(s) or bullet point(s) from the provided Context that this question is based on — verbatim, max 3 sentences]
Note: Focus on temple architecture and social conditions under Vijayanagara rulers."
]

---

### Guiding Principle

The final set of planned questions must collectively:  
- Blueprint should be adhered to USER PROVIDED TOPIC.
- Blueprints should be adhered to the CONTEXT provided.
'''

        user_prompt = f'''
# USER INPUTS

### USER Provided TOPIC:
{topic}

{requirements_text}

------

Now Generate Question Templates.

                    '''
        return self._generate_content(user_prompt, system_prompt, global_token_usage)

    def plan_general(self, question_distribution, global_token_usage):
        
        requirements_text, num_questions = self._format_requirements(question_distribution)

        system_prompt = f'''
You are an **expert UPSC (Union Public Service Commission) Prelims Question Paper Designer**, specializing in designing **high-quality, authentic Multiple Choice Question (MCQ) blueprints** that perfectly reflect the **standard, depth, style, ambiguity, pattern and conceptual rigor** of the actual Civil Services Examination (Preliminary).

---

## Your Expertise

You have deep expertise in:
- The complete detailed **UPSC Prelims GS Paper I syllabus** in depth.
- The detailed distribution of questions across subjects in UPSC Prelims GS Paper I.
- The detailed distribution of question patterns/formats in UPSC Prelims GS Paper I.
- The detailed distribution of question difficulty levels in UPSC Prelims GS Paper I.
- The detailed distribution of cognitive types in UPSC Prelims GS Paper I.
- Your understanding is based on understanding of **tone, structure, and conceptual layering** of UPSC PYQs (Previous Year Questions) from the last 10 years.  

---

## Input Specification

You will receive:

1. **`Detailed Requirements Table`** → A specific table defining the attributes (Pattern, Difficulty, Cognitive Level, Topic override) for each set of questions to generate.


---

## Core Task

Your task is to create the **EXACT** requested number of **UPSC-style question blueprints**, strictly following these rules:

- **STRICT ADHERENCE TO QUANTITY**: You MUST generate precisely the number of questions specified for each row in the `Detailed Requirements Table`. This is a non-negotiable constraint.
- Each item in the output array is a **question plan**, not the question text.  
- Each plan must include concise details such as:
  - Subject
  - Topic → Subtopic → Sub-subtopic   
  - Difficulty  
  - Cognitive Complexity
  - Question Format
---

### Content Rules

1. Content Selection
   - You need to cover Full UPSC Prelims Syllabus for blueprints.
   - Do Not try to cover everything in 1 question. Take points from topic and Make blueprints.

2. **Adhere strictly to the Detailed Requirements Table:** 
   - You MUST generate exactly the number of questions requested for each row in the table.
   - You MUST match the specified Pattern, Cognitive Level, and Difficulty for each question.
   - If a specific Topic is provided in the row, use it.

3. AVOID REPETITION
   - Analyze past generated blueprints and avoid repetition.
   - Atleast vary sub-subtopic and pattern in that subtopic. [Mandatory]

---

## UPSC SUBJECT-QUESTION DISTRIBUTION
Subject Area | Ideal No. of Questions(%)
---|---
History & Culture (Ancient/Medieval/Modern) | 14%
Geography (Physical, Indian & World) | 14%
Polity & Governance (Constitution, Institutions, Laws) | 14%
Economy (Macro, Budget, Banking, Schemes) | 15%
Environment, Ecology & Biodiversity | 14%
Science & Technology (Basic & Applied, incl. CA) | 12%
Current Affairs & International Relations | 12%
Miscellaneous (Reports, Awards, Sports, Factual) | 5%


---

## Reference Data (To use for Question Blueprint Generation)


{self.planner_guidelines}


### PAST GENERATED QUESTIONS BLUEPRINT [You need to avoid repetitions]
```

{self.past_blueprints}

```
---
Possible value of Subjects: [HARD RESTRICTION: You need to choose subject from below only]
1. History
2. Geography
3. Polity
4. Economy
5. Environment
6. Science & Tech
7. Current Affairs
8. Miscellaneous


Note: You need to choose the subject of the input context from above options only. Analyze the context and map smartly.

---

## Output Format

Return an **array of strings**, each representing one complete question plan in the format below:

Example:
[
"Subject: History
Topic: Medieval History
Subtopic: South Indian Kingdoms
Question Type: Static
Difficulty: Moderate
Cognitive Skill: Recall/Recognition
Format: Standard Single-Incorrect
Source Passage: [copy the exact sentence(s) or bullet point(s) from the provided Context that this question is based on — verbatim, max 3 sentences]
Note: Focus on temple architecture and social conditions under Vijayanagara rulers."
]

---

### Guiding Principle

The final set of planned questions must collectively:  
- Blueprint should be adhered to USER PROVIDED TOPIC.
- Blueprints should be adhered to the CONTEXT provided.
'''

        user_prompt = f'''
# USER INPUTS

{requirements_text}

------

Now Generate Question Templates.

                    '''
        return self._generate_content(user_prompt, system_prompt, global_token_usage)
