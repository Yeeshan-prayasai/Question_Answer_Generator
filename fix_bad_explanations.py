"""
Fix bad-format explanations in upscdev.

Categories:
  1. no-bold Correct Answer  (7)  — simple text fix
  2. ### Explanation header  (2)  — simple text fix
  3. Preamble lines          (8)  — simple text fix
  4. Plain text              (17) — Gemini regeneration

Run: uv run python fix_bad_explanations.py
"""
import os, re, json, asyncio, time
import psycopg2, psycopg2.extras
import tomllib
from google import genai
from google.genai import types

secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
with open(secrets_path, 'rb') as f:
    secrets = tomllib.load(f)

DB_CONFIG = {
    "host": secrets["host"],
    "database": secrets["database"],
    "user": secrets["user"],
    "password": secrets["password"],
    "port": secrets["port"],
}

api_key = secrets["api_key"]
os.environ['GEMINI_API_KEY'] = api_key
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
- Use cause-effect language: "occurs due to", "results from", "arises because"
- Give equal weightage to ALL concepts in the question

### Logical Elimination (only when applicable):
- Step-by-step elimination logic, 2-3 sentences max
- Show how to narrow down using partial knowledge or exam strategy

### Key Points to Remember:
- 3-5 main bullets with 1-3 sub-bullets each
- Bold the concept name/heading on each main bullet
- Equal importance to all concepts in the question

### Why This Question? (2-3 sentences):
- Current affairs relevance OR syllabus linkage
- If recurring: "This [topic] is a recurring theme in UPSC Prelims/Mains examinations."
- Be specific with names, dates, references
"""

SECTION_NAMES = {'Statement Analysis', 'Core Concept', 'Logical Elimination and Educated Guesstimate',
                 'Key Points to Remember', 'Why This Question?', 'Option Analysis',
                 'Analysis of Options', 'Chronological Analysis'}


def classify(exp: str):
    lines = [l.strip() for l in exp.strip().split('\n') if l.strip()]
    first = lines[0] if lines else ''
    has_sections = bool(re.search(
        r'^\*\*(Statement Analysis|Core Concept|Key Points|Why This Question\?|Logical Elimination|Option Analysis)\*\*',
        exp, re.MULTILINE))
    has_h3 = bool(re.search(r'^#{1,3}\s+', exp, re.MULTILINE))

    if re.match(r'^\*\*Correct Answer', first):
        return 'ideal'
    elif re.match(r'^Correct Answer', first, re.IGNORECASE):
        return 'no_bold'
    elif has_h3:
        return 'h3_header'
    elif not has_sections:
        return 'plain'
    else:
        return 'preamble'


def text_fix(exp: str, category: str) -> str:
    """Apply simple text fixes without touching content."""
    text = exp.strip()

    if category == 'h3_header':
        # Remove leading ### Explanation line(s)
        text = re.sub(r'^#{1,3}\s+\w.*\n+', '', text).strip()

    if category == 'no_bold':
        # Add ** around "Correct Answer: X" on the first line
        text = re.sub(
            r'^(Correct Answer\s*:\s*\(?[A-Da-d]\)?)',
            lambda m: f'**{m.group(1)}**',
            text,
            count=1,
            flags=re.IGNORECASE
        )

    if category == 'preamble':
        # Drop any leading non-section, non-correct-answer lines
        lines = text.split('\n')
        start = 0
        for i, line in enumerate(lines):
            s = line.strip()
            if re.match(r'^\*\*Correct Answer', s) or re.match(r'^Correct Answer', s, re.IGNORECASE):
                start = i
                break
            if re.match(r'^\*\*(Statement Analysis|Core Concept|Key Points|Why This Question\?|Logical Elimination)', s):
                start = i
                break
        text = '\n'.join(lines[start:]).strip()

    return text


async def generate_explanation(question_text: str, options: dict, answer: str) -> str:
    options_text = "\n".join(f"({k.upper()}) {v}" for k, v in sorted(options.items()))
    prompt = (
        f"Generate a detailed UPSC Prelims explanation for this question.\n\n"
        f"**Question:**\n{question_text}\n\n"
        f"**Options:**\n{options_text}\n\n"
        f"**Correct Answer: {answer}**\n\n"
        f"Follow the system instructions exactly. Output markdown only (English only, no JSON)."
    )
    resp = await async_client.models.generate_content(
        model=MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.1,
            max_output_tokens=2000,
        ),
    )
    return resp.text.strip() if resp.text else ""


async def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT id, question_english, options_english, answer, explanation
        FROM upsc_prelims_ai_generated_que
        WHERE explanation IS NOT NULL
    """)
    rows = cur.fetchall()

    simple, plain_rows = [], []
    for row in rows:
        cat = classify(row['explanation'])
        if cat == 'ideal':
            continue
        elif cat == 'plain':
            plain_rows.append(row)
        else:
            simple.append((row, cat))

    print(f"Simple text fixes: {len(simple)}")
    print(f"Gemini regenerations needed: {len(plain_rows)}")
    print()

    # --- Simple fixes ---
    for row, cat in simple:
        fixed = text_fix(row['explanation'], cat)
        new_cat = classify(fixed)
        print(f"[{cat}] {row['id']}")
        print(f"  Before first line: {row['explanation'].strip().splitlines()[0][:80]}")
        print(f"  After  first line: {fixed.splitlines()[0][:80]}")
        print(f"  New category: {new_cat}")
        cur.execute(
            "UPDATE upsc_prelims_ai_generated_que SET explanation = %s WHERE id = %s",
            (fixed, row['id'])
        )

    conn.commit()
    print(f"\nSimple fixes committed.\n")

    # --- Gemini regenerations ---
    print(f"Regenerating {len(plain_rows)} plain-text explanations via Gemini...")
    BATCH_SIZE = 10
    total_ok, total_fail = 0, 0

    for i in range(0, len(plain_rows), BATCH_SIZE):
        batch = plain_rows[i:i + BATCH_SIZE]
        tasks = []
        for row in batch:
            opts = row['options_english']
            if isinstance(opts, str):
                opts = json.loads(opts)
            tasks.append(generate_explanation(row['question_english'], opts, row['answer']))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for row, result in zip(batch, results):
            if isinstance(result, Exception) or not result:
                print(f"  ERROR {row['id']}: {result}")
                total_fail += 1
            else:
                print(f"  OK {row['id']}: {result.splitlines()[0][:60]}")
                cur.execute(
                    "UPDATE upsc_prelims_ai_generated_que SET explanation = %s WHERE id = %s",
                    (result, row['id'])
                )
                total_ok += 1

        conn.commit()
        await asyncio.sleep(0.5)

    print(f"\nDone. Gemini: {total_ok} OK, {total_fail} failed.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
