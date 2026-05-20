"""
Rà soát ngân hàng câu theo quy tắc IC3 (gom 1 Question = 1 câu, yesno, chọn 2, đáp án).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_PATH = ROOT / "data" / "quiz-visual" / "questions.json"
MERGED_PATH = ROOT / "data" / "questions-merged.json"

CHON2_RE = re.compile(r"ch[oơ]n\s*2|\(ch[oơ]n\s*2\)", re.I)
CHON3_RE = re.compile(r"ch[oơ]n\s*3|\(ch[oơ]n\s*3\)", re.I)
YESNO_CO = re.compile(
    r"ch[oơ]n\s*c[oó]|c[oó]\s+n[eê]u.*d[uú]ng|kh[oô]ng\s+n[eê]u.*sai|"
    r"cho\s+m[oỗ]i\s|chon\s+co\s+hoac",
    re.I,
)
YESNO_DUNG = re.compile(
    r"ch[oơ]n\s*[dđ][uú]ng|[dđ][uú]ng\s+n[eê]u|[dđ][uú]ng\s+ho[aă]c\s*sai|"
    r"sai\s+n[eê]u.*[dđ][uú]ng|dung.*sai",
    re.I,
)
YESNO_FACT = re.compile(
    r"th[uự]c\s*t|thyc\s*t|ý\s*ki|y\s*ki",
    re.I,
)
ONLY_LABEL = re.compile(
    r"^(c[oó]|kh[oô]ng|d[uú]ng|sai|th[uự]c\s*t|ý\s*ki|co|khong|dung)$",
    re.I,
)
Q_MARKER = re.compile(r"Question\s*\d+", re.I)


def is_yesno_prompt(prompt: str) -> bool:
    if YESNO_CO.search(prompt) or YESNO_DUNG.search(prompt):
        return True
    return bool(
        re.search(r"ch[oơ]n|hay\s+chon", prompt, re.I)
        and YESNO_FACT.search(prompt)
        and re.search(r"th[uự]c|thyc", prompt, re.I)
        and re.search(r"ki[eế]n|opinion", prompt, re.I)
    )


def audit_question(q: dict) -> list[str]:
    issues: list[str] = []
    prompt = (q.get("prompt") or "").strip()
    qtype = q.get("type", "single")
    opts = q.get("options") or []
    correct = [o for o in opts if o.get("isCorrect")]

    if not prompt:
        issues.append("missing_prompt")
    if Q_MARKER.search(prompt):
        issues.append("prompt_has_question_marker")

    if qtype == "matching":
        if not q.get("matching"):
            issues.append("matching_no_data")
        return issues

    if qtype == "yesno" or q.get("yesNoMode"):
        if len(opts) < 1:
            issues.append("yesno_no_statements")
        for o in opts:
            t = (o.get("text") or "").strip()
            if len(t) < 6:
                issues.append("yesno_short_statement")
                break
            if ONLY_LABEL.match(t):
                issues.append("yesno_label_as_statement")
                break
        if prompt and not is_yesno_prompt(prompt) and not q.get("yesNoMode"):
            issues.append("yesno_prompt_mismatch")
        return issues

    # Có thể phải là yesno nhưng đang là single/multiple
    if is_yesno_prompt(prompt) and qtype != "yesno":
        issues.append("should_be_yesno")

    if len(opts) == 0:
        issues.append("no_options")
        return issues

    if qtype in ("single", "multiple") and len(opts) < 2:
        issues.append("too_few_options")

    if len(correct) == 0:
        issues.append("no_correct_answer")

    if CHON2_RE.search(prompt):
        if qtype != "multiple":
            issues.append("chon2_not_multiple")
        elif len(correct) != 2:
            issues.append(f"chon2_wrong_count_{len(correct)}")
    elif CHON3_RE.search(prompt):
        if qtype != "multiple":
            issues.append("chon3_not_multiple")
        elif len(correct) != 3:
            issues.append(f"chon3_wrong_count_{len(correct)}")

    # Đáp án chỉ là nhãn dropdown (gom sai)
    label_opts = sum(1 for o in opts if ONLY_LABEL.match((o.get("text") or "").strip()))
    if label_opts >= 2 and is_yesno_prompt(prompt):
        issues.append("yesno_split_as_mc")

    return issues


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else BANK_PATH
    if not path.exists():
        print("Missing:", path)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    by_issue: dict[str, list[dict]] = {}
    flagged: list[dict] = []

    for q in questions:
        issues = audit_question(q)
        if not issues:
            continue
        flagged.append({**q, "_issues": issues})
        for iss in issues:
            by_issue.setdefault(iss, []).append(q)

    print(f"Audit: {path.name} — {len(questions)} câu, {len(flagged)} cần xem ({len(by_issue)} loại lỗi)\n")

    for iss, qs in sorted(by_issue.items(), key=lambda x: -len(x[1])):
        print(f"  [{len(qs):3d}] {iss}")

    report = ROOT / "data" / "audit-report.json"
    slim = [
        {
            "key": f"{q['topic']}|{q['testId']}|{q.get('indexInTest')}",
            "id": q["id"],
            "type": q.get("type"),
            "yesNoMode": q.get("yesNoMode"),
            "prompt": (q.get("prompt") or "")[:120],
            "options": len(q.get("options") or []),
            "correct": sum(1 for o in q.get("options") or [] if o.get("isCorrect")),
            "issues": q["_issues"],
        }
        for q in flagged
    ]
    report.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nChi tiết -> {report}")
    return 0 if len(flagged) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
