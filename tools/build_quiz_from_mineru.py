"""
Build visual quiz bank from MinerU output + green-check answer detection.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import uuid
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "ic3-answer-detect"))

from detector import green_check_centroids  # noqa: E402

PDF_PATH = ROOT / "data" / "ic3_unlocked.pdf"
MINERU_OCR = ROOT / "data" / "mineru_out" / "ic3_unlocked" / "ocr"
MINERU_OCR_FULL = ROOT / "data" / "mineru_out_full" / "ic3_unlocked" / "ocr"
OUT_DIR = ROOT / "data" / "quiz-visual"
OUT_ASSETS = OUT_DIR / "assets"
OUT_JSON = OUT_DIR / "questions.json"

Q_RE = re.compile(r"Question\s*(\d+)\s*(?:of|0f)\s*(\d+)", re.I)
TOPIC_RE = re.compile(r"CHỦ ĐỀ\s*(\d+|MỞ RỘNG)\s*[-–]\s*TEST\s*(\d+)", re.I)

# Known correct answers when tick detection fails (from PDF green checks)
CURATED: list[tuple[str, list[int]]] = [
    ("thiết bị ngoại vi", [0, 2]),
    ("ngoại vi", [0, 2]),
    ("wifi", [2]),
    ("internet", [2]),
    ("quyền riêng tư", [1]),
    ("bình luận", [3]),
    ("trolling", [0]),
    ("bookmark", [3]),
    ("liên kết", [3]),
    ("trình chiếu", [2]),
    ("ctrl + a", [3]),
    ("email", [0]),
    ("màu sắc yêu thích", [0]),
    ("người lạ", [0]),
    ("không bao giờ", [0]),
    ("media balance", [0]),
    ("sạc", [0]),
    ("xóa ảnh", [0]),
    ("ý kiến", [1]),
    ("collaboration", [0]),
    ("cộng tác", [0]),
]


def _norm(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _curated_correct_ids(prompt: str, n: int) -> list[int]:
    p = _norm(prompt)
    for key, indices in CURATED:
        if _norm(key) in p:
            return [i for i in indices if i < n]
    return []


def pick_mineru_dir() -> Path:
    if (MINERU_OCR_FULL / "ic3_unlocked_content_list.json").exists():
        return MINERU_OCR_FULL
    return MINERU_OCR


def bbox_to_pixels(bbox: list[float], w: int, h: int, pad: int = 8) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    px0 = max(0, int(x0 / 1000 * w) - pad)
    py0 = max(0, int(y0 / 1000 * h) - pad)
    px1 = min(w, int(x1 / 1000 * w) + pad)
    py1 = min(h, int(y1 / 1000 * h) + pad)
    return px0, py0, px1, py1


def render_page_crop(page: fitz.Page, bbox: list[float], scale: float = 2.0) -> Image.Image:
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    x0, y0, x1, y1 = bbox_to_pixels(bbox, pix.width, pix.height, pad=12)
    return img.crop((x0, y0, x1, y1))


def detect_correct_on_crop(crop: Image.Image, option_count: int) -> list[int]:
    """Map green ticks to option indices by vertical bands."""
    arr = np.array(crop)
    greens = green_check_centroids(arr)
    if not greens or option_count <= 0:
        return []
    h = crop.height
    band_h = h / option_count
    correct = []
    for i in range(option_count):
        y_mid = (i + 0.5) * band_h
        for gy, _gx in greens:
            if abs(gy - y_mid) < band_h * 0.6:
                correct.append(i)
                break
    return correct


def parse_topic(text: str, default: tuple[str, str]) -> tuple[str, str]:
    m = TOPIC_RE.search(text)
    if m:
        t = m.group(1).lower().replace(" ", "-")
        if "mở" in t or "mo" in t:
            return "topic-extended", f"test-{m.group(2)}"
        return f"topic-{t}", f"test-{m.group(2)}"
    return default


def load_content_list(ocr_dir: Path) -> list[dict]:
    path = ocr_dir / "ic3_unlocked_content_list.json"
    return json.loads(path.read_text(encoding="utf-8"))


def copy_image(ocr_dir: Path, img_path: str, dest_name: str) -> str:
    src = ocr_dir / img_path.replace("/", "\\")
    if not src.exists():
        src = ocr_dir / Path(img_path).name
    OUT_ASSETS.mkdir(parents=True, exist_ok=True)
    dest = OUT_ASSETS / dest_name
    if src.exists():
        shutil.copy2(src, dest)
        return f"/quiz-visual/assets/{dest_name}"
    return ""


def group_questions(blocks: list[dict]) -> list[dict]:
    """Group blocks; images BEFORE 'Question X of Y' belong to that question."""
    groups: list[dict] = []
    current: dict | None = None
    pending: list[dict] = []
    topic = ("topic-1", "test-1")

    for b in blocks:
        if b.get("type") in ("header", "footer", "page_number", "aside_text"):
            text = b.get("text", "")
            topic = parse_topic(text, topic)
            continue

        text = (b.get("text") or "").strip()
        qm = Q_RE.search(text)

        if qm:
            if current:
                groups.append(current)
            current = {
                "index": int(qm.group(1)),
                "total": int(qm.group(2)),
                "topic": topic[0],
                "testId": topic[1],
                "page_idx": b.get("page_idx", 0),
                "blocks": [*pending, b],
            }
            pending = []
            continue

        if current is not None:
            if text and "CHỦ ĐỀ" not in text.upper():
                current["blocks"].append(b)
        else:
            pending.append(b)

    if current:
        groups.append(current)
    return groups


def blocks_to_question(
    g: dict, ocr_dir: Path, doc: fitz.Document
) -> dict | None:
    blocks = g["blocks"]
    if not blocks:
        return None

    prompt_parts: list[str] = []
    option_items: list[dict] = []
    images: list[str] = []

    for b in blocks:
        if b.get("type") == "text":
            t = (b.get("text") or "").strip()
            if not t or Q_RE.search(t):
                continue
            if "?" in t or len(t) > 50:
                prompt_parts.append(t)
            elif len(t) < 120:
                option_items.append({"kind": "text", "text": t, "bbox": b.get("bbox")})
        elif b.get("type") == "image":
            img_path = b.get("img_path", "")
            if img_path:
                name = Path(img_path).name
                url = copy_image(ocr_dir, img_path, name)
                if url:
                    images.append(url)
                option_items.append({"kind": "image", "imageUrl": url, "bbox": b.get("bbox")})

    prompt = " ".join(prompt_parts).strip()
    if not prompt and not images:
        return None

    # Union bbox for question snapshot
    bboxes = [b["bbox"] for b in blocks if b.get("bbox")]
    if bboxes:
        ux0 = min(bb[0] for bb in bboxes)
        uy0 = min(bb[1] for bb in bboxes)
        ux1 = max(bb[2] for bb in bboxes)
        uy1 = max(bb[3] for bb in bboxes)
        union_bbox = [ux0, uy0, ux1, uy1]
    else:
        union_bbox = [50, 80, 950, 900]

    page_idx = g.get("page_idx", blocks[0].get("page_idx", 0))
    page = doc[page_idx]
    crop = render_page_crop(page, union_bbox)
    snap_name = f"q_{g['topic']}_{g['testId']}_{g['index']}_{uuid.uuid4().hex[:8]}.jpg"
    OUT_ASSETS.mkdir(parents=True, exist_ok=True)
    snap_path = OUT_ASSETS / snap_name
    crop.save(snap_path, quality=88)
    snapshot_url = f"/quiz-visual/assets/{snap_name}"

    # Build options A,B,C,D...
    options = []
    opt_count = max(len(option_items), 1)
    correct_idx = detect_correct_on_crop(crop, opt_count)

    for i, item in enumerate(option_items):
        oid = chr(65 + i)
        options.append(
            {
                "id": oid,
                "text": item.get("text", f"Lựa chọn {oid}"),
                "imageUrl": item.get("imageUrl"),
                "isCorrect": i in correct_idx,
            }
        )

    if not options and images:
        for i, url in enumerate(images):
            oid = chr(65 + i)
            options.append(
                {
                    "id": oid,
                    "text": f"Lựa chọn {oid}",
                    "imageUrl": url,
                    "isCorrect": i in correct_idx,
                }
            )

    # Merge curated answers when green detection fails
    if options and not any(o["isCorrect"] for o in options):
        curated = _curated_correct_ids(prompt, len(options))
        for i in curated:
            if 0 <= i < len(options):
                options[i]["isCorrect"] = True

    qtype = (
        "multiple"
        if re.search(r"ch[oơ]n\s*2|\(ch[oơ]n\s*2\)", prompt, re.I)
        else "single"
    )

    return {
        "id": str(uuid.uuid4()),
        "topic": g["topic"],
        "testId": g["testId"],
        "prompt": prompt,
        "type": qtype,
        "snapshotUrl": snapshot_url,
        "page": page_idx + 1,
        "indexInTest": g["index"],
        "totalInTest": g["total"],
        "options": options,
        "images": images,
    }


def main():
    ocr_dir = pick_mineru_dir()
    if not (ocr_dir / "ic3_unlocked_content_list.json").exists():
        print("MinerU output not found. Run: mineru -p data/ic3_unlocked.pdf -o data/mineru_out -b pipeline -m ocr")
        return 1

    blocks = load_content_list(ocr_dir)
    groups = group_questions(blocks)
    doc = fitz.open(PDF_PATH)

    questions = []
    for g in groups:
        q = blocks_to_question(g, ocr_dir, doc)
        if q and q.get("options"):
            if any(o["isCorrect"] for o in q["options"]):
                questions.append(q)
            elif q["prompt"]:
                questions.append(q)

    doc.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "source": "MinerU + IC3 PDF",
        "theme": "ic3-review",
        "total": len(questions),
        "questions": questions,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {len(questions)} visual questions -> {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
