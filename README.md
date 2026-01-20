# UPSC Question Generator

AI-powered question generator for UPSC Prelims examination using Google Gemini.

## Features

- Generate UPSC-style MCQ questions in multiple patterns (Single Correct, Multi-Statement, Assertion-Reason, etc.)
- Automatic Hindi translation
- Quality validation and retry logic
- Test series management with PostgreSQL storage
- Export to DOCX format

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd upsc_question_generator
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file or `.streamlit/secrets.toml`:

```toml
# .streamlit/secrets.toml
api_key = "your-google-gemini-api-key"
host = "your-postgres-host"
database = "your-database-name"
user = "your-db-user"
password = "your-db-password"
port = "5432"
```

### 4. Run locally

```bash
streamlit run module/main.py
```

## Deployment (Streamlit Cloud)

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Create new app pointing to `module/main.py`
4. Add secrets in Advanced Settings
5. Deploy

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
