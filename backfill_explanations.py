"""
Backfill explanations for MCQs with missing explanations in App Prod.
- GS questions: 5-section UPSC format
- CSAT questions: Logic/Steps/Topic/Verification or Crux/Analysis/Topic
"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(__file__))

import psycopg2, psycopg2.extras
from google import genai
from google.genai import types

# ── Config ──────────────────────────────────────────────────────────────────
API_KEY = "AIzaSyBPrI4DuAYsSQInih_To1fhAXnyZ4qa3bc"
MODEL   = "gemini-2.5-flash"

PROD_DB = dict(
    host="prayas-db.cbii0i4yge4n.ap-south-1.rds.amazonaws.com",
    database="prod-prayas-db",
    user="prayas_db_user",
    password="prayas_ai_dev_2025",
    port="5432"
)

# ── Section name normaliser (reused from archivist) ──────────────────────────
_SECTION_MAP = {
    "statement analysis": "Statement Analysis",
    "option analysis": "Statement Analysis",
    "analysis of options": "Statement Analysis",
    "chronological analysis": "Statement Analysis",
    "core concept": "Core Concept",
    "calculation steps:": "Core Concept",
    "calculation steps": "Core Concept",
    "logical elimination and educated guesstimate": "Logical Elimination and Educated Guesstimate",
    "logical elimination": "Logical Elimination and Educated Guesstimate",
    "key points to remember": "Key Points to Remember",
    "key points": "Key Points to Remember",
    "why this question?": "Why This Question?",
    "why this question": "Why This Question?",
    # CSAT sections
    "logic": "Logic",
    "steps": "Steps",
    "topic": "Topic",
    "verification": "Verification",
    "crux": "Crux",
    "analysis": "Analysis",
}

def _markdown_to_sections(text: str):
    if not text:
        return None
    lines = text.split('\n')
    sections, current_section, current_lines = [], None, []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^#{1,3}\s+', stripped):
            continue
        if re.match(r'^(\*\*)?correct answer[:\s]', stripped, re.IGNORECASE):
            continue
        header_match = re.match(r'^\*\*(.*?)\*\*\s*$', stripped)
        if header_match:
            header_text = header_match.group(1).strip()
            mapped = _SECTION_MAP.get(header_text.lower())
            if mapped:
                if current_section:
                    content = '\n'.join(current_lines).strip()
                    if content:
                        sections.append({"content": content, "sectionName": current_section})
                current_section = mapped
                current_lines = []
                continue
        if current_section is not None:
            current_lines.append(line)
    if current_section:
        content = '\n'.join(current_lines).strip()
        if content:
            sections.append({"content": content, "sectionName": current_section})
    if not sections and text.strip():
        return [{"content": text.strip(), "sectionName": "Core Concept"}]
    return sections or None

# ── Prompts ──────────────────────────────────────────────────────────────────
def _gs_explanation_prompt(question_text, options, correct_answer, taxonomy, web_context=""):
    opts_str = "\n".join(f"({o['id'].upper()}) {o['text']}" for o in options)
    web_block = f"\n\n### Reference Material (from web search)\n{web_context}" if web_context else ""
    return f"""You are a UPSC exam expert. Generate a detailed explanation for the following MCQ.

**Question:**
{question_text}

**Options:**
{opts_str}

**Correct Answer:** {correct_answer.upper()}

**Topic:** {', '.join(t for t in taxonomy if t)}
{web_block}

Generate explanation with these EXACT sections (use **bold** for section names, no # headings):

**Correct Answer: {correct_answer.upper()}**

**Statement Analysis**
Analyse each statement/option — mark ✓ Correct or ✗ Incorrect with a brief reason.

**Core Concept**
3–4 sentences explaining the core concept tested. Bold key terms.

**Logical Elimination and Educated Guesstimate**
2–3 sentences on how to eliminate wrong options logically.

**Key Points to Remember**
- **Point 1:** [key fact]
- **Point 2:** [related insight]
- **Point 3:** [current relevance]

**Why This Question?**
2–3 sentences on UPSC relevance, syllabus linkage, or current affairs connection.
"""

def _csat_explanation_prompt(question_text, options, correct_answer, taxonomy):
    opts_str = "\n".join(f"({o['id'].upper()}) {o['text']}" for o in options)
    topic = ', '.join(t for t in taxonomy if t)
    # Determine type
    reasoning_topics = {'reasoning', 'math', 'algebra', 'arithmetic', 'series', 'puzzles', 'seating', 'coding', 'direction', 'blood relations', 'data interpretation', 'geometry', 'number system'}
    is_reasoning = any(any(rt in t.lower() for rt in reasoning_topics) for t in taxonomy if t)

    if is_reasoning:
        return f"""You are a CSAT exam expert. Generate a detailed explanation for the following MCQ.

**Question:**
{question_text}

**Options:**
{opts_str}

**Correct Answer:** {correct_answer.upper()}
**Topic:** {topic}

Generate explanation with these EXACT sections (use **bold** for section names):

**Correct Answer: {correct_answer.upper()}**

**Logic**
Explain the core logical/mathematical reasoning or pattern used to solve this.

**Steps**
Step-by-step working:
1. [Step 1]
2. [Step 2]
3. [Step 3]
(add more steps as needed)

**Topic**
{topic}

**Verification**
Verify the answer by checking/substituting back. Explain why other options are wrong.
"""
    else:
        # English/comprehension
        return f"""You are a CSAT exam expert. Generate a detailed explanation for the following MCQ.

**Question:**
{question_text}

**Options:**
{opts_str}

**Correct Answer:** {correct_answer.upper()}
**Topic:** {topic}

Generate explanation with these EXACT sections (use **bold** for section names):

**Correct Answer: {correct_answer.upper()}**

**Crux**
State the central idea/argument of the passage or the key logical point being tested.

**Analysis**
Analyse each option:
1. Option A — [correct/incorrect + reason]
2. Option B — [correct/incorrect + reason]
3. Option C — [correct/incorrect + reason]
4. Option D — [correct/incorrect + reason]

**Topic**
{topic}
"""

# ── Web search ────────────────────────────────────────────────────────────────
def web_search_context(client, question_text, taxonomy):
    topic = ', '.join(t for t in taxonomy if t)
    try:
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        prompt = (
            f"Research this UPSC topic for explaining an MCQ:\nTopic: {topic}\n"
            f"Question hint: {question_text[:300]}\n\n"
            f"Return only key facts, dates, data points, policy details as bullet points."
        )
        resp = client.models.generate_content(
            model=MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=2000, tools=[grounding_tool])
        )
        return resp.text or ""
    except Exception as e:
        print(f"  [WebSearch] failed: {e}")
        return ""

def needs_web_search(client, question_text, taxonomy):
    topic = ', '.join(t for t in taxonomy if t)
    try:
        prompt = (
            f"Does explaining this UPSC MCQ require recent factual context (post May 2025)?\n"
            f"Topic: {topic}\nQuestion: {question_text[:200]}\nReply ONLY: YES or NO"
        )
        resp = client.models.generate_content(
            model=MODEL, contents=[prompt],
            config=types.GenerateContentConfig(temperature=0, max_output_tokens=5)
        )
        return (resp.text or "").strip().upper().startswith("YES")
    except:
        return False

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    client = genai.Client(api_key=API_KEY)
    prod = psycopg2.connect(**PROD_DB)
    cur = prod.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Fetch all MCQs with missing explanations + their metadata
    cur.execute("""
        SELECT
            m.id as mcq_id,
            m."questionText",
            m.options,
            m."correctOptionIds",
            m.question_pattern,
            li.paper,
            array_agg(t.name ORDER BY t.level) FILTER (WHERE t.name IS NOT NULL) as taxonomy
        FROM mcqs m
        JOIN learning_items li ON li.id = m."learningItemId"
        LEFT JOIN learning_item_taxonomies lit ON lit."learningItemId" = li.id
        LEFT JOIN taxonomies t ON t.id = lit."taxonomyId"
        WHERE m.explanation IS NULL
        GROUP BY m.id, m."questionText", m.options, m."correctOptionIds", m.question_pattern, li.paper
    """)
    rows = cur.fetchall()
    print(f"MCQs to backfill: {len(rows)}")

    success, failed, skipped = 0, 0, 0

    for i, row in enumerate(rows):
        mcq_id = row['mcq_id']
        question_text = row['questionText'] or ''
        options = row['options'] or []
        correct_ids = row['correctOptionIds'] or []
        paper = row['paper'] or 'gs1'
        taxonomy = row['taxonomy'] or []

        if not question_text or not options or not correct_ids:
            print(f"[{i+1}/{len(rows)}] SKIP {mcq_id} — missing question/options/answer")
            skipped += 1
            continue

        correct_answer = correct_ids[0] if correct_ids else 'A'
        print(f"\n[{i+1}/{len(rows)}] {mcq_id} | paper={paper} | topic={taxonomy}")

        # Build prompt
        if paper == 'csat':
            prompt = _csat_explanation_prompt(question_text, options, correct_answer, taxonomy)
            web_context = ""
        else:
            # GS — check if web search needed
            do_search = needs_web_search(client, question_text, taxonomy)
            web_context = ""
            if do_search:
                print(f"  [WebSearch] fetching context...")
                web_context = web_search_context(client, question_text, taxonomy)
                print(f"  [WebSearch] got {len(web_context)} chars")
            prompt = _gs_explanation_prompt(question_text, options, correct_answer, taxonomy, web_context)

        # Generate with retries
        generated = None
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=MODEL,
                    contents=[prompt],
                    config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=4000)
                )
                raw = resp.text or ""
                sections = _markdown_to_sections(raw)
                if sections and len(sections) >= 2:
                    generated = sections
                    break
                else:
                    print(f"  Attempt {attempt+1}: only {len(sections) if sections else 0} sections, retrying...")
                    time.sleep(2)
            except Exception as e:
                print(f"  Attempt {attempt+1} error: {e}")
                time.sleep(3)

        if not generated:
            print(f"  FAILED after 3 attempts")
            failed += 1
            continue

        # Update DB
        try:
            cur.execute(
                'UPDATE mcqs SET explanation = %s::jsonb WHERE id = %s',
                (json.dumps(generated), mcq_id)
            )
            prod.commit()
            print(f"  ✅ Saved {len(generated)} sections: {[s['sectionName'] for s in generated]}")
            success += 1
        except Exception as e:
            prod.rollback()
            print(f"  DB error: {e}")
            failed += 1

        time.sleep(0.5)  # rate limit

    cur.close()
    prod.close()

    print(f"\n{'='*60}")
    print(f"DONE. Success: {success} | Failed: {failed} | Skipped: {skipped}")
    print(f"Total: {success + failed + skipped}/{len(rows)}")

if __name__ == "__main__":
    main()
