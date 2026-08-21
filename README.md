# IntelliMinutes — Meeting Summarizer Assessment

IntelliMinutes converts meeting recordings into a timestamped transcript and a structured, action-oriented meeting record.

The implementation is intentionally small enough for a take-home assessment while using production-minded boundaries: FastAPI API routes, a service layer, provider adapters, validated LLM output, SQLite persistence, background processing, retry handling, file validation, and automated tests.

## Assessment coverage

| Requirement | Implementation |
|---|---|
| Meeting audio input | FastAPI multipart upload with extension, size, and empty-file validation |
| ASR integration | Groq Whisper adapter with timestamped segments and large-file chunking |
| Backend processing | FastAPI + service layer + SQLite/SQLAlchemy |
| LLM summary | Groq structured JSON output |
| Key decisions | Explicit `key_decisions[]` field |
| Action items | Task, owner, deadline, and priority |
| Open questions | Explicit `open_questions[]` field |
| Frontend | Streamlit dashboard focused on usability rather than visual complexity |
| Repository | Clean project structure, README, tests, `.env.example` |
| Demo readiness | Upload → queued → transcribing → summarizing → completed flow |

## Architecture

```text
                    Streamlit UI
                         │
                         │ HTTP / JSON
                         ▼
                    FastAPI API
                         │
                         ▼
                  Meeting Service
                    /          \
                   /            \
                  ▼              ▼
            Whisper ASR       LLM Summarizer
                  │              │
                  │              │
                  └──────┬───────┘
                         ▼
                    SQLAlchemy
                         │
                         ▼
                      SQLite
```

### Processing lifecycle

1. The frontend uploads an audio file.
2. The API validates the title, extension, size, and empty-file condition.
3. The audio is stored using a UUID filename rather than the original filename.
4. A `pending` meeting record is created.
5. The API returns `202 Accepted` immediately.
6. A background task starts the pipeline with a **fresh database session**.
7. Whisper produces normalized timestamped transcript segments.
8. The transcript is passed to the summarizer in bounded chunks when necessary.
9. The LLM is required to return a strict JSON schema.
10. Pydantic validates the response before persistence.
11. The meeting becomes `completed`, or `failed` with a useful error message.
12. The frontend polls the meeting detail endpoint and renders the result.

For a production deployment with multiple workers, the background task can be replaced by a real queue such as Celery/RQ/Arq without changing the core service interfaces.

## Why the LLM layer is structured this way

The original implementation relied on JSON mode plus regex-style cleanup. The improved implementation uses a strict JSON Schema response format and then validates the returned object with Pydantic.

The prompt also explicitly instructs the model to:

- use the transcript as the only source of truth;
- never invent owners or deadlines;
- distinguish decisions from discussion;
- create action items only for explicit tasks or commitments;
- preserve important technical names, dates, numbers, and constraints;
- return empty lists when a category is not present.

This directly targets the assessment's **summary quality** and **prompt effectiveness** criteria.

## Transcript format

Whisper produces timestamped text segments. Speaker identity is not inferred, so transcript segments use `speaker: null` unless the transcription provider supplies a label.

## Project structure

```text
meeting_summarizer/
├── app/
│   ├── api/
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── core/
│   │   └── config.py
│   ├── database/
│   │   ├── database.py
│   │   └── models.py
│   ├── prompts/
│   │   └── meeting_prompt.py
│   └── services/
│       ├── asr/
│       │   ├── base.py
│       │   └── whisper.py
│       ├── llm/
│       │   ├── base.py
│       │   └── provider.py
│       ├── meeting_service.py
│       └── summarizer.py
├── frontend/
│   └── streamlit_app.py
├── tests/
├── data/
│   └── uploads/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── run.py
```

## Setup

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and set a Groq API key:

```text
GROQ_API_KEY=your_groq_key
ASR_PROVIDER=groq_whisper
ASR_MODEL=whisper-large-v3
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
```

Never commit `.env` or an API key to GitHub.

### 4. Run

```bash
python run.py
```

Open:

- Frontend: `http://127.0.0.1:8501`
- API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/meetings/health`

## Offline development

The test suite retains mock hooks for deterministic offline tests. Runtime configuration in `.env`
uses Groq and does not select those providers.

## Tests

Run:

```bash
pytest -q
```

The test suite covers:

- API health and upload behavior;
- file validation;
- list/detail behavior;
- retry/delete rules;
- ASR normalization;
- prompt grounding rules;
- LLM schema validation;
- long-transcript chunking;
- successful pipeline completion.

The current assessment build has **18 automated tests** and they pass offline.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/meetings/health` | Health check |
| GET | `/api/meetings` | Lightweight meeting history |
| POST | `/api/meetings` | Upload and start processing |
| GET | `/api/meetings/{id}` | Full meeting result |
| POST | `/api/meetings/{id}/retry` | Retry failed processing |
| DELETE | `/api/meetings/{id}` | Delete meeting and stored audio |

## Reference used

The provided `narendrasaraf/meeting-summarizer` repository was useful as an architectural reference, particularly for the upload → background processing → polling lifecycle, provider separation, structured outputs, and the idea of measuring transcription/summary quality. The implementation here is deliberately kept aligned with the assessment scope rather than copying that repository's larger React/Docker/provider matrix.

## Evaluation strategy

For the company assessment, the most useful evidence to demonstrate is:

1. **Transcription accuracy:** show a real meeting clip and the resulting timestamped transcript.
2. **Summary quality:** show that decisions and action items are separated from conversational noise.
3. **Prompt effectiveness:** explain the grounding rules and strict schema.
4. **Code structure:** show the provider interfaces, service layer, validation layer, database layer, and tests.

A strong demo should take one meeting from upload to final output and briefly show the API Swagger page and test result afterward.
