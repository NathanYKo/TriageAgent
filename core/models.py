from typing import Literal
from pydantic import BaseModel


class TracebackFrame(BaseModel):
    file: str
    function: str
    line: int


class Symptoms(BaseModel):
    error_messages: list[str] = []
    traceback_frames: list[TracebackFrame] = []
    mentioned_identifiers: list[str] = []
    repro_steps: list[str] = []


class Issue(BaseModel):
    instance_id: str
    repo: str
    base_commit: str
    title: str
    body: str
    symptoms: Symptoms


class Candidate(BaseModel):
    file: str
    score: float
    snippet: str


class Hypothesis(BaseModel):
    location_file: str
    location_function: str | None = None
    rationale: str
    predicted_evidence: str
    confidence: float
    rank: int


class Verdict(BaseModel):
    hypothesis: Hypothesis
    status: Literal["CONFIRMED", "PARTIAL", "REJECTED"]
    reason: str


class Diagnosis(BaseModel):
    instance_id: str
    predicted_files: list[str]
    predicted_functions: list[str]
    confidence: float
    evidence_chain: list[str]
    explanation: str
    rounds: int


class RunResult(BaseModel):
    instance_id: str
    diagnosis: Diagnosis | None = None
    error: str | None = None
    cost_usd: float = 0.0
    latency_s: float = 0.0
