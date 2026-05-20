"""
Đối chiếu type single/multiple với số tick xanh trên PDF.
Quy tắc: >= 2 tick xanh trên các đáp án → multiple.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "data" / "quiz-visual" / "questions.json"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else BANK
    if not path.exists():
        print("Missing:", path)
        return 1

    qs = json.loads(path.read_text(encoding="utf-8"))["questions"]
    mc = [q for q in qs if q.get("type") in ("single", "multiple")]
    multi = [q for q in mc if q["type"] == "multiple"]
    single = [q for q in mc if q["type"] == "single"]

    bad_multi_1tick = []
    bad_single_2plus = []
    for q in mc:
        correct = [o for o in q.get("options") or [] if o.get("isCorrect")]
        n = len(correct)
        key = f"{q['topic']}|{q['testId']}|{q.get('indexInTest')}"
        if q["type"] == "multiple" and n < 2:
            bad_multi_1tick.append((key, n, (q.get("prompt") or "")[:60]))
        if q["type"] == "single" and n >= 2:
            bad_single_2plus.append(
                (key, n, [o["id"] for o in correct], (q.get("prompt") or "")[:60])
            )

    print(f"Bank: {path.name}")
    print(f"  MC questions: {len(mc)} (multiple={len(multi)}, single={len(single)})")
    print(f"  Multiple với <2 tick: {len(bad_multi_1tick)}")
    for row in bad_multi_1tick[:12]:
        print(f"    {row[0]} ticks={row[1]} | {row[2]}")
    print(f"  Single với >=2 tick: {len(bad_single_2plus)}")
    for row in bad_single_2plus[:12]:
        print(f"    {row[0]} ticks={row[1]} ids={row[2]} | {row[3]}")
    if len(bad_multi_1tick) + len(bad_single_2plus) > 12:
        print("  ...")

    dist: dict[int, int] = {}
    for q in multi:
        n = sum(1 for o in q.get("options") or [] if o.get("isCorrect"))
        dist[n] = dist.get(n, 0) + 1
    print("  Phân bố số tick (multiple):", dict(sorted(dist.items())))

    return 0 if not bad_single_2plus and not bad_multi_1tick else 1


if __name__ == "__main__":
    raise SystemExit(main())
