"""
Kiểm tra snapshot vs câu hỏi: trang PDF, chiều cao vùng crop, thiếu đề/ảnh.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "data" / "quiz-visual" / "questions.json"
OUT = ROOT / "data" / "snapshot-audit.json"

Q_IN_PROMPT = re.compile(r"question\s*(\d+)", re.I)
HINH_ANH = re.compile(r"hinh\s*anh|anh\s*minh", re.I)
MATCH_HINT = re.compile(r"gh[eé]p|kéo.*sang|di chuy", re.I)
YESNO_HINT = re.compile(r"chon\s*co|chon\s*dung|phat\s*bieu", re.I)


def audit(q: dict) -> list[str]:
    issues: list[str] = []
    prompt = (q.get("prompt") or "").strip()
    n = len(q.get("options") or [])
    qn = Q_IN_PROMPT.search(prompt)
    idx = q.get("indexInTest")

    if not prompt:
        issues.append("missing_prompt")
    if n == 0 and q.get("type") not in ("matching",):
        issues.append("no_options")

    # Gợi ý loại vs đề
    if HINH_ANH.search(prompt) and q.get("type") != "multiple":
        if n >= 2 and not any(o.get("isCorrect") for o in q.get("options", [])):
            pass
    if YESNO_HINT.search(prompt.lower()) and q.get("type") != "yesno":
        issues.append("likely_yesno_wrong_type")
    if MATCH_HINT.search(prompt) and q.get("type") != "matching":
        issues.append("likely_matching_wrong_type")

    if qn and idx and int(qn.group(1)) != int(idx):
        issues.append(f"prompt_qnum_{qn.group(1)}_vs_index_{idx}")

    if not q.get("snapshotUrl"):
        issues.append("no_snapshot")
    return issues


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else BANK
    data = json.loads(path.read_text(encoding="utf-8"))
    flagged = []
    for q in data.get("questions", []):
        issues = audit(q)
        if issues:
            flagged.append(
                {
                    "key": f"{q['topic']}|{q['testId']}|{q.get('indexInTest')}",
                    "type": q.get("type"),
                    "page": q.get("page"),
                    "prompt": (q.get("prompt") or "")[:100],
                    "snapshot": q.get("snapshotUrl"),
                    "issues": issues,
                }
            )
    OUT.write_text(json.dumps(flagged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Snapshot audit: {len(data.get('questions', []))} câu, {len(flagged)} gợi ý xem -> {OUT}")
    from collections import Counter

    c = Counter(i for x in flagged for i in x["issues"])
    for k, v in c.most_common():
        print(f"  [{v:3d}] {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
