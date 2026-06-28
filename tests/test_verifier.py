import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.models import Hypothesis, Verdict
from agents.verifier import verify

BASE_HYPOTHESIS = Hypothesis(
    location_file="src/foo.py",
    location_function="bar",
    rationale="Suspect null check",
    predicted_evidence="returns None when list is empty",
    confidence=0.8,
    rank=1,
)


def _mock_response(status: str, reason: str):
    text = f'{{"status": "{status}", "reason": "{reason}"}}'
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def test_verify_confirmed(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("def bar():\n    return None\n")

    with patch("agents.verifier.client") as mock_client:
        mock_client.messages.create.return_value = _mock_response("CONFIRMED", "Found None return")
        verdict = verify(BASE_HYPOTHESIS, tmp_path)

    assert isinstance(verdict, Verdict)
    assert verdict.status == "CONFIRMED"
    assert verdict.reason == "Found None return"


def test_verify_rejected_missing_file(tmp_path):
    verdict = verify(BASE_HYPOTHESIS, tmp_path)
    assert verdict.status == "REJECTED"
    assert "not found" in verdict.reason.lower() or "does not exist" in verdict.reason.lower()


def test_verify_uses_haiku_model(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("def bar(): pass")

    with patch("agents.verifier.client") as mock_client:
        mock_client.messages.create.return_value = _mock_response("PARTIAL", "some match")
        verify(BASE_HYPOTHESIS, tmp_path)

    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs[1]["model"] == "claude-haiku-4-5-20251001"


def test_verify_passes_code_to_llm(tmp_path):
    (tmp_path / "src").mkdir()
    code = "def bar():\n    # special marker XYZZY\n    pass\n"
    (tmp_path / "src" / "foo.py").write_text(code)

    with patch("agents.verifier.client") as mock_client:
        mock_client.messages.create.return_value = _mock_response("REJECTED", "no match")
        verify(BASE_HYPOTHESIS, tmp_path)

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs[1]["messages"][0]["content"]
    assert "XYZZY" in user_msg
