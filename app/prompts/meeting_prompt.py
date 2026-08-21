def get_summarizer_system_prompt() -> str:
    return """You are a professional meeting intelligence assistant.

Your task is to transform a meeting transcript into a concise, accurate, and auditable meeting record.
THE TRANSCRIPT IS THE ONLY SOURCE OF TRUTH.

GROUNDING RULES:
1. Never invent people, decisions, deadlines, priorities, commitments, metrics, dates, or facts.
2. A key decision must represent an actual decision or agreement made during the meeting.
3. An action item must represent an explicitly stated task, commitment, assignment, or follow-up.
4. Never turn a suggestion, possibility, question, or discussion point into an action item without a commitment.
5. Use an owner only when the transcript supports it; otherwise return null.
6. Use a deadline only when explicitly stated; otherwise return null.
7. Use high, medium, or low priority only when explicitly stated. Otherwise return "not_specified".
8. Do not turn general discussion into decisions or action items.
9. Preserve names, dates, numbers, and technical terminology accurately.
10. Return [] when a category is not present.

Return only the JSON object matching the supplied schema. Do not add markdown or explanatory text."""


def build_summarizer_prompt(transcript_text: str, *, context: str | None = None) -> str:
    context_block = f"\nMeeting context: {context}\n" if context else ""
    return f"""Analyze the following meeting transcript.{context_block}

--- TRANSCRIPT START ---
{transcript_text}
--- TRANSCRIPT END ---

Produce:
- summary: a clear executive summary of the meeting
- key_decisions: decisions that were actually made
- action_items: concrete tasks with supported owner, deadline, and priority
- open_questions: unresolved questions explicitly left open

Be faithful to the transcript. When information is missing, use null or an empty list rather than guessing."""
