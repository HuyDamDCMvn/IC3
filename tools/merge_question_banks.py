"""Gộp ngân hàng text + visual MinerU thành một file."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = ROOT / "data" / "questions.json"
VISUAL = ROOT / "data" / "quiz-visual" / "questions.json"
OUT = ROOT / "data" / "questions-merged.json"


def question_key(q: dict) -> str:
    return f"{q['topic']}|{q['testId']}|{q.get('indexInTest', '')}"


def main():
    merged: dict[str, dict] = {}
    for path in (TEXT, VISUAL):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for q in data.get("questions", []):
            k = question_key(q)
            # Visual (MinerU) ghi đè text khi trùng số câu
            merged[k] = q
    payload = {
        "version": 2,
        "source": "merged text + MinerU visual",
        "total": len(merged),
        "questions": list(merged.values()),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Merged {len(merged)} questions -> {OUT}")


if __name__ == "__main__":
    main()
