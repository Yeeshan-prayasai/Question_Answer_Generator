import os
import sys
import uuid
import json
import psycopg2
import psycopg2.extras
from typing import List, Optional
from dotenv import load_dotenv
import streamlit as st

try:
    from .models import Question
except (ImportError, KeyError):
    from models import Question

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)
env_path = os.path.join(root_dir, '.env')
load_dotenv(env_path)

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"

def _get_upsc_db_config():
    """Get UPSC DB config from st.secrets (Community Cloud) or .env (local)."""
    def _s(key):
        try:
            return st.secrets.get(key) or os.getenv(key)
        except Exception:
            return os.getenv(key)
    return {
        "host": _s("host"),
        "database": _s("database"),
        "user": _s("user"),
        "password": _s("password"),
        "port": _s("port"),
    }

def _get_app_db_configs():
    def _s(key):
        try:
            return st.secrets.get(key) or os.getenv(key)
        except Exception:
            return os.getenv(key)
    return {
        "dev": {
            "host": _s("app_dev_DB_HOST"),
            "database": _s("app_dev_DB_NAME"),
            "user": _s("app_DB_USERNAME"),
            "password": _s("app_dev_DB_PASSWORD"),
            "port": _s("app_dev_DB_PORT"),
        },
        "prod": {
            "host": _s("app_prod_DB_HOST"),
            "database": _s("app_prod_DB_NAME"),
            "user": _s("app_prod_DB_USERNAME"),
            "password": _s("app_prod_DB_PASSWORD"),
            "port": _s("app_prod_DB_PORT"),
        },
    }

# Lazy connection — established on first use, not at import time
conn = None
cur = None

def _ensure_upsc_conn():
    """Lazily connect to UPSC DB. Returns (conn, cur) or (None, None) on failure."""
    global conn, cur
    if conn is not None:
        try:
            conn.isolation_level  # ping — raises if connection is dead
            return conn, cur
        except Exception:
            conn = None
            cur = None
    try:
        cfg = _get_upsc_db_config()
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    except Exception as e:
        print(f"Database connection error: {e}")
        conn = None
        cur = None
    return conn, cur

_SECTION_NAME_MAP = {
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
}

def _markdown_to_app_explanation(markdown_text: str):
    """Convert generator markdown explanation to app DB structured array format.

    Handles multiple format variants found in upscdev:
      1. Ideal:   **Correct Answer: D**\n\n**Statement Analysis**\n...
      2. No bold: Correct Answer: C\n\n**Statement Analysis**\n...
      3. H3 prefix: ### Explanation\n\n**Correct Answer: B**\n...
      4. Plain text: no section headers at all

    App format (array of {content, sectionName}):
        [{"content": "...", "sectionName": "Statement Analysis"}, ...]
    """
    import re

    if not markdown_text:
        return None

    lines = markdown_text.split('\n')
    sections = []
    current_section = None
    current_lines = []

    for line in lines:
        stripped = line.strip()

        # Skip markdown headings like ### Explanation / ## Explanation
        if re.match(r'^#{1,3}\s+', stripped):
            continue

        # Skip plain "Correct Answer: X" lines (with or without bold)
        plain_ca = re.match(r'^(\*\*)?correct answer[:\s]', stripped, re.IGNORECASE)
        if plain_ca:
            continue

        # Detect bold section headers like **Statement Analysis**
        header_match = re.match(r'^\*\*(.*?)\*\*\s*$', stripped)
        if header_match:
            header_text = header_match.group(1).strip()
            mapped = _SECTION_NAME_MAP.get(header_text.lower())
            if mapped:
                # Save previous section
                if current_section:
                    content = '\n'.join(current_lines).strip()
                    if content:
                        sections.append({"content": content, "sectionName": current_section})
                current_section = mapped
                current_lines = []
                continue

        # Accumulate lines for current section
        if current_section is not None:
            current_lines.append(line)

    # Save last section
    if current_section:
        content = '\n'.join(current_lines).strip()
        if content:
            sections.append({"content": content, "sectionName": current_section})

    # Fallback: plain text with no recognized sections — wrap as Core Concept
    if not sections:
        full_text = markdown_text.strip()
        if full_text:
            return [{"content": full_text, "sectionName": "Core Concept"}]
        return None

    return sections


class ArchivistAgent:
    def __init__(self):
        self._taxonomy_cache = None  # {name.lower(): uuid} built on first sync

    def _get_connection(self):
        # Re-establish connection if closed
        global conn, cur
        if conn is None or conn.closed:
             try:
                conn = psycopg2.connect(**_get_upsc_db_config())
                cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
             except Exception as e:
                 print(f"Reconnect error: {e}")
                 return None
        return conn

    def get_unique_test_codes(self) -> List[str]:
        conn = self._get_connection()
        if not conn: return []
        try:
            cur.execute("SELECT DISTINCT test_code FROM upsc_prelims_ai_generated_que WHERE test_code IS NOT NULL")
            rows = cur.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            print(f"Error fetching test codes: {e}")
            if conn and not conn.closed:
                conn.rollback()
            return []

    def check_test_code_exists(self, test_code: str) -> bool:
        conn = self._get_connection()
        if not conn: return False
        try:
            cur.execute("SELECT 1 FROM upsc_prelims_ai_generated_que WHERE test_code = %s LIMIT 1", (test_code,))
            return cur.fetchone() is not None
        except Exception as e:
            print(f"Error checking test code: {e}")
            if conn and not conn.closed:
                conn.rollback()
            return False

    def _build_taxonomy_cache(self, app_cur):
        """Build a lookup: (level, name_lower) -> taxonomy_id. Called once per sync."""
        app_cur.execute('SELECT id, name, level FROM taxonomies')
        cache = {}
        for row in app_cur.fetchall():
            cache[(row['level'], row['name'].lower())] = row['id']
        return cache

    # Planner subject names → app taxonomy level-1 names (canonical names pass through unchanged)
    _SUBJECT_NAME_MAP = {
        # Legacy planner names (backwards compat)
        "history & culture": "history",
        "polity & governance": "polity",
        "science & technology": "science & tech",
        "ca & ir": "current affairs",
        "current affairs & ir": "current affairs",
        # Canonical names (from syllabus.csv / taxonomy DB) — already correct
        "history": "history",
        "polity": "polity",
        "science & tech": "science & tech",
        "current affairs": "current affairs",
        "economy": "economy",
        "geography": "geography",
        "environment": "environment",
        "miscellaneous": "miscellaneous",
    }

    def _fuzzy_lookup(self, cache, level, name, cutoff=0.85):
        """Exact lookup first; falls back to closest difflib match above cutoff."""
        from difflib import get_close_matches
        exact = cache.get((level, name.lower()))
        if exact:
            return exact
        candidates = [k[1] for k in cache if k[0] == level]
        matches = get_close_matches(name.lower(), candidates, n=1, cutoff=cutoff)
        if matches:
            print(f"[Taxonomy] Fuzzy match: '{name}' → '{matches[0]}' (level {level})")
            return cache[(level, matches[0])]
        return None

    def _resolve_taxonomy_ids(self, cache, subject, topic, subtopic):
        """Return list of taxonomy UUIDs for subject/topic/subtopic with fuzzy fallback."""
        ids = []
        if subject:
            mapped = self._SUBJECT_NAME_MAP.get(subject.lower(), subject.lower())
            tid = self._fuzzy_lookup(cache, 1, mapped)
            if tid:
                ids.append(tid)
            else:
                print(f"[Taxonomy] No match for subject='{subject}'")
        if topic:
            tid = self._fuzzy_lookup(cache, 2, topic)
            if tid:
                ids.append(tid)
            else:
                print(f"[Taxonomy] No match for topic='{topic}'")
        if subtopic:
            tid = self._fuzzy_lookup(cache, 3, subtopic)
            if tid:
                ids.append(tid)
            else:
                print(f"[Taxonomy] No match for subtopic='{subtopic}'")
        return ids

    def get_taxonomy_names(self, env: str = 'dev') -> dict:
        """Fetch taxonomy names from app DB grouped by level. Used to seed planner."""
        cfg = _get_app_db_configs().get(env, {})
        if not cfg.get("host"):
            return {}
        try:
            app_conn = psycopg2.connect(**cfg)
            app_cur = app_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            app_cur.execute('SELECT level, name FROM taxonomies ORDER BY level, name')
            result = {1: [], 2: [], 3: []}
            for row in app_cur.fetchall():
                result[row['level']].append(row['name'])
            app_cur.close()
            app_conn.close()
            return result
        except Exception as e:
            print(f"get_taxonomy_names error: {e}")
            return {}

    def _sync_to_app_databases(self, questions: List[Question], target_envs: List[str]):
        """
        Syncs questions to the specified app environments ('dev', 'prod').
        Groups questions by question_english so multi-test-type questions
        become one MCQ with all test types merged into the tags array.
        Fails silently — main save already committed.
        """
        # Group by question_english: collect test_types and pick first UUID/metadata
        groups = {}  # question_english -> {uuid, q, test_types}
        for q in questions:
            key = q.question_english
            test_types = []
            if q.test_type:
                if isinstance(q.test_type, str):
                    test_types = [t.strip() for t in q.test_type.split(',') if t.strip()]
                elif isinstance(q.test_type, list):
                    test_types = q.test_type

            if key not in groups:
                groups[key] = {
                    "q": q,
                    "mcq_uuid": q.db_uuid or str(uuid.uuid4()),
                    "test_types": test_types,
                }
            else:
                # Merge additional test types
                for tt in test_types:
                    if tt and tt not in groups[key]["test_types"]:
                        groups[key]["test_types"].append(tt)

        for env, cfg in {k: v for k, v in _get_app_db_configs().items() if k in target_envs}.items():
            if not cfg.get("host"):
                continue
            try:
                app_conn = psycopg2.connect(**cfg)
                app_cur = app_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                tax_cache = self._build_taxonomy_cache(app_cur)

                for group in groups.values():
                    q = group["q"]
                    mcq_uuid = group["mcq_uuid"]
                    tags = [tt for tt in group["test_types"] if tt]

                    opts = [{"id": chr(97 + i), "text": opt} for i, opt in enumerate(q.options_english)]
                    correct = [q.answer.upper()]
                    explanation = _markdown_to_app_explanation(q.explanation)
                    difficulty = q.difficulty if q.difficulty is not None else 3.0

                    # Check if MCQ already exists FIRST to avoid orphaned learning_items
                    app_cur.execute(
                        'SELECT "learningItemId" FROM mcqs WHERE id = %s::uuid',
                        (mcq_uuid,)
                    )
                    existing = app_cur.fetchone()

                    if existing:
                        # Update existing learning_item and mcq — do NOT create new li_uuid
                        existing_li_id = existing["learningItemId"]
                        app_cur.execute("""
                            UPDATE learning_items SET
                                tags = %s,
                                "difficultyLevel" = %s,
                                "updatedAt" = NOW()
                            WHERE id = %s
                        """, (tags, difficulty, existing_li_id))
                        app_cur.execute("""
                            UPDATE mcqs SET
                                "questionText" = %s,
                                options = %s,
                                "correctOptionIds" = %s,
                                explanation = %s,
                                silly_mistake_prone = %s,
                                question_pattern = %s,
                                "updatedAt" = NOW()
                            WHERE id = %s::uuid
                        """, (
                            q.question_english,
                            json.dumps(opts, ensure_ascii=False),
                            correct,
                            json.dumps(explanation, ensure_ascii=False) if explanation else None,
                            q.prone_to_silly_mistakes or False,
                            q.pattern,
                            mcq_uuid,
                        ))
                        # Refresh taxonomy links (subject/topic may have changed)
                        app_cur.execute(
                            'DELETE FROM learning_item_taxonomies WHERE "learningItemId" = %s',
                            (existing_li_id,)
                        )
                        tax_ids = self._resolve_taxonomy_ids(
                            tax_cache, q.subject, q.topic, q.subtopic
                        )
                        for tax_id in tax_ids:
                            app_cur.execute("""
                                INSERT INTO learning_item_taxonomies (
                                    id, "createdAt", "updatedAt",
                                    "learningItemId", "taxonomyId"
                                ) VALUES (%s, NOW(), NOW(), %s, %s)
                                ON CONFLICT DO NOTHING
                            """, (str(uuid.uuid4()), existing_li_id, tax_id))
                    else:
                        # New question — create learning_item then MCQ
                        li_uuid = str(uuid.uuid4())
                        app_cur.execute("""
                            INSERT INTO learning_items (
                                id, "createdAt", "updatedAt", type, "difficultyLevel",
                                "estimatedTimeSeconds", "isPyq", paper, status,
                                "isVerified", "canServeIndependently", tags,
                                "createdBy", "max_marks"
                            ) VALUES (
                                %s, NOW(), NOW(), 'mcq', %s,
                                72, FALSE, 'gs1', 'published',
                                TRUE, TRUE, %s,
                                %s, 2
                            )
                        """, (li_uuid, difficulty, tags, SYSTEM_USER_ID))
                        app_cur.execute("""
                            INSERT INTO mcqs (
                                id, "createdAt", "updatedAt",
                                "questionText", options, "correctOptionIds",
                                "isMultiSelect", "learningItemId",
                                explanation, silly_mistake_prone, question_pattern
                            ) VALUES (
                                %s::uuid, NOW(), NOW(),
                                %s, %s, %s,
                                FALSE, %s,
                                %s, %s, %s
                            )
                        """, (
                            mcq_uuid,
                            q.question_english,
                            json.dumps(opts, ensure_ascii=False),
                            correct,
                            li_uuid,
                            json.dumps(explanation, ensure_ascii=False) if explanation else None,
                            q.prone_to_silly_mistakes or False,
                            q.pattern,
                        ))
                        # Insert taxonomy links
                        tax_ids = self._resolve_taxonomy_ids(
                            tax_cache, q.subject, q.topic, q.subtopic
                        )
                        for tax_id in tax_ids:
                            app_cur.execute("""
                                INSERT INTO learning_item_taxonomies (
                                    id, "createdAt", "updatedAt",
                                    "learningItemId", "taxonomyId"
                                ) VALUES (%s, NOW(), NOW(), %s, %s)
                                ON CONFLICT DO NOTHING
                            """, (str(uuid.uuid4()), li_uuid, tax_id))
                        if not tax_ids:
                            print(f"[Archivist] WARNING: No taxonomy IDs resolved for subject='{q.subject}' topic='{q.topic}' subtopic='{q.subtopic}'")

                app_conn.commit()
                app_cur.close()
                app_conn.close()
                print(f"Synced {len(groups)} questions to app_{env}")
            except Exception as e:
                print(f"App sync error ({env}): {e}")

    def save_questions(self, questions: List[Question], test_code: str, target_envs: Optional[List[str]] = None):
        conn = self._get_connection()
        if not conn: return False
        try:
            for q in questions:
                # Convert options list to dict
                opts_eng = {chr(97+i): opt for i, opt in enumerate(q.options_english)}
                opts_hin = {chr(97+i): opt for i, opt in enumerate(q.options_hindi)}

                ans = q.answer.upper() # Ensure upper

                # Parse test types (could be comma-separated string)
                test_types = []
                if q.test_type:
                    if isinstance(q.test_type, str):
                        test_types = [t.strip() for t in q.test_type.split(',') if t.strip()]
                    elif isinstance(q.test_type, list):
                        test_types = q.test_type

                # If no test types selected, save once with NULL test_type
                if not test_types:
                    test_types = [None]

                # Save question once for each test type
                # q.db_uuid is the canonical MCQ UUID used in app dev (first test_type's UUID)
                if not q.db_uuid:
                    q.db_uuid = str(uuid.uuid4())

                for test_type in test_types:
                    if len(test_types) == 1:
                        q_uuid = q.db_uuid
                    else:
                        # Each test_type row in upsc dev gets its own UUID,
                        # but q.db_uuid (already set above) is the canonical app dev MCQ UUID
                        q_uuid = str(uuid.uuid4())

                    # Use UPSERT (INSERT ON CONFLICT) logic
                    cur.execute("""
                        INSERT INTO upsc_prelims_ai_generated_que (
                            id, test_code, question_number, subject, topic, subtopic,
                            month, year, test_type,
                            prone_to_silly_mistakes, pattern, content_type,
                            difficulty, explanation,
                            question_blueprint, question_hindi, options_hindi,
                            question_english, options_english,
                            answer, quality_pass_flag, quality_feedback
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            question_number = EXCLUDED.question_number,
                            subject = EXCLUDED.subject,
                            topic = EXCLUDED.topic,
                            subtopic = EXCLUDED.subtopic,
                            month = EXCLUDED.month,
                            year = EXCLUDED.year,
                            test_type = EXCLUDED.test_type,
                            prone_to_silly_mistakes = EXCLUDED.prone_to_silly_mistakes,
                            pattern = EXCLUDED.pattern,
                            content_type = EXCLUDED.content_type,
                            difficulty = EXCLUDED.difficulty,
                            explanation = EXCLUDED.explanation,
                            question_blueprint = EXCLUDED.question_blueprint,
                            question_hindi = EXCLUDED.question_hindi,
                            options_hindi = EXCLUDED.options_hindi,
                            question_english = EXCLUDED.question_english,
                            options_english = EXCLUDED.options_english,
                            answer = EXCLUDED.answer,
                            quality_pass_flag = EXCLUDED.quality_pass_flag,
                            quality_feedback = EXCLUDED.quality_feedback
                    """, (
                        q_uuid, test_code, q.question_number, q.subject, q.topic, q.subtopic,
                        q.month, q.year, test_type,
                        q.prone_to_silly_mistakes, q.pattern, q.content_type,
                        q.difficulty, q.explanation,
                        q.question_blueprint,
                        q.question_hindi, json.dumps(opts_hin, ensure_ascii=False),
                        q.question_english, json.dumps(opts_eng, ensure_ascii=False),
                        ans, q.is_selected, q.user_feedback
                    ))
            conn.commit()
            if target_envs:
                self._sync_to_app_databases(questions, target_envs)
            return True
        except Exception as e:
            print(f"Error saving questions: {e}")
            if conn and not conn.closed:
                conn.rollback()
            return False

    def get_questions_by_test_code(self, test_code: str) -> List[dict]:
        conn = self._get_connection()
        if not conn: return []
        try:
            # Fetch ALL questions (selected and rejected) order by question_number
            cur.execute("""
                SELECT * FROM upsc_prelims_ai_generated_que
                WHERE test_code = %s
                ORDER BY question_number ASC
            """, (test_code,))
            rows = cur.fetchall()

            questions_data = []
            for row in rows:
                questions_data.append(dict(row))
            return questions_data
        except Exception as e:
            print(f"Error fetching questions: {e}")
            if conn and not conn.closed:
                conn.rollback()
            return []

    def get_max_question_number(self, test_code: str) -> int:
        conn = self._get_connection()
        if not conn: return 0
        try:
            cur.execute("SELECT MAX(question_number) FROM upsc_prelims_ai_generated_que WHERE test_code = %s", (test_code,))
            val = cur.fetchone()[0]
            return val if val is not None else 0
        except Exception as e:
            print(f"Error fetching max number: {e}")
            return 0

    def get_all_questions(self) -> List[dict]:
        """
        Fetches all questions (blueprints) that were selected (passed quality check).
        Used by Planner to avoid duplicates.
        """
        conn = self._get_connection()
        if not conn: return []
        try:
            cur.execute("""SELECT question_blueprint FROM upsc_prelims_ai_generated_que
                WHERE quality_pass_flag = TRUE""")
            rows = cur.fetchall()

            questions_data = []
            for row in rows:
                questions_data.append(dict(row))
            return questions_data
        except Exception as e:
            print(f"Error fetching all questions: {e}")
            if conn and not conn.closed:
                conn.rollback()
            return []

    def get_unique_test_types(self) -> List[str]:
        conn = self._get_connection()
        if not conn: return []
        try:
            cur.execute(
                "SELECT DISTINCT test_type FROM upsc_prelims_ai_generated_que "
                "WHERE test_type IS NOT NULL ORDER BY test_type"
            )
            return [row[0] for row in cur.fetchall()]
        except Exception as e:
            print(f"Error fetching test types: {e}")
            if conn and not conn.closed:
                conn.rollback()
            return []

    def get_questions_by_test_type(self, test_type: str) -> List[dict]:
        conn = self._get_connection()
        if not conn: return []
        try:
            cur.execute(
                "SELECT * FROM upsc_prelims_ai_generated_que "
                "WHERE test_type = %s ORDER BY question_number ASC",
                (test_type,)
            )
            return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            print(f"Error fetching questions by test_type: {e}")
            if conn and not conn.closed:
                conn.rollback()
            return []

    def get_prod_existing_combined(self, questions_map: List[dict]) -> set:
        """
        Check app prod for duplicates using a combination of question UUID and question text.
        questions_map: list of {'uuid': str, 'text': str}
        Returns a set of UUIDs (from questions_map) whose question is already in prod —
        matched if the prod MCQ id = uuid OR its questionText = text.
        """
        cfg = _get_app_db_configs().get('prod', {})
        if not cfg.get('host') or not questions_map:
            return set()
        try:
            app_conn = psycopg2.connect(**cfg)
            app_cur = app_conn.cursor()
            uuids = [q['uuid'] for q in questions_map if q.get('uuid')]
            texts = [q['text'] for q in questions_map if q.get('text')]
            # Single query: match by UUID or by question text
            app_cur.execute(
                'SELECT id::text, "questionText" FROM mcqs '
                'WHERE id = ANY(%s::uuid[]) OR "questionText" = ANY(%s)',
                (uuids, texts)
            )
            rows = app_cur.fetchall()
            app_cur.close()
            app_conn.close()

            matched_prod_ids = {str(r[0]) for r in rows}
            matched_prod_texts = {r[1] for r in rows}

            # Map back to input UUIDs
            result = set()
            for q in questions_map:
                if q.get('uuid') in matched_prod_ids or q.get('text') in matched_prod_texts:
                    result.add(q['uuid'])
            return result
        except Exception as e:
            print(f"get_prod_existing_combined error: {e}")
            return set()

    def get_app_mcq_data(self, mcq_uuid: str, env: str = 'dev', question_text: str = None) -> Optional[dict]:
        """
        Fetch MCQ + learning_item + taxonomy from app DB.
        Tries UUID first; if not found, falls back to questionText match.
        Returns dict with an extra 'matched_by' key: 'uuid' or 'text'.
        """
        cfg = _get_app_db_configs().get(env, {})
        if not cfg.get('host'):
            return None
        try:
            app_conn = psycopg2.connect(**cfg)
            app_cur = app_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # Try UUID first
            app_cur.execute("""
                SELECT m.id, m."questionText", m."correctOptionIds",
                       m.explanation, m.silly_mistake_prone, m.question_pattern,
                       m."learningItemId",
                       li.tags, li."difficultyLevel", li.status, li."isVerified"
                FROM mcqs m
                JOIN learning_items li ON li.id = m."learningItemId"
                WHERE m.id = %s::uuid
            """, (mcq_uuid,))
            row = app_cur.fetchone()

            # Fallback: search by questionText
            if not row and question_text:
                app_cur.execute("""
                    SELECT m.id, m."questionText", m."correctOptionIds",
                           m.explanation, m.silly_mistake_prone, m.question_pattern,
                           m."learningItemId",
                           li.tags, li."difficultyLevel", li.status, li."isVerified"
                    FROM mcqs m
                    JOIN learning_items li ON li.id = m."learningItemId"
                    WHERE m."questionText" = %s
                    LIMIT 1
                """, (question_text,))
                row = app_cur.fetchone()
                matched_by = 'text' if row else None
            else:
                matched_by = 'uuid' if row else None

            if not row:
                app_cur.close()
                app_conn.close()
                return None

            data = dict(row)
            data['matched_by'] = matched_by
            app_cur.execute("""
                SELECT t.name, t.level FROM learning_item_taxonomies lit
                JOIN taxonomies t ON t.id = lit."taxonomyId"
                WHERE lit."learningItemId" = %s ORDER BY t.level
            """, (data['learningItemId'],))
            data['taxonomies'] = [dict(r) for r in app_cur.fetchall()]
            app_cur.close()
            app_conn.close()
            return data
        except Exception as e:
            print(f"get_app_mcq_data({env}) error: {e}")
            return None

    def update_upsc_question(self, q_uuid: str, updates: dict) -> bool:
        """Update specific fields on an upsc dev question row by UUID."""
        conn = self._get_connection()
        if not conn:
            return False
        allowed = {
            'question_english', 'question_hindi', 'answer',
            'subject', 'topic', 'subtopic', 'test_type', 'pattern',
            'content_type', 'difficulty', 'explanation', 'prone_to_silly_mistakes',
            'month', 'year', 'quality_pass_flag', 'quality_feedback',
        }
        sets = []
        vals = []
        for k, v in updates.items():
            if k in allowed:
                sets.append(f"{k} = %s")
                vals.append(v)
        if not sets:
            return True
        vals.append(q_uuid)
        try:
            cur.execute(
                f"UPDATE upsc_prelims_ai_generated_que SET {', '.join(sets)} WHERE id = %s",
                vals
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"update_upsc_question error: {e}")
            if conn and not conn.closed:
                conn.rollback()
            return False

    def push_to_prod(self, questions: List[Question]) -> bool:
        """Push questions to app prod DB."""
        try:
            self._sync_to_app_databases(questions, ['prod'])
            return True
        except Exception as e:
            print(f"push_to_prod error: {e}")
            return False
