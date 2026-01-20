# UPSC Question Generator

AI-powered question generator for UPSC Prelims examination using Google Gemini.

## Features

- Generate UPSC-style MCQ questions in multiple patterns (Single Correct, Multi-Statement, Assertion-Reason, etc.)
- Automatic Hindi translation
- Quality validation and retry logic
- Test series management with PostgreSQL storage
- Export to DOCX format

## Project Structure

```
upsc_question_generator/
├── module/
│   ├── main.py          # Streamlit UI
│   ├── manager.py       # Orchestrates generation pipeline
│   ├── generator.py     # Question generation with validation
│   ├── translator.py    # English to Hindi translation
│   ├── planner.py       # Blueprint planning
│   ├── archivist.py     # Database operations
│   ├── models.py        # Pydantic models
│   ├── prompt_crafter.py
│   └── prompt_config.py
├── prompts/
│   ├── planner_guidelines.txt
│   └── default_blueprint.xlsx
├── .streamlit/
│   └── secrets.toml     # Local secrets (don't commit)
├── requirements.txt
└── README.md
```

## Question Patterns Supported

- Standard Single-Correct/Incorrect
- Multiple-Statement (2, 3, 4 statements)
- Assertion-Reason (2-stmt and 3-stmt)
- How Many Statements
- Chronological Ordering
- Geographical Sequencing

## License

Proprietary
