import os
import time
from datetime import datetime

import requests
import streamlit as st

st.set_page_config(
    page_title="IntelliMinutes",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")

st.markdown(
    """
<style>
:root { --ink:#172033; --muted:#667085; --line:#e7eaf0; --surface:#ffffff; --soft:#f7f8fb; }
.block-container { max-width: 1240px; padding-top: 2rem; padding-bottom: 3rem; }
.hero { padding: 1.8rem 0 1.2rem; }
.hero h1 { font-size: 2.7rem; letter-spacing:-0.04em; margin:0; color:var(--ink); }
.hero p { color:var(--muted); font-size:1.05rem; margin-top:.45rem; }
.card { background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:1.15rem 1.25rem; margin-bottom:1rem; }
.metric { background:var(--soft); border:1px solid var(--line); border-radius:14px; padding:1rem; }
.metric .label { color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.06em; }
.metric .value { color:var(--ink); font-size:1.25rem; font-weight:700; margin-top:.2rem; }
.status { display:inline-block; border-radius:999px; padding:.25rem .65rem; font-size:.75rem; font-weight:700; }
.status-completed { background:#eaf8ef; color:#19713a; }
.status-processing { background:#eef4ff; color:#2457a6; }
.status-failed { background:#fff0f0; color:#a33a3a; }
.status-pending { background:#f1f3f6; color:#667085; }
.decision { padding:.75rem .9rem; border-left:3px solid #6b7280; background:var(--soft); border-radius:0 10px 10px 0; margin:.55rem 0; }
.action { border:1px solid var(--line); border-radius:12px; padding:.85rem; margin:.55rem 0; background:#fff; }
.transcript { border-bottom:1px solid var(--line); padding:.75rem 0; }
.speaker { font-weight:700; color:var(--ink); }
.time { color:var(--muted); font-size:.78rem; margin-left:.5rem; }
.small { color:var(--muted); font-size:.86rem; }
</style>
""",
    unsafe_allow_html=True,
)


def api_request(method: str, endpoint: str, **kwargs):
    try:
        response = requests.request(method, f"{API_BASE_URL}/{endpoint.lstrip('/')}", timeout=30, **kwargs)
        return response
    except requests.RequestException as exc:
        st.error(f"Backend unavailable: {exc}")
        return None


def format_duration(seconds):
    if seconds is None:
        return "—"
    seconds = int(seconds)
    return f"{seconds // 60}m {seconds % 60:02d}s"


def status_html(status: str):
    css = "status-processing" if status in {"pending", "transcribing", "summarizing"} else f"status-{status}"
    return f'<span class="status {css}">{status.replace("_", " ").upper()}</span>'


with st.sidebar:
    st.markdown("### 🎙️ IntelliMinutes")
    st.caption("Turn meeting audio into decisions and executable next steps.")
    st.divider()

    st.markdown("#### New meeting")
    title = st.text_input("Meeting title", value=f"Meeting — {datetime.now():%b %d, %Y}")
    audio = st.file_uploader("Upload audio", type=["wav", "mp3", "m4a", "ogg", "flac", "webm", "mp4"])

    if st.button("Process meeting", type="primary", use_container_width=True):
        if not audio:
            st.warning("Choose an audio file first.")
        else:
            with st.spinner("Uploading meeting…"):
                response = api_request(
                    "POST",
                    "/meetings",
                    files={"file": (audio.name, audio.getvalue(), audio.type or "application/octet-stream")},
                    data={"title": title},
                )
            if response and response.status_code == 202:
                st.success("Meeting accepted. Processing has started.")
                st.rerun()
            elif response:
                try:
                    st.error(response.json().get("detail", "Upload failed."))
                except ValueError:
                    st.error("Upload failed.")

    st.divider()
    st.markdown("#### Saved meetings")
    list_response = api_request("GET", "/meetings")
    meetings = list_response.json() if list_response and list_response.ok else []

    if meetings:
        labels = {m["id"]: f'{m["title"]} · {m["status"]}' for m in meetings}
        selected_id = st.selectbox("Select meeting", list(labels), format_func=lambda x: labels[x])
    else:
        selected_id = None
        st.caption("No meetings yet. Upload your first recording above.")

    if st.button("Refresh", use_container_width=True):
        st.rerun()


if selected_id is None:
    st.markdown('<div class="hero"><h1>Meeting intelligence, without the busywork.</h1><p>Upload a recording and get a grounded summary, decisions, action items, and unresolved questions.</p></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    for col, title, body in [
        (c1, "🎙️ Accurate transcript", "Timestamped transcript segments from Whisper."),
        (c2, "🧠 Decision-focused", "Structured LLM output instead of an unstructured wall of text."),
        (c3, "✅ Actionable", "Owners, deadlines, priorities, and open questions in one view."),
    ]:
        with col:
            st.markdown(f'<div class="card"><h3>{title}</h3><p class="small">{body}</p></div>', unsafe_allow_html=True)
    st.info("Use the upload panel in the sidebar to start.")
    st.stop()


detail_response = api_request("GET", f"/meetings/{selected_id}")
if not detail_response or not detail_response.ok:
    st.error("Could not load this meeting.")
    st.stop()

meeting = detail_response.json()
status = meeting["status"]

st.markdown(
    f'<div class="hero"><h1>{meeting["title"]}</h1><p>{meeting["date"]} · {format_duration(meeting.get("duration"))} · {status_html(status)}</p></div>',
    unsafe_allow_html=True,
)

if status in {"pending", "transcribing", "summarizing"}:
    stage = {"pending": "Queued", "transcribing": "Transcribing audio", "summarizing": "Generating meeting insights"}[status]
    st.info(f"**{stage}** — this page will refresh automatically.")
    progress = {"pending": 15, "transcribing": 55, "summarizing": 82}[status]
    st.progress(progress)
    time.sleep(2.5)
    st.rerun()

if status == "failed":
    st.error(f"Processing failed: {meeting.get('error_message') or 'Unknown error'}")
    if st.button("Retry processing", type="primary"):
        response = api_request("POST", f"/meetings/{selected_id}/retry")
        if response and response.status_code == 202:
            st.rerun()
        elif response:
            st.error(response.json().get("detail", "Retry failed."))

if status == "completed":
    result = meeting.get("result") or {}
    actions = result.get("action_items", [])
    decisions = result.get("key_decisions", [])
    questions = result.get("open_questions", [])

    c1, c2, c3, c4 = st.columns(4)
    metrics = [
        (c1, "Duration", format_duration(meeting.get("duration"))),
        (c2, "Decisions", str(len(decisions))),
        (c3, "Action items", str(len(actions))),
        (c4, "Questions", str(len(questions))),
    ]
    for col, label, value in metrics:
        with col:
            st.markdown(f'<div class="metric"><div class="label">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)

    st.write("")
    summary_tab, actions_tab, transcript_tab = st.tabs(["Executive view", "Action items", "Transcript"])

    with summary_tab:
        st.markdown("### Executive summary")
        st.markdown(result.get("summary", "No summary available."))
        st.markdown("### Key decisions")
        if decisions:
            for decision in decisions:
                st.markdown(
                    f'<div class="decision">{decision.get("description", "")}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No explicit decisions were identified.")
        st.markdown("### Open questions")
        if questions:
            for question in questions:
                st.markdown(f"- {question.get('question', '')}")
        else:
            st.caption("No unresolved questions were identified.")

        st.download_button(
            "Download meeting summary",
            data=meeting.get("summary_markdown") or "",
            file_name=f"meeting_{meeting['id']}_summary.md",
            mime="text/markdown",
        )

    with actions_tab:
        if actions:
            for action in actions:
                priority = str(action.get("priority", "not_specified")).replace("_", " ").title()
                st.markdown(
                    f'<div class="action"><strong>{action.get("task", "")}</strong><br>'
                    f'<span class="small">Owner: {action.get("owner") or "Unassigned"} · '
                    f'Deadline: {action.get("deadline") or "Not specified"} · Priority: {priority}</span></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No action items were identified.")

    with transcript_tab:
        transcript = meeting.get("transcript_json") or []
        search = st.text_input("Search transcript", placeholder="e.g. deployment, deadline, API")
        if search:
            transcript = [s for s in transcript if search.lower() in str(s.get("text", "")).lower()]
        for segment in transcript:
            start = float(segment.get("start") or 0)
            timestamp = f"{int(start // 60):02d}:{int(start % 60):02d}"
            speaker = segment.get("speaker") or "Speaker"
            st.markdown(
                f'<div class="transcript"><span class="speaker">{speaker}</span>'
                f'<span class="time">{timestamp}</span><br>{segment.get("text", "")}</div>',
                unsafe_allow_html=True,
            )

        raw_text = "\n".join(
            f"{s.get('speaker') or 'Speaker'}: {s.get('text', '')}" for s in meeting.get("transcript_json") or []
        )
        st.download_button("Download transcript", raw_text, file_name=f"meeting_{meeting['id']}_transcript.txt")

    st.divider()
    if meeting.get("asr_seconds") is not None or meeting.get("summary_seconds") is not None:
        st.caption(
            f"Pipeline timing · transcription: {meeting.get('asr_seconds') or 0:.2f}s · "
            f"summarization: {meeting.get('summary_seconds') or 0:.2f}s"
        )

st.divider()
if st.button("Delete meeting", type="secondary"):
    response = api_request("DELETE", f"/meetings/{selected_id}")
    if response and response.ok:
        st.success("Meeting deleted.")
        time.sleep(0.5)
        st.rerun()
    elif response:
        st.warning(response.json().get("detail", "Could not delete meeting."))
