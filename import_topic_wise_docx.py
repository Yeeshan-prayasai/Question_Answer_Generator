"""
Import questions from exported UPSC DOCX into upsc_prelims_ai_generated_que.

Assumptions:
- DOCX format matches module/exporter.py output.
- Filename pattern carries taxonomy metadata:
  "Subject - Topic - Subtopic (...).docx"

Usage:
  uv run python import_topic_wise_docx.py \
    --file "History -  ancient - Guptas and post gupta  (1).docx" \
    --test-code "history_topic_wise_mar26" \
    --execute
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import List, Tuple

from docx import Document

from module.archivist import ArchivistAgent
from module.models import Question


OPTION_RE = re.compile(r"^\(([a-dA-D])\)\s*(.+)$")
QUESTION_LINE_RE = re.compile(r"^\d+\.\s*(.+)$")
ANSWER_RE = re.compile(r"^Answer:\s*([A-Da-d])\s*$")


def clean_filename_stem(stem: str) -> str:
    stem = re.sub(r"\(\d+\)\s*$", "", stem).strip()
    return re.sub(r"\s+", " ", stem)


def parse_subject_topic_subtopic(file_path: Path) -> Tuple[str, str, str]:
    stem = clean_filename_stem(file_path.stem)
    parts = [p.strip() for p in stem.split(" - ") if p.strip()]
    if len(parts) < 3:
        # e.g. "history- ancient history- harappan civilization.docx"
        parts = [p.strip() for p in re.split(r"\s*-\s*", stem) if p.strip()]
    if len(parts) < 3:
        raise ValueError(
            f"Could not parse subject/topic/subtopic from filename: '{file_path.name}'. "
            "Expected pattern like 'Subject - Topic - Subtopic (1).docx'."
        )
    subject = parts[0]
    topic = parts[1]
    subtopic = " - ".join(parts[2:])
    return subject, topic, subtopic


def next_non_empty(paragraphs: List[str], i: int) -> int:
    while i < len(paragraphs) and not paragraphs[i].strip():
        i += 1
    return i


def collect_options(paragraphs: List[str], i: int) -> Tuple[List[str], int]:
    options: List[str] = []
    while i < len(paragraphs):
        line = paragraphs[i].strip()
        m = OPTION_RE.match(line)
        if not m:
            break
        options.append(m.group(2).strip())
        i += 1
    return options, i


def parse_exported_docx(file_path: Path) -> List[dict]:
    doc = Document(str(file_path))
    paragraphs = [p.text for p in doc.paragraphs]

    parsed: List[dict] = []
    i = 0
    while i < len(paragraphs):
        i = next_non_empty(paragraphs, i)
        if i >= len(paragraphs):
            break

        # Stop at answer-key section
        if paragraphs[i].strip().lower() == "answer key":
            break

        # Hindi question
        m_h = QUESTION_LINE_RE.match(paragraphs[i].strip())
        if not m_h:
            i += 1
            continue
        q_h = m_h.group(1).strip()
        i += 1

        i = next_non_empty(paragraphs, i)
        opts_h, i = collect_options(paragraphs, i)
        if len(opts_h) != 4:
            raise ValueError(f"Expected 4 Hindi options near paragraph {i}, got {len(opts_h)}")

        i = next_non_empty(paragraphs, i)

        # English question
        m_e = QUESTION_LINE_RE.match(paragraphs[i].strip()) if i < len(paragraphs) else None
        if not m_e:
            raise ValueError(f"Expected English question line near paragraph {i}")
        q_e = m_e.group(1).strip()
        i += 1

        i = next_non_empty(paragraphs, i)
        opts_e, i = collect_options(paragraphs, i)
        if len(opts_e) != 4:
            raise ValueError(f"Expected 4 English options near paragraph {i}, got {len(opts_e)}")

        i = next_non_empty(paragraphs, i)
        if i >= len(paragraphs):
            raise ValueError("Unexpected end of document before answer line")
        ans_m = ANSWER_RE.match(paragraphs[i].strip())
        if not ans_m:
            raise ValueError(f"Expected 'Answer: X' near paragraph {i}, got: {paragraphs[i]!r}")
        answer = ans_m.group(1).upper()
        i += 1

        parsed.append(
            {
                "question_hindi": q_h,
                "options_hindi": opts_h,
                "question_english": q_e,
                "options_english": opts_e,
                "answer": answer,
            }
        )

    return parsed


def build_questions(
    raw: List[dict],
    subject: str,
    topic: str,
    subtopic: str,
    start_question_number: int,
) -> List[Question]:
    out: List[Question] = []
    for idx, q in enumerate(raw, start=start_question_number):
        out.append(
            Question(
                id=idx,
                question_number=idx,
                question_english=q["question_english"],
                options_english=q["options_english"],
                question_hindi=q["question_hindi"],
                options_hindi=q["options_hindi"],
                answer=q["answer"],
                subject=subject,
                topic=topic,
                subtopic=subtopic,
                test_type="Topic-wise",
                content_type="Static",
                is_selected=True,
                user_feedback="Imported from DOCX",
            )
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Import topic-wise DOCX questions into UPSC DB")
    parser.add_argument("--file", required=True, help="Path to DOCX file")
    parser.add_argument("--test-code", required=True, help="Target test_code in upsc_prelims_ai_generated_que")
    parser.add_argument(
        "--start-question-number",
        type=int,
        default=None,
        help="Start question number (default: append after max existing for test_code)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually write to DB (without this, runs as preview only)",
    )
    args = parser.parse_args()

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    subject, topic, subtopic = parse_subject_topic_subtopic(file_path)
    raw_questions = parse_exported_docx(file_path)
    if not raw_questions:
        raise ValueError("No questions parsed from DOCX.")

    archivist = ArchivistAgent()

    if args.start_question_number is not None:
        start_num = args.start_question_number
    else:
        start_num = archivist.get_max_question_number(args.test_code) + 1
        if start_num <= 0:
            start_num = 1

    questions = build_questions(raw_questions, subject, topic, subtopic, start_num)

    print("=== Import Preview ===")
    print(f"File: {file_path.name}")
    print(f"test_code: {args.test_code}")
    print(f"subject/topic/subtopic: {subject} / {topic} / {subtopic}")
    print(f"questions parsed: {len(questions)}")
    print(f"question_number range: {questions[0].question_number} - {questions[-1].question_number}")
    print(f"test_type: {questions[0].test_type}")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to insert into DB.")
        return

    ok = archivist.save_questions(questions, test_code=args.test_code, target_envs=None)
    if not ok:
        raise RuntimeError("DB insert failed via ArchivistAgent.save_questions().")
    print(f"\nInserted {len(questions)} questions successfully.")


if __name__ == "__main__":
    main()
