"""Gán type=matching + matching pairs cho câu ghép mảnh."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURATED_ID = json.loads(
    (ROOT / "data" / "matching-curated.json").read_text(encoding="utf-8")
)
CURATED_KEY = json.loads(
    (ROOT / "data" / "matching-by-key.json").read_text(encoding="utf-8")
    if (ROOT / "data" / "matching-by-key.json").exists()
    else {}
)
MATCH_HINT = re.compile(r"gh[eé]p|n[oố]i\s+m[oỗ]i|kéo.*sang|di chuy", re.I)
TERM_PAREN = re.compile(
    r"^(\d+)\s*[\.\)]\s*(.+?)\s*\(([^)]+)\)\s*$", re.I
)
TERM_SIMPLE = re.compile(r"^(\d+)\s*[\.\)]\s*(.+)$", re.I)
DEF_EMBED = re.compile(r"^(\d+)\.\s*(.+)$", re.I)


def parse_term(text: str) -> dict | None:
    t = text.strip()
    m = re.match(r"^(\d+)\s*[\.\)]\s*(.+)$", t, re.I)
    if m:
        body = m.group(2).strip()
        pm = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", body)
        if pm:
            return {
                "id": m.group(1),
                "text": f"{pm.group(1).strip()} ({pm.group(2).strip()})",
            }
        return {"id": m.group(1), "text": body}
    m = re.match(r"^(.+?)\s+(\d+)\.\s*\(([^)]+)\)", t, re.I)
    if m:
        return {"id": m.group(2), "text": f"{m.group(1).strip()} ({m.group(3)})"}
    return None


def try_parse_mixed_options(q: dict) -> dict | None:
    """Ghép từ danh sách option: dòng có (English) = thuật ngữ, còn lại = định nghĩa."""
    terms: list[dict] = []
    defs: list[dict] = []
    for o in q.get("options", []):
        raw = (o.get("text") or "").strip()
        if len(raw) < 8:
            continue
        term = parse_term(raw)
        if term and "(" in raw and len(raw) < 80:
            if term["id"] not in [t["id"] for t in terms]:
                terms.append(term)
            continue
        body = re.sub(r"^\d+\.\s*", "", raw).strip()
        if len(body) > 35:
            defs.append({"id": str(len(defs) + 1), "text": body})

    if len(terms) < 2 or len(defs) < 2:
        return None

    n = min(len(terms), len(defs))
    definitions = defs[:n]
    for i, d in enumerate(definitions):
        d["id"] = str(i + 1)
    correct_map = {definitions[i]["id"]: terms[i]["id"] for i in range(n)}

    instruction = "Ghép mỗi thuật ngữ với định nghĩa tương ứng."
    prompt = q.get("prompt", "")
    if prompt:
        instruction = prompt[:200]

    return {
        "instruction": instruction,
        "definitions": definitions,
        "terms": terms[: max(n, len(terms))],
        "correctMap": correct_map,
    }


def try_parse(q: dict) -> dict | None:
    terms = []
    for o in q.get("options", []):
        term = parse_term(o.get("text", ""))
        if term and term["id"] not in [t["id"] for t in terms]:
            terms.append(term)

    prompt = q.get("prompt", "")
    body = MATCH_HINT.sub("", prompt)
    body = re.sub(r"để trả lời[^.]*\.", "", body, flags=re.I)
    body = re.sub(r"hãy kéo[^.]*\.", "", body, flags=re.I).strip()

    numbered = re.split(r"(?=\d+\.\s)", body)
    defs = [
        re.sub(r"^\d+\.\s*", "", s).strip()
        for s in numbered
        if re.match(r"^\d+\.", s.strip()) and len(s.strip()) > 20
    ]
    if len(defs) < 2:
        defs = [
            s.strip()
            for s in re.split(r"\.\s+(?=[A-ZÀ-ỹM]|Mot |Một )", body)
            if len(s.strip()) > 30 and not MATCH_HINT.search(s)
        ]

    if len(terms) < 2 or len(defs) < 2:
        return try_parse_mixed_options(q)

    n = min(len(terms), len(defs))
    definitions = [{"id": str(i + 1), "text": defs[i]} for i in range(n)]
    correct_map = {definitions[i]["id"]: terms[i]["id"] for i in range(n)}

    instruction = "Ghép mỗi thuật ngữ với định nghĩa tương ứng."
    for o in q.get("options", []):
        if MATCH_HINT.search(o.get("text", "")):
            instruction = o["text"]
            break

    return {
        "instruction": instruction,
        "definitions": definitions,
        "terms": terms[: max(n, len(terms))],
        "correctMap": correct_map,
    }


def apply_matching(q: dict, data: dict) -> None:
    q["type"] = "matching"
    q["matching"] = data
    q["prompt"] = data.get("instruction", q.get("prompt", ""))


def enrich_file(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for q in data.get("questions", []):
        qid = q.get("id", "")
        key = f"{q.get('topic')}|{q.get('testId')}|{q.get('indexInTest')}"

        if key in CURATED_KEY:
            apply_matching(q, CURATED_KEY[key])
            count += 1
            continue

        if qid in CURATED_ID:
            apply_matching(q, CURATED_ID[qid])
            count += 1
            continue

        prompt = q.get("prompt", "")
        opts = " ".join(o.get("text", "") for o in q.get("options", []))
        if not MATCH_HINT.search(prompt) and not MATCH_HINT.search(opts):
            continue

        parsed = try_parse(q)
        if parsed and len(parsed["definitions"]) >= 2:
            apply_matching(q, parsed)
            count += 1

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return count


def main():
    for rel in (
        "data/quiz-visual/questions.json",
        "data/questions.json",
        "data/questions-merged.json",
    ):
        p = ROOT / rel
        if p.exists():
            print(f"{rel}: {enrich_file(p)} matching")


if __name__ == "__main__":
    main()
