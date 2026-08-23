# IntelliMinutes — Meeting Summarizer Assessment

> [!NOTE]
> 🎬 **Demo**: [Watch the IntelliMinutes Demo Video](https://drive.google.com/file/d/1kR-J3v_9d5w_BHVmxh1y0qCojImf01Ct/view?usp=drive_link)

IntelliMinutes converts meeting recordings into a timestamped transcript and a structured, action-oriented meeting record.

The implementation is intentionally small enough for a take-home assessment while using production-minded boundaries: FastAPI API routes, a service layer, provider adapters, validated LLM output, SQLite persistence, background processing, retry handling, file validation, and automated tests.

---

## 📋 Assessment Coverage

| Requirement | Implementation |
| :--- | :--- |
| **Meeting Audio Input** | FastAPI multipart upload with extension, size, and empty-file validation |
| **ASR Integration** | Groq Whisper adapter with timestamped segments and large-file chunking |
| **Backend Processing** | FastAPI + service layer + SQLite/SQLAlchemy |
| **LLM Summary** | Groq structured JSON output |
| **Key Decisions** | Explicit `key_decisions[]` field |
| **Action Items** | Task, owner, deadline, and priority |
| **Open Questions** | Explicit `open_questions[]` field |
| **Frontend** | Streamlit dashboard focused on usability rather than visual complexity |
| **Repository** | Clean project structure, README, tests, `.env.example` |
| **Demo Readiness** | Upload → queued → transcribing → summarizing → completed flow |

---

## 🏗️ Architecture

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

### Processing Lifecycle

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

> [!TIP]
> For a production deployment with multiple workers, the background task can be replaced by a real queue such as Celery/RQ/Arq without changing the core service interfaces.

---

## 🧠 LLM Integration & Prompt Grounding

The original implementation relied on JSON mode plus regex-style cleanup. The improved implementation uses a strict JSON Schema response format and then validates the returned object with Pydantic.

The prompt also explicitly instructs the model to:
* Use the transcript as the only source of truth;
* Never invent owners or deadlines;
* Distinguish decisions from discussion;
* Create action items only for explicit tasks or commitments;
* Preserve important technical names, dates, numbers, and constraints;
* Return empty lists when a category is not present.

This directly targets the assessment's **summary quality** and **prompt effectiveness** criteria.

### Transcript Format & Diarization
Whisper produces timestamped text segments. Speaker diarization is outside the scope of this build, so transcripts contain only `start`, `end`, and `text` fields.

---

## 📂 Project Structure

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

---

## ⚙️ Setup & Installation

### 1. Create a Virtual Environment

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Copy `.env.example` to `.env` and set a Groq API key:
```text
GROQ_API_KEY=your_groq_key
ASR_PROVIDER=groq_whisper
ASR_MODEL=whisper-large-v3
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
```

> [!WARNING]
> Never commit `.env` or an API key to GitHub or public source control.

### 4. Run Application
```bash
python run.py
```

* **Streamlit Frontend:** `http://127.0.0.1:8501`
* **API Documentation (Swagger):** `http://127.0.0.1:8000/docs`
* **API Health Check:** `http://127.0.0.1:8000/api/meetings/health`

---

## ⚡ Tests & Performance Matrix

```bash
pytest -v
```

<!-- METRICS_START -->
### Mathematical Performance Metrics

* **Passed Test Cases ($N_\text{passed}$):**
  $$N_\text{passed} = 24$$

* **Total Test Cases ($N_\text{total}$):**
  $$N_\text{total} = 24$$

* **Pass Rate ($P_\text{rate}$):**
  $$P_\text{rate} = \frac{N_\text{passed}}{N_\text{total}} \times 100\% = \frac{24}{24} \times 100\% = 100.0\%$$

* **Total Execution Time ($T_\text{total}$):**
  $$T_\text{total} = 2.08\text{ seconds}$$

* **Average Time per Test Case ($T_\text{avg}$):**
  $$T_\text{avg} = \frac{T_\text{total}}{N_\text{total}} = \frac{2.08\text{ s}}{24} \approx 0.09\text{ seconds / test}$$

* **Failure Rate ($F_\text{rate}$):**
  $$F_\text{rate} = \frac{N_\text{total} - N_\text{passed}}{N_\text{total}} \times 100\% = \frac{24 - 24}{24} \times 100\% = 0.0\%$$
<!-- METRICS_END -->

### Detailed Performance & Test Matrix

| Component | Test File | Test Case Name | Objective / Coverage | Status |
| :--- | :--- | :--- | :--- | :--- |
| **API Endpoints** | [test_api.py](file:///d:/meeting_summarizer/tests/test_api.py) | `test_health` | Verifies FastAPI health check endpoint returns 200 OK | `PASSED` |
| | | `test_list_is_lightweight` | Confirms list endpoint excludes large transcript JSON fields | `PASSED` |
| | | `test_upload_returns_202_and_schedules_processing` | Validates immediate response on upload & schedules pipeline | `PASSED` |
| | | `test_invalid_extension_rejected` | Checks that invalid audio extensions are rejected with 400 | `PASSED` |
| | | `test_get_missing_meeting` | Validates 404 response for non-existent meeting IDs | `PASSED` |
| | | `test_delete_processing_meeting_is_blocked` | Blocks deletion of active processing tasks with 409 | `PASSED` |
| | | `test_retry_requires_existing_audio` | Blocks retry requests if source audio file is deleted | `PASSED` |
| **ASR Service** | [test_asr.py](file:///d:/meeting_summarizer/tests/test_asr.py) | `test_mock_asr_returns_plain_transcript_segments` | Tests Whisper adapter transcription formatting | `PASSED` |
| | | `test_api_segments_are_normalized` | Ensures Whisper segments align to standardized format | `PASSED` |
| **Prompt Rules** | [test_prompts.py](file:///d:/meeting_summarizer/tests/test_prompts.py) | `test_prompt_has_grounding_rules` | Asserts key LLM grounding keywords are present in system prompt | `PASSED` |
| **Validation Schemas** | [test_schemas.py](file:///d:/meeting_summarizer/tests/test_schemas.py) | `test_action_item_defaults` | Checks default fields (unassigned, low priority) for new actions | `PASSED` |
| | | `test_action_item_rejects_empty_task` | Blocks action items containing empty task description | `PASSED` |
| | | `test_meeting_result_validation` | Validates compliance with Pydantic output schemas | `PASSED` |
| | | `test_invalid_priority_rejected` | Rejects action items with invalid priority levels | `PASSED` |
| **Pipeline Service** | [test_service.py](file:///d:/meeting_summarizer/tests/test_service.py) | `test_pipeline_marks_completed` | Validates full pipeline transitions state from pending to completed | `PASSED` |
| **Summarizer Logic** | [test_summarizer.py](file:///d:/meeting_summarizer/tests/test_summarizer.py) | `test_summarizer_returns_validated_result` | Verifies end-to-end summarizer output formatting and mapping | `PASSED` |
| | | `test_empty_transcript_is_rejected` | Rejects empty transcripts with proper error handling | `PASSED` |
| | | `test_groq_provider_falls_back_to_prompt_json_after_json_object_failure` | Tests LLM json mode fallback when schema verification fails | `PASSED` |
| | | `test_response_normalizes_missing_action_fields_and_ignores_casual_questions` | Sanitizes LLM outputs, cleans missing fields, filters noise | `PASSED` |
| | | `test_long_transcript_is_chunked` | Asserts chunking behavior works properly under character limits | `PASSED` |
| **JSON Validation** | [test_validation.py](file:///d:/meeting_summarizer/tests/test_validation.py) | `test_parse_clean_json` | Standard JSON parser test | `PASSED` |
| | | `test_parse_json_with_markdown_blocks` | Extracts JSON from inside markdown block annotations | `PASSED` |
| | | `test_parse_json_with_surrounding_text_noise` | Parses JSON when prefixed/suffixed with LLM intro chat text | `PASSED` |
| | | `test_parse_malformed_json_raises_value_error` | Throws appropriate error on syntax-broken JSON strings | `PASSED` |

---

## 📡 API Endpoints

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| **GET** | `/api/meetings/health` | Health check |
| **GET** | `/api/meetings` | Lightweight meeting history (excludes large transcript segments) |
| **POST** | `/api/meetings` | Upload audio file and start async summarization pipeline |
| **GET** | `/api/meetings/{id}` | Retrieve full meeting details, transcript, and summary output |
| **POST** | `/api/meetings/{id}/retry` | Retry failed processing steps for a specific meeting |
| **DELETE** | `/api/meetings/{id}` | Delete meeting records and stored audio file from disk |

