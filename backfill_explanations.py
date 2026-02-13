"""
One-time script to backfill explanations for existing questions in the DB.
Run with: uv run python backfill_explanations.py
Sample run: uv run python backfill_explanations.py --sample 5

2184 questions, ~15 minutes with async batching.
"""
import os
import sys
import json
import time
import asyncio
import argparse

# Fix Windows console encoding for Unicode characters (✓, ✗, etc.)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
import psycopg2.extras
from google import genai
from google.genai import types

# Read secrets from .streamlit/secrets.toml
import tomllib
secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
with open(secrets_path, 'rb') as f:
    secrets = tomllib.load(f)

DB_CONFIG = {
    "host": secrets["host"],
    "database": secrets["database"],
    "user": secrets["user"],
    "password": secrets["password"],
    "port": secrets["port"]
}

# Gemini client
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


async def generate_explanation(question_text: str, options: dict, answer: str) -> str:
    """Generate a detailed explanation for an existing question."""
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


async def process_batch(batch, conn, cur, batch_num, total_batches, dry_run=False):
    """Process a batch of questions concurrently."""
    tasks = []
    for row in batch:
        options = row['options_english']
        if isinstance(options, str):
            options = json.loads(options)
        tasks.append(generate_explanation(row['question_english'], options, row['answer']))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    success = 0
    failed = 0
    for row, result in zip(batch, results):
        if isinstance(result, Exception):
            print(f"  ERROR for {row['id']}: {result}")
            failed += 1
        elif result:
            if dry_run:
                print(f"\n{'='*80}")
                print(f"Q: {row['question_english'][:100]}...")
                print(f"Answer: {row['answer']}")
                print(f"{'='*80}")
                print(result)
                print(f"{'='*80}\n")
            else:
                cur.execute(
                    "UPDATE upsc_prelims_ai_generated_que SET explanation = %s WHERE id = %s",
                    (result, row['id'])
                )
            success += 1
        else:
            failed += 1

    if not dry_run:
        conn.commit()
    print(f"  Batch {batch_num}/{total_batches}: {success} OK, {failed} failed")
    return success, failed


async def main():
    parser = argparse.ArgumentParser(description="Backfill explanations for UPSC questions")
    parser.add_argument('--sample', type=int, default=0,
                        help="Run on N sample rows (dry run, no DB writes)")
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Get questions without explanations
    limit_clause = f"LIMIT {args.sample}" if args.sample > 0 else ""
    cur.execute(f"""
        SELECT id, question_english, options_english, answer
        FROM upsc_prelims_ai_generated_que
        WHERE explanation IS NULL
        ORDER BY question_number
        {limit_clause}
    """)
    rows = cur.fetchall()

    total = len(rows)
    dry_run = args.sample > 0

    if dry_run:
        print(f"SAMPLE RUN: Processing {total} questions (no DB writes)")
    else:
        print(f"Found {total} questions without explanations.")

    if total == 0:
        print("Nothing to do.")
        return

    BATCH_SIZE = 15
    total_success = 0
    total_failed = 0
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    start = time.perf_counter()

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        s, f = await process_batch(batch, conn, cur, batch_num, total_batches, dry_run=dry_run)
        total_success += s
        total_failed += f
        if not dry_run:
            await asyncio.sleep(0.5)

    elapsed = time.perf_counter() - start
    print(f"\nDone in {elapsed:.1f}s! Success: {total_success}, Failed: {total_failed}, Total: {total}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
