import re
from core.models import Symptoms, TracebackFrame

_TRACEBACK_RE = re.compile(
    r'File "([^"]+)", line (\d+), in (\w+)'
)
_ERROR_RE = re.compile(
    r'((?:\w+Error|\w+Exception|Traceback \(most recent call last\))[^\n]*)'
)
_IDENTIFIER_RE = re.compile(
    r'\b([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+)\b'
)
_REPRO_PREFIXES = ("```", ">>>", "$ ")
MAX_ERRORS = 10
MAX_IDENTIFIERS = 30


def parse_issue(title: str, body: str) -> Symptoms:
    text = f"{title}\n{body}"

    frames = [
        TracebackFrame(file=m.group(1), line=int(m.group(2)), function=m.group(3))
        for m in _TRACEBACK_RE.finditer(text)
    ]

    errors = list(dict.fromkeys(_ERROR_RE.findall(text)))[:MAX_ERRORS]
    identifiers = list(dict.fromkeys(_IDENTIFIER_RE.findall(text)))[:MAX_IDENTIFIERS]

    repro_steps = [
        s
        for line in body.split("\n")
        if (s := line.strip()).startswith(_REPRO_PREFIXES)
    ]

    return Symptoms(
        error_messages=errors,
        traceback_frames=frames,
        mentioned_identifiers=identifiers,
        repro_steps=repro_steps,
    )
