"""Gộp đáp án từ questions.json (text) sang curated-answers cho câu visual thiếu tick."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIS = ROOT / "data" / "quiz-visual" / "questions.json"
TEXT = ROOT / "data" / "questions.json"
CURATED = ROOT / "data" / "curated-answers.json"


def key(q: dict) -> str:
    return f"{q['topic']}|{q['testId']}|{q.get('indexInTest')}"


def main() -> int:
    vis = json.loads(VIS.read_text(encoding="utf-8"))["questions"]
    text_map: dict[str, dict] = {}
    if TEXT.exists():
        for q in json.loads(TEXT.read_text(encoding="utf-8")).get("questions", []):
            text_map[key(q)] = q

    curated = (
        json.loads(CURATED.read_text(encoding="utf-8"))
        if CURATED.exists()
        else {}
    )
    added = 0
    for q in vis:
        k = key(q)
        if k in curated:
            continue
        if q.get("type") in ("matching", "yesno"):
            continue
        if any(o.get("isCorrect") for o in q.get("options", [])):
            continue
        src = text_map.get(k)
        if not src:
            continue
        correct = [o["id"] for o in src.get("options", []) if o.get("isCorrect")]
        if not correct:
            continue
        curated[k] = {
            "type": q.get("type", src.get("type", "single")),
            "correct": correct,
            "prompt": src.get("prompt") or q.get("prompt"),
            "options": [
                {
                    "id": o["id"],
                    "text": o.get("text", ""),
                    "correct": o.get("isCorrect", False),
                }
                for o in src.get("options", [])
            ],
        }
        added += 1

    CURATED.write_text(
        json.dumps(curated, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Added {added} curated keys -> {CURATED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
