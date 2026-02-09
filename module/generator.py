from google.genai import types
import random
import time
import re
try:
    from .models import QuestionLLM
    from .prompt_crafter import PromptCrafter
except ImportError:
    from models import QuestionLLM
    from prompt_crafter import PromptCrafter




class GeneratorAgent:
    def __init__(self, client):
        self.client = client
        self.model = "gemini-2.5-pro"

        # Initialize Prompt Crafter
        self.prompt_crafter = PromptCrafter()

    def _validate_sequence_randomization(self, question_obj, blueprint):
        """
        Validates that chronological/geographical sequencing questions don't have
        predictable sequences like "1-2-3-4" or "4-3-2-1" as the correct answer.

        Returns: (is_valid: bool, error_message: str)
        """
        # Check if this is a sequencing question
        blueprint_lower = blueprint.lower()
        is_sequencing = any(keyword in blueprint_lower for keyword in
                           ["chronological", "geographical", "sequencing", "correct chronological order",
                            "correct sequence", "north to south", "east to west", "earliest first"])

        if not is_sequencing:
            return True, ""

        # Get the correct answer
        correct_option_idx = ord(question_obj.answer) - ord('A')
        correct_option = question_obj.options[correct_option_idx]

        # Extract sequence pattern from the answer (e.g., "1-2-3-4", "2-3-1-4")
        sequence_pattern = re.findall(r'\d+\s*[-–—]\s*\d+\s*[-–—]\s*\d+\s*[-–—]\s*\d+', correct_option)

        if sequence_pattern:
            # Normalize the sequence (remove spaces and standardize dashes)
            sequence = re.sub(r'\s+', '', sequence_pattern[0])
            sequence = re.sub(r'[–—]', '-', sequence)

            # Check for forbidden sequences
            forbidden = ["1-2-3-4", "4-3-2-1"]
            if sequence in forbidden:
                return False, f"Forbidden sequence '{sequence}' detected as correct answer. This makes the answer too predictable."

        return True, ""

    def _validate_assertion_reason_format(self, question_obj, blueprint):
        """
        Validates that Assertion-Reason questions have proper option structure.

        Returns: (is_valid: bool, error_message: str)
        """
        blueprint_lower = blueprint.lower()
        is_assertion_reason = any(keyword in blueprint_lower for keyword in
                                 ["assertion", "assertion-reason", "statement-i", "statement-ii"])

        if not is_assertion_reason:
            return True, ""

        # Check if options follow A/R format
        option_a = question_obj.options[0].lower()

        # A/R format should have keywords like "both", "correct", "explains", "explanation"
        ar_keywords = ["both", "correct", "incorrect", "explains", "explanation"]
        has_ar_format = any(keyword in option_a for keyword in ar_keywords)

        if not has_ar_format:
            return False, "Assertion-Reason question doesn't have proper A/R option format. Options should discuss whether statements are correct and if one explains the other."

        return True, ""

    def _count_statements(self, question_text):
        """
        Count the number of statements in a multi-statement question.
        Returns the highest statement number found (not just count of matches).
        """
        roman_map = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5}

        # Pattern 1: Numbered statements like "1.", "2.", "3.", "4." - get highest number
        numbered_matches = re.findall(r'(?:^|\n)\s*(\d+)\.\s+', question_text)
        numbered_count = max(int(n) for n in numbered_matches) if numbered_matches else 0

        # Pattern 2: Roman numeral statements like "I.", "II.", "III.", "IV."
        roman_matches = re.findall(r'(?:^|\n)\s*(I{1,3}|IV|V)\.\s+', question_text, re.IGNORECASE)
        roman_count = max(roman_map.get(m.lower(), 0) for m in roman_matches) if roman_matches else 0

        # Pattern 3: Statement-I, Statement-II, Statement-III format
        statement_matches = re.findall(r'Statement[-\s]*(I{1,3}|IV|\d+)', question_text, re.IGNORECASE)
        statement_count = 0
        for m in statement_matches:
            m_lower = m.lower()
            if m_lower in roman_map:
                statement_count = max(statement_count, roman_map[m_lower])
            elif m.isdigit():
                statement_count = max(statement_count, int(m))

        return max(numbered_count, roman_count, statement_count)

    def _validate_closing_question(self, question_obj, blueprint):
        """
        Validates that multi-statement questions have the required closing question.
        Returns: (is_valid: bool, error_message: str)
        """
        blueprint_lower = blueprint.lower()
        question_lower = question_obj.question.lower()

        # Check for multi-statement patterns (correct/incorrect variants)
        if 'multiple-statement' in blueprint_lower:
            closing_patterns = [
                "which of the statements given above is/are correct",
                "which of the statements given above is/are not correct",
                "which of the statements given above are incorrect",
                "which of the above statements is/are correct",
                "which of the above statements is/are not correct"
            ]
            has_closing = any(p in question_lower for p in closing_patterns)
            if not has_closing:
                return False, "Multi-statement question missing closing question (e.g., 'Which of the statements given above is/are correct?')"

        # Check for "How Many" patterns
        if 'how many' in blueprint_lower:
            closing_patterns = [
                "how many of the statements given above are correct",
                "how many of the above statements are correct",
                "how many of the statements given above is/are correct"
            ]
            has_closing = any(p in question_lower for p in closing_patterns)
            if not has_closing:
                return False, "How-Many question missing closing question (e.g., 'How many of the statements given above are correct?')"

        # Check for assertion-reason patterns
        if 'assertion' in blueprint_lower or '3-stmt' in blueprint_lower or '2-stmt' in blueprint_lower:
            closing_patterns = [
                "which one of the following is correct in respect of the above statements",
                "which of the following is correct in respect of the above"
            ]
            has_closing = any(p in question_lower for p in closing_patterns)
            if not has_closing:
                return False, "Assertion-Reason question missing closing question (e.g., 'Which one of the following is correct in respect of the above statements?')"

        return True, ""

    def _validate_statement_completeness(self, question_obj, blueprint):
        """
        Validates that all expected statements are present in the question.

        Returns: (is_valid: bool, error_message: str)
        """
        # Extract expected statement count from blueprint/pattern name
        blueprint_lower = blueprint.lower()

        # Check for patterns like "Multiple-Statement-3", "Multiple-Statement-4", etc.
        pattern_match = re.search(r'multiple[-\s]*statement[-\s]*(\d+)', blueprint_lower)

        if pattern_match:
            expected_count = int(pattern_match.group(1))
            actual_count = self._count_statements(question_obj.question)

            if actual_count < expected_count:
                return False, f"Expected {expected_count} statements but found only {actual_count}. Last statement may be missing."

        # Check for 3-statement Assertion-Reason
        if "3-stmt assertion" in blueprint_lower or "complex 3-stmt" in blueprint_lower:
            actual_count = self._count_statements(question_obj.question)
            if actual_count < 3:
                return False, f"Expected 3 statements for Complex Assertion-Reason but found only {actual_count}."

        return True, ""

    async def generate_question(self, blueprint, global_token_usage):

        # Delegate prompt creation to PromptCrafter
        system_instruction = self.prompt_crafter.craft_prompt(blueprint)

        # 1. Define the actual python function (Logic)
        def get_random_answer_key():
            return random.choice(["A", "B", "C", "D"])

        # Detect pattern type early for retry count
        blueprint_lower = blueprint.lower()

        # Use more retries for critical patterns that often fail
        is_critical_pattern = (
            'multiple-statement-4' in blueprint_lower or
            'complex 3-stmt' in blueprint_lower or
            '3-stmt assertion' in blueprint_lower
        )
        max_retries = 5 if is_critical_pattern else 3

        for attempt in range(max_retries):
            ans = get_random_answer_key()
            print(f'-------- Answer: {ans} (Attempt {attempt + 1}/{max_retries})')
            pattern_constraint = ""

            if 'multiple-statement-4' in blueprint_lower:
                pattern_constraint = """
##########################################################
# CRITICAL: THIS IS A 4-STATEMENT QUESTION               #
##########################################################

YOU MUST GENERATE EXACTLY 4 STATEMENTS. NOT 3. FOUR (4).

REQUIRED STRUCTURE:
1. [First statement]
2. [Second statement]
3. [Third statement]
4. [Fourth statement] ← THIS IS MANDATORY. DO NOT SKIP.

Which of the statements given above is/are correct?

CHECKLIST BEFORE RESPONDING:
☐ Statement 1 exists
☐ Statement 2 exists
☐ Statement 3 exists
☐ Statement 4 exists ← VERIFY THIS IS PRESENT
☐ Closing question exists AFTER statement 4

IF YOU ONLY HAVE 3 STATEMENTS, YOU ARE WRONG. ADD A 4TH.
"""
            elif 'complex 3-stmt' in blueprint_lower or '3-stmt assertion' in blueprint_lower:
                pattern_constraint = """
### CRITICAL STRUCTURE REQUIREMENT:
This is a 3-STATEMENT ASSERTION-REASON question. You MUST:
1. Include Statement-I, Statement-II, AND Statement-III
2. DO NOT omit Statement-III
3. Use 3-statement options (tests if II and III explain I)
4. End with "Which one of the following is correct in respect of the above statements?"

DO NOT use 2-statement assertion-reason format. All 3 statements required.
"""
            elif 'multiple-statement-3' in blueprint_lower:
                pattern_constraint = """
### CRITICAL STRUCTURE REQUIREMENT:
This question requires EXACTLY 3 statements numbered 1, 2, 3. Include all 3 and end with the closing question.
"""
            elif 'multiple-statement-2' in blueprint_lower:
                pattern_constraint = """
### CRITICAL STRUCTURE REQUIREMENT:
This question requires EXACTLY 2 statements (I and II or 1 and 2). Include both and end with the closing question.
"""

            # Check if blueprint contains web research reference material
            has_reference = "--- REFERENCE MATERIAL" in blueprint
            reference_instruction = ""
            if has_reference:
                reference_instruction = (
                    "\n### IMPORTANT: Reference Material is provided below the blueprint. "
                    "You MUST use the facts, data points, and information from the Reference Material "
                    "to create an accurate, up-to-date question. Do NOT rely on your training data for "
                    "current affairs facts — use the Reference Material as your primary source of truth.\n"
                )

            user_prompt = f'''## Use below details to generate the question.
{pattern_constraint}{reference_instruction}
### Question Blueprint
{blueprint}

### MANDATORY Constraint: Generate the question and options in such manner that answer is {ans}.

### Now generate question.
'''

            try:
                resp = await self.client.models.generate_content(
                        model=self.model,
                        contents=[user_prompt],
                        config=types.GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=70000,
                            response_mime_type="application/json",
                            response_schema=QuestionLLM,
                            system_instruction=system_instruction,
                        ),
                    )

                if hasattr(resp, 'usage_metadata'):
                    global_token_usage.append(resp.usage_metadata)

                question_obj = resp.parsed

                # Validate sequence randomization
                is_valid_seq, seq_error = self._validate_sequence_randomization(question_obj, blueprint)
                if not is_valid_seq:
                    print(f"Validation Error (Sequence): {seq_error}")
                    if attempt < max_retries - 1:
                        print("Retrying question generation...")
                        time.sleep(1)
                        continue

                # Validate assertion-reason format
                is_valid_ar, ar_error = self._validate_assertion_reason_format(question_obj, blueprint)
                if not is_valid_ar:
                    print(f"Validation Error (A/R Format): {ar_error}")
                    if attempt < max_retries - 1:
                        print("Retrying question generation...")
                        time.sleep(1)
                        continue

                # Validate statement completeness
                is_valid_stmt, stmt_error = self._validate_statement_completeness(question_obj, blueprint)
                if not is_valid_stmt:
                    print(f"Validation Error (Statement Count): {stmt_error}")
                    if attempt < max_retries - 1:
                        print("Retrying question generation...")
                        time.sleep(1)
                        continue

                # Validate closing question presence
                is_valid_closing, closing_error = self._validate_closing_question(question_obj, blueprint)
                if not is_valid_closing:
                    print(f"Validation Error (Closing Question): {closing_error}")
                    if attempt < max_retries - 1:
                        print("Retrying question generation...")
                        time.sleep(1)
                        continue

                # All validations passed
                print("✓ All validations passed")
                return question_obj

            except Exception as e:
                print(f"Generator Error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Brief backoff
                    continue
                return None

        # If all retries exhausted, check if this is a critical pattern
        # For 4-statement and 3-stmt A/R patterns, return None instead of defective question
        blueprint_lower = blueprint.lower()
        is_critical_pattern = (
            'multiple-statement-4' in blueprint_lower or
            'complex 3-stmt' in blueprint_lower or
            '3-stmt assertion' in blueprint_lower
        )

        if is_critical_pattern and 'question_obj' in locals():
            # Re-check validation for critical patterns
            stmt_valid, _ = self._validate_statement_completeness(question_obj, blueprint)
            closing_valid, _ = self._validate_closing_question(question_obj, blueprint)
            if not stmt_valid or not closing_valid:
                print("ERROR: Critical pattern validation failed after all retries. Returning None.")
                return None

        print("Warning: Max retries reached. Returning question despite validation issues.")
        return question_obj if 'question_obj' in locals() else None
