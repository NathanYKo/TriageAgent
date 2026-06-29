from unittest.mock import patch, MagicMock
from core.models import Symptoms, Candidate, Hypothesis
from agents.hypothesizer import hypothesize

FAKE_RESPONSE_JSON = """
Here are my hypotheses:
[
  {
    "location_file": "django/db/models/query.py",
    "location_function": "filter",
    "rationale": "The filter method raises ValueError on invalid columns",
    "predicted_evidence": "A raise ValueError statement in the filter method",
    "confidence": 0.85,
    "rank": 1
  },
  {
    "location_file": "django/db/models/sql/compiler.py",
    "location_function": null,
    "rationale": "SQL compiler validates column names",
    "predicted_evidence": "Column validation logic raising ValueError",
    "confidence": 0.60,
    "rank": 2
  }
]
"""

def _make_mock_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def test_hypothesize_returns_list_of_hypotheses():
    symptoms = Symptoms(error_messages=["ValueError: bad"])
    candidates = [Candidate(file="django/db/models/query.py", score=3.0, snippet="def filter():")]

    with patch("agents.hypothesizer.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response(FAKE_RESPONSE_JSON)
        result = hypothesize(symptoms, candidates)

    assert len(result) == 2
    assert all(isinstance(h, Hypothesis) for h in result)


def test_hypothesize_correct_fields():
    symptoms = Symptoms()
    candidates = [Candidate(file="foo.py", score=1.0, snippet="")]

    with patch("agents.hypothesizer.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response(FAKE_RESPONSE_JSON)
        result = hypothesize(symptoms, candidates)

    assert result[0].location_file == "django/db/models/query.py"
    assert result[0].location_function == "filter"
    assert result[0].confidence == 0.85
    assert result[0].rank == 1
    assert result[1].location_function is None


def test_hypothesize_with_rejection_context():
    symptoms = Symptoms()
    candidates = [Candidate(file="foo.py", score=1.0, snippet="")]

    with patch("agents.hypothesizer.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response(FAKE_RESPONSE_JSON)
        hypothesize(symptoms, candidates, rejection_context="foo.py was wrong")

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs[1]["messages"][0]["content"]
    assert "foo.py was wrong" in user_msg


def test_hypothesize_uses_correct_model():
    symptoms = Symptoms()
    candidates = [Candidate(file="foo.py", score=1.0, snippet="")]

    with patch("agents.hypothesizer.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response(FAKE_RESPONSE_JSON)
        hypothesize(symptoms, candidates)

    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs[1]["model"] == "claude-opus-4-8"
