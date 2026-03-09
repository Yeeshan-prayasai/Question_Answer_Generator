"""
Regenerate explanations for questions where the explanation's correct answer
doesn't match the DB answer column. Uses Google Search grounding for current affairs.
"""
import os, json, asyncio, tomllib
import psycopg2, psycopg2.extras
from google import genai
from google.genai import types

secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
with open(secrets_path, 'rb') as f:
    secrets = tomllib.load(f)

DB_CONFIG = {
    "host": secrets["host"], "database": secrets["database"],
    "user": secrets["user"], "password": secrets["password"], "port": secrets["port"],
}

os.environ['GEMINI_API_KEY'] = secrets["api_key"]
async_client = genai.Client().aio
MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTION = """You are an expert UPSC Prelims explanation writer. Generate concise, exam-oriented explanations in English with consistent markdown formatting.

## DYNAMIC KNOWLEDGE PROTOCOL
- **Temporal Awareness:** You are an expert analyst operating in real-time. Always evaluate if a concept is current, legacy, or newly updated.
- **Verification First:** Before drafting an explanation, check for the latest government notifications, law amendments, or data releases.
- **Adaptive Nomenclature:** If a scheme has been rebranded or replaced, prioritize the most recent official version.

## OUTPUT FORMAT
Return ONLY the markdown explanation (English only, no JSON wrapper). Use these exact sections IN THIS ORDER with BLANK LINES between sections:

1. **Correct Answer: [Letter]** (at the very top, bold)
2. **Statement Analysis** (bold text, normal size)
3. **Core Concept** (bold text, normal size, 60-80 words)
4. **Logical Elimination and Educated Guesstimate** (only when applicable)
5. **Key Points to Remember** (bold text, normal size)
6. **Why This Question?** (bold text, normal size)

## MARKDOWN FORMATTING RULES

### Use These:
- **bold** for section headers (NO markdown heading syntax — no #, ##, or ###)
- **bold** for exam-relevant keywords in Core Concept (technical terms, acts, articles, years, personalities)
- ✓ for correct statements | ✗ for incorrect statements
- NUMBERED statements (1, 2, 3) as per official UPSC format (MANDATORY)
- `-` (dash with space) for main bullet points
- `  -` (two spaces + dash) for sub-bullets under main points
- Blank line before and after Key Points section for readability

### Don't Use:
- NO markdown heading syntax (#, ##, ###) — use bold text instead
- NO code blocks with ```
- NO alphabetical labeling (a, b, c) — use numbers (1, 2, 3) for statements
- NO generic bolding ("important", "significant") — only bold exam-relevant terms

## CONTENT GUIDELINES

### Statement Analysis:
- Number each statement as 1, 2, 3 (official UPSC format)
- Format: `1. **Statement 1:** ✓ Correct — [10-15 word reason]`
- Be direct and assertive

### Core Concept (60-80 words):
- Analytical depth with mechanisms, relationships, and underlying principles
- Bold ONLY exam-relevant terms: technical concepts, constitutional refs, acts, years, key personalities

### Logical Elimination (only when applicable):
- Step-by-step elimination logic, 2-3 sentences max

### Key Points to Remember:
- 3-5 main bullets with 1-3 sub-bullets each
- Bold the concept name/heading on each main bullet

### Why This Question? (2-3 sentences):
- Current affairs relevance OR syllabus linkage
"""

MISMATCH_IDS = [
    '99d61b22-4d1b-481b-839a-e039c16bd447',
    'ee96ba3b-fe03-4b1e-94aa-6c50bd84d555',
    '4b00cfc0-fb91-4707-8768-41b9f349cab6',
    '8905a3ff-0844-4a46-8d44-1ea00bc4f452',
]


async def generate_with_search(question_text: str, options: dict, answer: str) -> str:
    opts_text = "\n".join(f"({k.upper()}) {v}" for k, v in sorted(options.items()))
    prompt = (
        f"Generate a detailed UPSC Prelims explanation for this question. "
        f"Use web search to verify the latest facts before writing.\n\n"
        f"**Question:**\n{question_text}\n\n"
        f"**Options:**\n{opts_text}\n\n"
        f"**Correct Answer: {answer}**\n\n"
        f"The correct answer is definitively {answer}. "
        f"Use Google Search to verify the facts, then write the explanation confirming why {answer} is correct "
        f"and explaining why the other options are wrong. "
        f"Follow the system instructions exactly. Output markdown only (English only, no JSON)."
    )

    grounding_tool = types.Tool(google_search=types.GoogleSearch())

    resp = await async_client.models.generate_content(
        model=MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.1,
            max_output_tokens=2000,
            tools=[grounding_tool],
        ),
    )
    return resp.text.strip() if resp.text else ""


async def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    for uid in MISMATCH_IDS:
        cur.execute(
            'SELECT question_english, options_english, answer FROM upsc_prelims_ai_generated_que WHERE id = %s',
            (uid,)
        )
        row = cur.fetchone()
        opts = row['options_english']
        if isinstance(opts, str):
            opts = json.loads(opts)

        print(f"\n{'='*60}")
        print(f"ID: {uid}")
        print(f"DB Answer: {row['answer']}")
        print(f"Question: {row['question_english'][:100]}...")
        print("Generating with web search...")

        result = await generate_with_search(row['question_english'], opts, row['answer'])

        if result:
            print(f"Result first line: {result.splitlines()[0]}")
            cur.execute(
                "UPDATE upsc_prelims_ai_generated_que SET explanation = %s WHERE id = %s",
                (result, uid)
            )
            conn.commit()
            print("Saved.")
        else:
            print("ERROR: empty result, skipping.")

        await asyncio.sleep(1)

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
