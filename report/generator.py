import json
from pathlib import Path
from core.models import Diagnosis


def generate_report(diagnosis: Diagnosis, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{diagnosis.instance_id}.json"
    md_path = output_dir / f"{diagnosis.instance_id}.md"

    json_path.write_text(
        json.dumps(diagnosis.model_dump(), indent=2),
        encoding="utf-8",
    )

    md_lines = [
        f"# Diagnosis: {diagnosis.instance_id}",
        "",
        f"**Predicted files:** {', '.join(diagnosis.predicted_files)}",
        f"**Confidence:** {diagnosis.confidence:.2f}",
        f"**Replanning rounds:** {diagnosis.rounds}",
        "",
        "## Root Cause",
        diagnosis.explanation,
        "",
        "## Evidence Chain",
        *[f"- {e}" for e in diagnosis.evidence_chain],
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return json_path, md_path
