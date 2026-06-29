import json
import re
import anthropic
from core.models import Symptoms, Candidate, Hypothesis

client = anthropic.Anthropic()

_SYSTEM = (
    "You are a software bug localization expert. Given a GitHub issue and candidate files "
    "from a repository, generate ranked hypotheses about which file contains the root cause.\n\n"
    "Return a JSON array of 1-3 hypotheses, each with:\n"
    "- location_file: relative path to the suspect file\n"
    "- location_function: function name if identifiable, else null\n"
    "- rationale: one sentence explaining why this location is suspect\n"
    "- predicted_evidence: what the code at this location should contain if the hypothesis is correct\n"
    "- confidence: float 0.0-1.0\n"
    "- rank: integer 1 (most likely) to 3\n\n"
    "Each hypothesis MUST point to a DIFFERENT file path — do not repeat the same file across multiple hypotheses.\n"
    "Respond with the JSON array only, wrapped in any prose you need."
)


def hypothesize(
    symptoms: Symptoms,
    candidates: list[Candidate],
    rejection_context: str | None = None,
) -> list[Hypothesis]:
    candidate_text = "\n\n".join(
        f"[{i+1}] {c.file} (BM25 score={c.score:.2f})\n{c.snippet[:300]}"
        for i, c in enumerate(candidates)
    )

    user_msg = (
        f"Issue symptoms:\n"
        f"Errors: {symptoms.error_messages}\n"
        f"Traceback frames: {[(f.file, f.function) for f in symptoms.traceback_frames]}\n"
        f"Identifiers: {symptoms.mentioned_identifiers}\n\n"
        f"Top candidate files:\n{candidate_text}"
    )
    if rejection_context:
        user_msg += f"\n\nPrevious hypotheses were rejected: {rejection_context}\nBroaden your search."

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text
    start, end = text.find("["), text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array found in hypothesizer response: {text[:200]}")
    raw = text[start:end]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Escape stray backslashes that aren't part of a valid JSON escape sequence
        raw = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
        data = json.loads(raw)
    return [Hypothesis(**h) for h in data]
