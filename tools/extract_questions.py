"""
Extract IC3 GS6 Spark LV1 questions from password-protected PDF.
Correct answers: green checkmarks (tick xanh) on the left of options.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

PDF_PATH = Path(r"c:\Users\Acer\Downloads\On Thi IC3 GS6 SPARK LV1-Pass.pdf")
PDF_PASSWORD = "ttthaqv"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.json"
RENDER_DIR = Path(__file__).resolve().parent.parent / "data" / "pages"

SKIP_PAGES = {1, 70, 71}  # cover, closing, ads


@dataclass
class Option:
    id: str
    text: str
    is_correct: bool


@dataclass
class Question:
    id: str
    topic: str
    test_id: str
    page: int
    index_in_test: int
    total_in_test: int
    prompt: str
    type: str  # single | multiple | truefalse | matching
    options: list[Option] = field(default_factory=list)
    image_page: str | None = None


def green_mark_centroids(img_rgb: np.ndarray) -> list[tuple[int, int]]:
    g = img_rgb[:, :, 1].astype(int)
    r = img_rgb[:, :, 0].astype(int)
    b = img_rgb[:, :, 2].astype(int)
    mask = (g > 140) & (g > r + 35) & (g > b + 35) & (r < 130) & (g < 230)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return []
    # cluster by y (option rows)
    points = sorted(zip(ys.tolist(), xs.tolist()), key=lambda p: p[0])
    clusters: list[list[tuple[int, int]]] = []
    for y, x in points:
        if x > 120:  # checkmarks are on the left
            continue
        if not clusters or abs(y - clusters[-1][0][0]) > 25:
            clusters.append([(y, x)])
        else:
            clusters[-1].append((y, x))
    centroids = []
    for cl in clusters:
        cy = int(sum(p[0] for p in cl) / len(cl))
        cx = int(sum(p[1] for p in cl) / len(cl))
        if cx < 100:
            centroids.append((cy, cx))
    return centroids


def parse_topic_header(text: str) -> tuple[str, str] | None:
    m = re.search(r"CHỦ ĐỀ\s*(\d+|MỞ RỘNG)\s*[-–]\s*TEST\s*(\d+)", text, re.I)
    if m:
        topic = f"topic-{m.group(1).lower().replace(' ', '-')}"
        test_id = f"test-{m.group(2)}"
        return topic, test_id
    if "MỞ RỘNG" in text.upper():
        return "topic-extended", "test-1"
    return None


def classify_question_type(prompt: str, options: list[str]) -> str:
    p = prompt.lower()
    if "chọn 2" in p or "chọn hai" in p or "(chọn 2)" in p:
        return "multiple"
    if "đúng" in p and "sai" in p and len(options) <= 6:
        if all(o.strip().lower() in ("đúng", "sai", "có", "không", "yes", "no") for o in options if o):
            return "truefalse"
    if "nối" in p or "ghép" in p or "di chuyển" in p:
        return "matching"
    return "single"


def extract_page(reader, page_num: int, topic: str, test_id: str) -> tuple[list[Question], str | None]:
    import easyocr

    doc_page = page_num - 1
    pix = reader[doc_page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img_rgb = np.array(img)

    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    rel_img = f"pages/page_{page_num:03d}.png"
    img.save(RENDER_DIR.parent / rel_img)

    ocr = reader._ocr  # type: ignore
    results = ocr.readtext(str(RENDER_DIR.parent / rel_img))

    lines: list[tuple[str, int, int]] = []
    for bbox, text, conf in results:
        if conf < 0.25 or not text.strip():
            continue
        cy = int(sum(p[1] for p in bbox) / 4)
        cx = int(sum(p[0] for p in bbox) / 4)
        lines.append((text.strip(), cy, cx))

    lines.sort(key=lambda x: x[1])
    green_ys = [c[0] for c in green_mark_centroids(img_rgb)]

    full_text = "\n".join(t[0] for t in lines)
    new_topic = parse_topic_header(full_text)
    if new_topic:
        topic, test_id = new_topic

    questions: list[Question] = []
    current: dict | None = None
    option_lines: list[tuple[str, int]] = []

    q_pattern = re.compile(r"Question\s*(\d+)\s*(?:of|0f)\s*(\d+)", re.I)

    for text, cy, cx in lines:
        if any(
            skip in text.upper()
            for skip in (
                "TTNNTH",
                "TÀI LIỆU ÔN THI",
                "IC3 GS6",
                "CHỦ ĐỀ",
                "TEST ",
                "Page ",
                "HƯỚNG DẪN",
                "Nguồn tài liệu",
                "Học sinh chú ý",
            )
        ):
            continue

        qm = q_pattern.search(text)
        if qm:
            if current and current.get("prompt"):
                questions.append(_finalize(current, option_lines, green_ys, topic, test_id, page_num, rel_img))
            current = {
                "index": int(qm.group(1)),
                "total": int(qm.group(2)),
                "prompt_parts": [],
            }
            option_lines = []
            continue

        if current is None:
            continue

        # prompt vs option heuristic
        is_option = (
            cx < 200
            and len(text) < 120
            and not text.endswith("?")
            and "Question" not in text
        ) or (
            len(option_lines) > 0
            and cy > (option_lines[-1][1] if option_lines else 0) - 5
            and len(text) < 150
        )

        if not option_lines and not text.endswith("?"):
            if len(text) > 15 or "?" in text:
                current["prompt_parts"].append(text)
            continue

        if text.endswith("?") or (len(text) > 40 and "?" in text):
            current["prompt_parts"].append(text)
        elif re.match(r"^[A-D]\.|^\d+\.", text):
            option_lines.append((text, cy))
        elif len(text) > 3 and not q_pattern.search(text):
            if current["prompt_parts"] and not option_lines:
                if text.endswith("?") or len(" ".join(current["prompt_parts"])) < 20:
                    current["prompt_parts"].append(text)
                else:
                    option_lines.append((text, cy))
            else:
                option_lines.append((text, cy))

    if current and current.get("prompt_parts"):
        questions.append(_finalize(current, option_lines, green_ys, topic, test_id, page_num, rel_img))

    return questions, f"{topic}|{test_id}"


def _finalize(
    current: dict,
    option_lines: list[tuple[str, int]],
    green_ys: list[int],
    topic: str,
    test_id: str,
    page: int,
    rel_img: str,
) -> Question:
    prompt = " ".join(current["prompt_parts"]).strip()
    opts: list[Option] = []
    for i, (text, cy) in enumerate(option_lines):
        is_correct = any(abs(cy - gy) < 35 for gy in green_ys)
        opts.append(
            Option(
                id=chr(65 + i),
                text=text,
                is_correct=is_correct,
            )
        )

    if opts and not any(o.is_correct for o in opts):
        # fallback: first option if only one green cluster matched page
        pass

    qtype = classify_question_type(prompt, [o.text for o in opts])
    correct_count = sum(1 for o in opts if o.is_correct)

    if qtype == "multiple" and correct_count == 0 and len(green_ys) >= 2:
        sorted_opts = sorted(enumerate(option_lines), key=lambda x: x[1][1])
        green_sorted = sorted(green_ys)
        for idx, (_, cy) in enumerate(sorted_opts):
            opts[idx] = Option(
                id=opts[idx].id,
                text=opts[idx].text,
                is_correct=any(abs(cy - gy) < 40 for gy in green_sorted),
            )

    return Question(
        id=str(uuid.uuid4()),
        topic=topic,
        test_id=test_id,
        page=page,
        index_in_test=current["index"],
        total_in_test=current["total"],
        prompt=prompt,
        type=qtype,
        options=opts,
        image_page=rel_img,
    )


def main():
    import easyocr

    print("Loading EasyOCR...")
    ocr_reader = easyocr.Reader(["vi", "en"], gpu=False, verbose=False)

    doc = fitz.open(PDF_PATH)
    doc.authenticate(PDF_PASSWORD)

    topic, test_id = "topic-1", "test-1"
    all_questions: list[Question] = []
    seen_keys: set[str] = set()

    class _Reader:
        _ocr = ocr_reader

    r = _Reader()
    r.__class__ = type("R", (), {"__getitem__": lambda self, i: doc[i]})

    for page_num in range(1, doc.page_count + 1):
        if page_num in SKIP_PAGES:
            continue
        print(f"Processing page {page_num}/{doc.page_count}...")
        pix = doc[page_num - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        RENDER_DIR.mkdir(parents=True, exist_ok=True)
        img_path = RENDER_DIR / f"page_{page_num:03d}.png"
        img.save(img_path)

        img_rgb = np.array(img)
        green_ys = [c[0] for c in green_mark_centroids(img_rgb)]
        results = ocr_reader.readtext(str(img_path))

        lines: list[tuple[str, int, int]] = []
        for bbox, text, conf in results:
            if conf < 0.25 or not text.strip():
                continue
            cy = int(sum(p[1] for p in bbox) / 4)
            cx = int(sum(p[0] for p in bbox) / 4)
            lines.append((text.strip(), cy, cx))
        lines.sort(key=lambda x: x[1])

        full_text = "\n".join(t[0] for t in lines)
        nt = parse_topic_header(full_text)
        if nt:
            topic, test_id = nt

        q_pattern = re.compile(r"Question\s*(\d+)\s*(?:of|0f)\s*(\d+)", re.I)
        current: dict | None = None
        option_lines: list[tuple[str, int]] = []
        rel_img = f"pages/page_{page_num:03d}.png"

        for text, cy, cx in lines:
            if any(
                skip in text.upper()
                for skip in (
                    "TTNNTH",
                    "TÀI LIỆU",
                    "IC3 GS6",
                    "CHỦ ĐỀ",
                    "PAGE ",
                    "HƯỚNG DẪN",
                    "NGUỒN TÀI",
                    "HỌC SINH",
                    "RESOURES",
                    "RESOURCES",
                )
            ):
                continue
            if re.match(r"^TEST\s*\d+$", text, re.I):
                continue

            qm = q_pattern.search(text)
            if qm:
                if current and current.get("prompt_parts"):
                    q = _finalize(current, option_lines, green_ys, topic, test_id, page_num, rel_img)
                    key = f"{q.topic}|{q.test_id}|{q.index_in_test}|{q.prompt[:40]}"
                    if key not in seen_keys and q.options and q.prompt:
                        seen_keys.add(key)
                        all_questions.append(q)
                current = {"index": int(qm.group(1)), "total": int(qm.group(2)), "prompt_parts": []}
                option_lines = []
                continue

            if current is None:
                continue

            if "?" in text and len(text) > 10:
                current["prompt_parts"].append(text)
            elif len(option_lines) < 8 and len(text) > 1:
                if current["prompt_parts"] and len(text) < 8 and text.lower() in ("có", "không", "đúng", "sai"):
                    option_lines.append((text, cy))
                elif not current["prompt_parts"] or cy > lines[0][1] + 50:
                    if len(text) < 200:
                        option_lines.append((text, cy))

        if current and current.get("prompt_parts"):
            q = _finalize(current, option_lines, green_ys, topic, test_id, page_num, rel_img)
            key = f"{q.topic}|{q.test_id}|{q.index_in_test}|{q.prompt[:40]}"
            if key not in seen_keys and q.options and q.prompt:
                seen_keys.add(key)
                all_questions.append(q)

    doc.close()

    # Post-filter: must have at least one correct or infer from type
    valid = []
    for q in all_questions:
        if any(o.is_correct for o in q.options):
            valid.append(q)
        elif q.type == "truefalse" and len(q.options) >= 2:
            valid.append(q)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "source": "On Thi IC3 GS6 SPARK LV1-Pass.pdf",
        "total": len(valid),
        "questions": [asdict(q) for q in valid],
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(valid)} questions to {OUT_PATH}")


if __name__ == "__main__":
    main()
