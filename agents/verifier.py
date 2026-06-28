import json
from pathlib import Path
import anthropic
from core.models import Hypothesis, Verdict

client = anthropic.Anthropic()


def verify(hypothesis: Hypothesis, repo_dir: Path) -> Verdict:
    code_path = repo_dir / hypothesis.location_file
    if not code_path.exists():
        return Verdict(
            hypothesis=hypothesis,
            status="REJECTED",
            reason=f"File {hypothesis.location_file} does not exist in repo",
        )

    code = code_path.read_text(encoding="utf-8", errors="ignore")[:4000]

    prompt = (
        f"Does the code at {hypothesis.location_file} confirm this hypothesis?\n\n"
        f"Hypothesis: {hypothesis.rationale}\n"
        f"Expected evidence: {hypothesis.predicted_evidence}\n\n"
        f"Code snippet:\n{code}\n\n"
        f'Reply with JSON only: {{"status": "CONFIRMED"|"PARTIAL"|"REJECTED", "reason": "one sentence"}}'
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text
    start, end = text.find("{"), text.rfind("}") + 1
    data = json.loads(text[start:end])
    return Verdict(
        hypothesis=hypothesis,
        status=data["status"],
        reason=data["reason"],
    )
