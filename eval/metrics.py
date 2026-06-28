from core.models import RunResult


def parse_gold_files(patch: str) -> list[str]:
    files = set()
    for line in patch.split("\n"):
        if line.startswith("+++ b/"):
            path = line[6:]
            if path and path != "/dev/null":
                files.add(path)
    return list(files)


def acc_at_k(predicted: list[str], gold: list[str], k: int) -> bool:
    return any(g in predicted[:k] for g in gold)


def compute_metrics(results: list[RunResult], instances: list[dict]) -> dict:
    id_to_instance = {inst["instance_id"]: inst for inst in instances}
    total = acc1 = acc5 = 0

    for r in results:
        if r.diagnosis is None:
            continue
        inst = id_to_instance.get(r.instance_id)
        if not inst:
            continue
        gold = parse_gold_files(inst.get("patch", ""))
        if not gold:
            continue
        total += 1
        acc1 += int(acc_at_k(r.diagnosis.predicted_files, gold, 1))
        acc5 += int(acc_at_k(r.diagnosis.predicted_files, gold, 5))

    return {
        "total": total,
        "acc@1": acc1 / total if total else 0.0,
        "acc@5": acc5 / total if total else 0.0,
    }
