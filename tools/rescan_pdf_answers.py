"""
Quét lại tick xanh trên PDF (zoom 3x) cho câu chưa có đáp án → curated-answers.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "ic3-answer-detect"))
from detector import green_check_centroids  # noqa: E402


def detect_correct_on_crop(crop: np.ndarray, n: int) -> list[int]:
    if n <= 0:
        return []
    greens = green_check_centroids(crop)
    if not greens:
        return []
    h = crop.shape[0]
    band = h / n
    correct = []
    for i in range(n):
        mid = (i + 0.5) * band
        for gy, _ in greens:
            if abs(gy - mid) < band * 0.55:
                correct.append(i)
                break
    return correct

PDF = ROOT / "data" / "ic3_unlocked.pdf"
BANK = ROOT / "data" / "quiz-visual" / "questions.json"
CURATED = ROOT / "data" / "curated-answers.json"
OCR = ROOT / "data" / "mineru_out_full" / "ic3_unlocked" / "ocr"
CL = OCR / "ic3_unlocked_content_list.json"

Q_RE = re.compile(r"Question\s*(\d+)\s*(?:of|0f)\s*(\d+)", re.I)


def page_for_question(index_in_test: int, blocks: list) -> int | None:
    for b in blocks:
        t = b.get("text") or ""
        m = Q_RE.search(t)
        if m and int(m.group(1)) == index_in_test:
            return int(b.get("page_idx", 0))
    return None


def detect_on_page(doc: fitz.Document, page_idx: int, n: int) -> list[int]:
    page = doc[page_idx]
    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
    img = np.array(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
    h = img.shape[0]
    # Vùng đáp án: dưới 25% trang
    crop = img[int(h * 0.2) :, :]
    return detect_correct_on_crop(crop, n)


def main() -> int:
    bank = json.loads(BANK.read_text(encoding="utf-8"))["questions"]
    blocks = json.loads(CL.read_text(encoding="utf-8"))
    curated = (
        json.loads(CURATED.read_text(encoding="utf-8"))
        if CURATED.exists()
        else {}
    )
    doc = fitz.open(PDF)
    added = 0

    for q in bank:
        k = f"{q['topic']}|{q['testId']}|{q.get('indexInTest')}"
        if k in curated:
            continue
        if q.get("type") in ("matching", "yesno"):
            continue
        opts = q.get("options") or []
        if not opts or any(o.get("isCorrect") for o in opts):
            continue
        page_idx = (q.get("page") or 1) - 1
        if page_idx < 0:
            page_idx = page_for_question(q.get("indexInTest") or 0, blocks) or 0
        correct_idx = detect_on_page(doc, page_idx, len(opts))
        if not correct_idx:
            continue
        qtype = "multiple" if len(correct_idx) >= 2 else "single"
        curated[k] = {
            "type": qtype,
            "correctIndices": correct_idx,
        }
        added += 1
        print(f"  {k} -> indices {correct_idx}")

    doc.close()
    CURATED.write_text(
        json.dumps(curated, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"PDF rescan added {added} keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
