from typing import Dict, Optional
import re
import random
try:
    from .prompt_config import PROMPT_CONFIG
except ImportError:
    from prompt_config import PROMPT_CONFIG

class PromptCrafter:
    def __init__(self):
        self.config = PROMPT_CONFIG

    def _find_match(self, text: str, category: str) -> Optional[Dict[str, str]]:
        """
        Finds the matching configuration for a given category in the text.
        If no match is found for patterns and default mode is needed, randomly selects one.
        """
        items = self.config.get(category, {})
        text_lower = text.lower()

        # Sort keys by length descending to match longest phrases first (for exact matching)
        sorted_keys = sorted(items.keys(), key=len, reverse=True)

        for key in sorted_keys:
            if key.lower() in text_lower:
                return items[key]

        # If category is "patterns" and no match found, use random selection for default mode
        if category == "patterns":
            # Check if this looks like a case where format was not specified
            # (no pattern keywords found in blueprint)
            pattern_keywords = ["format:", "pattern:", "standard", "multiple-statement",
                              "chronological", "assertion", "pairs", "sequencing"]
            has_pattern = any(keyword in text_lower for keyword in pattern_keywords)

            if not has_pattern:
                # Randomly select a pattern for default mode
                random_key = random.choice(list(items.keys()))
                print(f"Default mode activated: Randomly selected pattern '{random_key}'")
                return items[random_key]

        return None

    def craft_prompt(self, blueprint: str) -> str:
        """
        Constructs the detailed system prompt based on the blueprint.
        Ensures format/pattern takes priority over cognitive level and difficulty.
        """

        # Identify components - pattern is MANDATORY and takes priority
        pattern_info = self._find_match(blueprint, "patterns")
        cognitive_info = self._find_match(blueprint, "cognitive_types")
        difficulty_info = self._find_match(blueprint, "difficulty_levels")

        # Build sections
        pattern_section = ""
        if pattern_info:
            pattern_section = f"""
### SPECIFIC QUESTION PATTERN INSTRUCTION [HIGHEST PRIORITY]
You MUST follow the Question pattern and Logic defined below. This is your PRIMARY constraint.
{pattern_info.get('description', '')}

**Reference Example:**
{pattern_info.get('example', '')}
"""
        else:
            # If no pattern found, this is a warning but we continue
            print("Warning: No specific pattern found in blueprint. Using general guidelines only.")

        cognitive_section = ""
        if cognitive_info:
            cognitive_section = f"""
### COGNITIVE OBJECTIVE [Secondary Priority]
Target Cognitive Level: {cognitive_info.get('description', '')}
Example Context: {cognitive_info.get('example', '')}

NOTE: If this cognitive level conflicts with the Pattern requirements above, prioritize the PATTERN.
"""
        else:
            # Default cognitive level if not specified
            cognitive_section = f"""
### COGNITIVE OBJECTIVE [Secondary Priority]
Target Cognitive Level: Standard UPSC Comprehension/Conceptual level.

NOTE: Focus primarily on matching the PATTERN requirements. Ensure all parts of the question align with the chosen pattern. Do not omit any statements or alter the structure.
"""

        # Default difficulty if not specified
        if difficulty_info and isinstance(difficulty_info, str):
            difficulty_text = difficulty_info
        else:
            difficulty_text = "Moderate - Standard UPSC Prelims Level"

        # Construct final prompt
        prompt = f'''
You are an **expert UPSC (Union Public Service Commission) Prelims Question Generator Agent**.
---
## Your Expertise
You have deep expertise in:
- The complete **UPSC Prelims GS Paper I syllabus**.  
- The **tone, structure, and conceptual layering** of UPSC PYQs.  
- The **art of framing close, plausible options** and **balanced distractors**.
---
## Input Specification
    **`question_blueprint`** → A detailed plan describing the question to be generated.  
    - It specifies the **topic**, **subtopic**, **sub-subtopic**, **difficulty level**, **cognitive focus**, and **question format**.
    - Use this blueprint as the **sole reference**.
---
## Core Task
    Your task is to **generate a UPSC-style question** strictly based on the provided **question blueprint**.
    - **Difficulty Level Target:** {difficulty_text}
    - **Adherence:** The question must align **precisely** with the details mentioned in the input blueprint.

{pattern_section}

{cognitive_section}

---
## General Guidelines
1. The Stem (the main body of the question) must be written with the following constraints:
* Contain **one central idea** per stem.
* Avoid **excessive clauses and complex jargon**.

2. For multi-statement questions (e.g., "Which of the statements given above is/are correct?"):
* **MANDATORY STRUCTURE REQUIREMENT:** EVERY multi-statement question MUST include BOTH:
  - **Opening context:** Begin with an introductory phrase (e.g., "With reference to...", "Consider the following statements about...", "Consider the following regarding...")
  - **Closing question:** End with the appropriate closing question (e.g., "Which of the statements given above is/are correct?", "How many of the statements given above are correct?")
* **CRITICAL:** Include ALL statements completely. If the pattern specifies 4 statements, you MUST include all 4 statements numbered 1, 2, 3, and 4. Never truncate or omit the last statement.
* **Length:** The pattern specification will indicate the exact number of statements (2, 3, or 4). Follow the pattern precisely.
* **Independence:** Each statement should be **independent, testable, and concise**.
* **Pattern Avoidance:** Avoid predictable statement patterns across different questions.

3. Option & Distractor Rules

* **Correct Answer:** There must be a single best and defensible answer.
* **Homogeneity:** All options should be **homogeneous in form and approximately equal in length**.
* **Plausibility:** Every distractor must be **plausible to a partially informed candidate**.
* **Special Options:** Use "None of the above" or "All of the above" **sparingly and only when conceptually necessary**.

## MAJOR GUIDELINE
**
Use `get_random_answer_key` tool to get the answer option. Once we have it, generate the question and options order such that this option is the answer.
**


---

## Common Pitfalls and Quality Controls
    1. **Style and Flow**: Ensure natural flow, avoid excessive punctuation.
    2. **Multi-Statement Design**: Keep statements crisp, small, and to the point. Use standard numbering (1., 2., 3.).
    3. **Factual Question Difficulty**: Avoid common facts. Target obscure but relevant details.
    4. **Plausible Distractors**: All options must be plausible.
    5. **Avoid Ambiguity**: Ensure only one correct answer. Avoid overlapping options.
    6. **Clarity:** Avoid **idioms or colloquial expressions**.
    7. Do not make correct options as `a` or `any specific` always. It should vary. Shuffle options if needed. [do not give preference to any specific options]
    8. For Assertion-Reason type questions, do not make options such that always `a` options is answer. Make tricky wrong statements as well to trap students.
    
---

## Required Output Format

For question, provide the following in a clean, structured JSON format (as requested by schema):

**Question [Number]:**
[Question text, including all statements (1, 2, 3...) if any]

**Options:**
(a) [Option 1]
(b) [Option 2]
(c) [Option 3]
(d) [Option 4]

**Answer:** The correct option letter (A, B, C, or D)

'''
        return prompt
