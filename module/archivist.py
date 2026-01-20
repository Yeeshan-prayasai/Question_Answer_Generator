import os
import sys
import uuid
import json
import psycopg2
import psycopg2.extras
from typing import List, Optional
from dotenv import load_dotenv
load_dotenv()
import streamlit as st

try:
    from .models import Question
except ImportError:
    from models import Question

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)
env_path = os.path.join(root_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# DB_CONFIG = {
#     "host": st.secrets["host"],
#     "database": st.secrets["database"],
#     "user": st.secrets["user"],
#     "password": st.secrets["password"],
#     "port": st.secrets["port"]
# }

DB_CONFIG = {
    "host": os.getenv("host"),
    "database": os.getenv("database"),
    "user": os.getenv("user"),
    "password": os.getenv("password"),
    "port": os.getenv("port")
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
except Exception as e:
    print(f"Database connection error: {e}")
    conn = None
    cur = None

class ArchivistAgent:
    def __init__(self):
        pass

    def _get_connection(self):
        # Re-establish connection if closed
        global conn, cur
        if conn is None or conn.closed:
             try:
                conn = psycopg2.connect(**DB_CONFIG)
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

    def save_questions(self, questions: List[Question], test_code: str):
        conn = self._get_connection()
        if not conn: return False
        try:
            for q in questions:
                # Convert options list to dict
                opts_eng = {chr(97+i): opt for i, opt in enumerate(q.options_english)}
                opts_hin = {chr(97+i): opt for i, opt in enumerate(q.options_hindi)}

                ans = q.answer.upper() # Ensure upper

                # Check if we have a UUID already, if not generate one
                if not q.db_uuid:
                     q.db_uuid = str(uuid.uuid4())

                q_uuid = q.db_uuid

                # Use UPSERT (INSERT ON CONFLICT) logic
                cur.execute("""
                    INSERT INTO upsc_prelims_ai_generated_que (
                        id, test_code, question_number, subject, question_blueprint,
                        question_hindi, options_hindi,
                        question_english, options_english,
                        answer, quality_pass_flag, quality_feedback
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        question_number = EXCLUDED.question_number,
                        subject = EXCLUDED.subject,
                        question_blueprint = EXCLUDED.question_blueprint,
                        question_hindi = EXCLUDED.question_hindi,
                        options_hindi = EXCLUDED.options_hindi,
                        question_english = EXCLUDED.question_english,
                        options_english = EXCLUDED.options_english,
                        answer = EXCLUDED.answer,
                        quality_pass_flag = EXCLUDED.quality_pass_flag,
                        quality_feedback = EXCLUDED.quality_feedback
                """, (
                    q_uuid, test_code, q.question_number, q.subject, q.question_blueprint,
                    q.question_hindi, json.dumps(opts_hin, ensure_ascii=False),
                    q.question_english, json.dumps(opts_eng, ensure_ascii=False),
                    ans, q.is_selected, q.user_feedback
                ))
            conn.commit()
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
