from google.genai import types
import time
try:
    from .models import QuestionLLMHindi
except ImportError:
    from models import QuestionLLMHindi

class TranslatorAgent:
    def __init__(self, client):
        self.client = client
        self.model = "gemini-2.5-flash"

    async def translate_question(self, question_text, options_list, global_token_usage):
        
        # Format options for prompt
        options_text = ""
        for i, opt in enumerate(options_list):
            options_text += f"({chr(97+i)}) {opt}\n"

        prompt_hindi_converter = ''' ### Role
You are an expert **UPSC Translation Specialist** with deep knowledge of the Civil Services Examination (CSE) syllabus and official terminology across General Studies subjects (e.g., Polity, Economy, History). Your expertise is in converting English text to high-quality, standard Hindi.

---

### Objective
Your primary task is to receive a UPSC Previous Year Question (PYQ) in English and produce its complete, precise translation in the Hindi language, adhering strictly to UPSC's expected linguistic standards.

---

### Translation Guidelines
1.  **Standard Terminology (Crucial):** Use **official, standard Hindi vocabulary** recognized and employed by UPSC. For example, translate 'Judicial Review' as 'न्यायिक पुनर्विलोकन', 'Fiscal Deficit' as 'राजकोषीय घाटा', and 'Bill' as 'विधेयक'.
2.  **Accuracy and Flow:** Ensure the translation is grammatically correct and maintains the formal, authoritative tone and logical structure of the original English question.
3.  **Structure Preservation:** The question's structure (main statement, subsidiary statements/points 1, 2, 3..., and options a, b, c, d) must be perfectly preserved in the Hindi output.
4.  **Completeness:** Translate every part of the question and all options provided.
5.  **Option Mapping:** Ensure Option (a) in Hindi corresponds exactly to Option (a) in English, and so on.

* **IMPORTANT NOTE:** Do not use any English abbreviations in the Hindi translation. Use only Hindi terminology, or omit the abbreviated term if the full name is already present.

---

## Output Format
You **MUST** adhere to the following clean, structured format. Do not include any preamble, explanation, or additional text outside of this structure.

**प्रश्न [Number]:**
[The Hindi translation of the question text, including all statements (1, 2, 3...) if present]

**विकल्प:**
(a) [Hindi translation of Option 1]
(b) [Hindi translation of Option 2]
(c) [Hindi translation of Option 3]
(d) [Hindi translation of Option 4]

**उत्तर:** The correct option letter (A, B, C, or D)


'''
        user_prompt = f'''## Below is the question which you need to convert in to Hindi.

                            ### Question (English)
                            {question_text}
                            
                            ### Options (English)
                            {options_text}

                    '''
        
        try:
            resp = await self.client.models.generate_content(
                    model=self.model,
                    contents=[user_prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=65000,
                        response_mime_type="application/json",
                        response_schema=QuestionLLMHindi,
                        system_instruction=prompt_hindi_converter,
                    ),
                )
            
            if hasattr(resp, 'usage_metadata'):
                global_token_usage.append(resp.usage_metadata)

            return resp.parsed
        except Exception as e:
            time.sleep(5)
            return None
