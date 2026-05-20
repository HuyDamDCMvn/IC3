"""
Phân tích PDF + MinerU để tìm quy luật: câu nào có hình minh họa, câu nào chỉ chữ.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "ic3-answer-detect"))
sys.path.insert(0, str(ROOT / "tools"))
from rebuild_from_mineru import (  # noqa: E402
    Q_RE,
    blocks_on_page,
    group_questions,
    is_illustration_question,
    normalize_vn,
    parse_topic,
    split_prompt_options,
)
from vn_ocr import normalize_vn as norm_vn  # noqa: E402

PDF = ROOT / "data" / "ic3_unlocked.pdf"
OCR_DIR = ROOT / "data" / "mineru_out_full" / "ic3_unlocked" / "ocr"
OCR_JSON = OCR_DIR / "ic3_unlocked_content_list.json"
OUT_RULES = ROOT / "data" / "pdf-image-rules.json"
OUT_REPORT = ROOT / "data" / "pdf-image-report.json"

# --- Quy luật từ đọc PDF IC3 GS6 Spark LV1 ---

PROMPT_IMAGE_PICK = re.compile(
    r"hinh\s*anh\s*nay\s|"
    r"hinh\s*anh\s*nao\s+sau|"
    r"hinh\s*anh\s*nao.*la\s*hinh|"
    r"cho\s+biet.*hinh\s*anh\s*nao|"
    r"hinh\s*anh\s*nao\s+duoi",
    re.I,
)

PROMPT_OPTIONS_ARE_IMAGES = re.compile(
    r"hinh\s*anh\s*nao\s+sau.*la\s*hinh\s*anh\s+cua|"
    r"hai\s+thiet\s+bi\s+nao.*\(chon",
    re.I,
)

MATCHING = re.compile(r"gh[eé]p|kéo.*sang|di chuy[eê]n t", re.I)
YESNO = re.compile(
    r"chon\s*co|chon\s*dung|phat\s*bieu|dung\s+hoac\s+sai|"
    r"co\s+neu.*dung|khong\s+neu",
    re.I,
)

MIN_IMAGE_AREA = 12_000  # bbox 0-1000 scale, ~3% page


def bbox_area(bb: list[float]) -> float:
    return max(0, bb[2] - bb[0]) * max(0, bb[3] - bb[1])


def images_in_y_band(
    all_blocks: list[dict], page_idx: int, y0: float, y1: float
) -> list[dict]:
    """Ảnh MinerU trong dải Y (0–1000) — group_questions bỏ qua block image."""
    out = []
    for b in all_blocks:
        if b.get("type") != "image" or not b.get("img_path"):
            continue
        if int(b.get("page_idx", -1)) != page_idx:
            continue
        bb = b.get("bbox") or [0, 0, 0, 0]
        cy = (bb[1] + bb[3]) / 2
        if y0 - 20 <= cy <= y1 + 20:
            out.append(b)
    return out


def large_illustration_images(imgs: list[dict]) -> list[dict]:
    return [b for b in imgs if bbox_area(b.get("bbox") or [0, 0, 0, 0]) >= MIN_IMAGE_AREA]


def pdf_raster_in_band(doc: fitz.Document, page_idx: int, y0n: float, y1n: float) -> int:
    """Đếm ảnh raster trong dải Y (0–1) trên trang PDF."""
    page = doc[page_idx]
    h = page.rect.height
    y0, y1 = y0n * h, y1n * h
    count = 0
    for img in page.get_images(full=True):
        try:
            rects = page.get_image_rects(img[0])
        except Exception:
            continue
        for r in rects:
            cy = (r.y0 + r.y1) / 2
            if y0 - 5 <= cy <= y1 + 5 and (r.x1 - r.x0) * (r.y1 - r.y0) > 800:
                count += 1
    return count


def classify_question(
    g: dict,
    doc: fitz.Document,
    page_bounds: dict[str, tuple[float, float]],
    all_blocks: list[dict],
) -> dict:
    page_idx = int(g["page_idx"])
    blocks = blocks_on_page(g.get("blocks") or [], page_idx)
    prompt, opts = split_prompt_options(blocks)
    n = norm_vn(prompt)

    key = f"{g['topic']}|{g['testId']}|{g['index']}"
    y0n, y1n = page_bounds.get(key, (65.0, 995.0))
    imgs = images_in_y_band(all_blocks, page_idx, y0n, y1n)
    large_imgs = large_illustration_images(imgs)
    pdf_img_count = pdf_raster_in_band(doc, page_idx, y0n / 1000, y1n / 1000)

    # Heuristic flags
    prompt_pick_image = bool(PROMPT_IMAGE_PICK.search(n))
    prompt_options_images = bool(PROMPT_OPTIONS_ARE_IMAGES.search(n))
    is_matching = bool(MATCHING.search(n))
    is_yesno = bool(YESNO.search(n)) or bool(
        re.search(r"chon\s*co|chon\s*dung", n, re.I)
    )
    old_rule = is_illustration_question(prompt)

    # Quyết định cuối
    has_illustration = False
    reason = "text_only"

    if is_matching:
        reason = "matching_ui"
    elif is_yesno:
        reason = "yesno_dropdown"
    elif prompt_pick_image and large_imgs:
        has_illustration = True
        reason = "prompt_hinh_anh_nay + photo"
    elif prompt_options_images and len(imgs) >= 2:
        has_illustration = True
        reason = "pick_image_from_options (grid)"
    elif len(imgs) >= 2 and not is_yesno and not is_matching:
        has_illustration = True
        reason = "multiple_images_in_band"
    elif prompt_pick_image:
        has_illustration = True
        reason = "prompt_hinh_anh"
    elif len(large_imgs) >= 1 and not is_yesno and not is_matching:
        has_illustration = True
        reason = "large_mineru_image"
    elif pdf_img_count >= 1 and prompt_pick_image:
        has_illustration = True
        reason = "pdf_raster_in_band"

    return {
        "key": key,
        "topic": g["topic"],
        "testId": g["testId"],
        "indexInTest": g["index"],
        "page": page_idx + 1,
        "prompt": prompt[:120],
        "hasIllustration": has_illustration,
        "oldIsIllustrationRule": old_rule,
        "reason": reason,
        "mineruImageCount": len(imgs),
        "largeImageCount": len(large_imgs),
        "pdfRasterInBand": pdf_img_count,
        "isMatching": is_matching,
        "isYesNo": is_yesno,
    }


def md_image_counts_for_groups(groups: list[dict]) -> dict[str, int]:
    """Đếm ![](images/...) trong MD — khớp 1:1 thứ tự marker Question."""
    md_lines = (OCR_DIR / "ic3_unlocked.md").read_text(encoding="utf-8").splitlines()
    topic = ("topic-1", "test-1")
    secs: list[dict] = []
    cur: dict = {"imgs": 0, "q": 0, "topic": "", "test": ""}
    for line in md_lines:
        t = line.strip()
        if t:
            topic = parse_topic(t, topic)
        m = Q_RE.search(t)
        if m:
            if cur["q"]:
                secs.append(cur)
            cur = {"imgs": 0, "q": int(m.group(1)), "topic": topic[0], "test": topic[1]}
            continue
        if cur["q"]:
            cur["imgs"] += len(re.findall(r"!\[\]\(images/", line))
    if cur["q"]:
        secs.append(cur)
    out: dict[str, int] = {}
    for g, s in zip(groups, secs):
        out[f"{g['topic']}|{g['testId']}|{g['index']}"] = s["imgs"]
    return out


def image_question_kind(prompt: str, md_imgs: int) -> str:
    n = norm_vn(prompt)
    if PROMPT_IMAGE_PICK.search(n) and re.search(r"hinh\s*anh\s*nay", n, re.I):
        return "A_single_illustration"
    if PROMPT_OPTIONS_ARE_IMAGES.search(n) or (
        md_imgs >= 2 and re.search(r"hinh\s*anh\s*nao", n, re.I)
    ):
        return "B_options_are_images"
    if md_imgs >= 1:
        return "C_ui_screenshot_context"
    return "none"


def main() -> int:
    from rebuild_from_mineru import build_page_y_bounds

    blocks = json.loads(OCR_JSON.read_text(encoding="utf-8"))
    groups = group_questions(blocks)
    page_bounds = build_page_y_bounds(groups)
    md_counts = md_image_counts_for_groups(groups)
    doc = fitz.open(PDF)

    rows = []
    for g in groups:
        row = classify_question(g, doc, page_bounds, blocks)
        key = row["key"]
        row["mdImageCount"] = md_counts.get(key, 0)
        row["kind"] = image_question_kind(row["prompt"], row["mdImageCount"])
        if row["mdImageCount"] > 0:
            row["hasIllustration"] = True
            if row["kind"] == "A_single_illustration":
                row["reason"] = "hinh_anh_nay + photo"
            elif row["kind"] == "B_options_are_images":
                row["reason"] = "dap_an_la_anh (grid)"
            else:
                row["reason"] = "anh_minh_hoa_giao_dien"
        rows.append(row)
    doc.close()

    with_img = [r for r in rows if r["mdImageCount"] > 0]
    without = [r for r in rows if r["mdImageCount"] == 0]
    by_kind: dict[str, list] = defaultdict(list)
    for r in with_img:
        by_kind[r["kind"]].append(r["key"])

    by_reason: dict[str, int] = defaultdict(int)
    for r in rows:
        by_reason[r["reason"]] += 1

    rules = {
        "version": 1,
        "source": "IC3 GS6 Spark LV1 PDF + MinerU",
        "summary": {
            "totalQuestions": len(rows),
            "withIllustration": len(with_img),
            "withoutIllustration": len(without),
        },
        "withIllustration": {
            "total": len(with_img),
            "byKind": {k: v for k, v in by_kind.items()},
            "kinds": {
                "A_single_illustration": {
                    "count": len(by_kind.get("A_single_illustration", [])),
                    "rule": "Đề có 'Hình ảnh này cho biết…' + 1–2 ảnh thiết bị lớn; đáp án là chữ (Laptop, Tablet…).",
                    "app": "Hiển thị snapshot giữa màn hình (should_attach_snapshot=true).",
                    "keys": by_kind.get("A_single_illustration", []),
                },
                "B_options_are_images": {
                    "count": len(by_kind.get("B_options_are_images", [])),
                    "rule": "Đề 'Hình ảnh nào sau đây là…' hoặc '(Chọn 2)' kèm lưới 4+ ảnh; đáp án là ảnh, không phải A/B/C chữ.",
                    "app": "Không snapshot giữa màn hình; gắn ảnh vào từng lựa chọn (option images).",
                    "keys": by_kind.get("B_options_are_images", []),
                },
                "C_ui_screenshot_context": {
                    "count": len(by_kind.get("C_ui_screenshot_context", [])),
                    "rule": "Có ảnh chụp giao diện (trình duyệt, tập tin, email…) nhưng đề không bắt đầu bằng 'Hình ảnh này'.",
                    "app": "Tùy curated: có thể snapshot hoặc chỉ chữ nếu đề đủ rõ.",
                    "keys": by_kind.get("C_ui_screenshot_context", []),
                },
            },
        },
        "withoutIllustration": {
            "description": "Chỉ hiển thị đề + đáp án chữ, không snapshot PDF",
            "types": [
                "Trắc nghiệm chữ (là gì?, kịch bản, chọn A/B/C/D)",
                "Có/Không / Đúng-Sai / Thực tế-Ý kiến (dropdown)",
                "Ghép mảnh (matching) — UI ghép trong app, không ảnh đề",
                "Chọn 2 / Chọn 3 — chỉ text",
            ],
            "detectBy": [
                "Không có prompt 'hình ảnh'",
                "Không có image block MinerU lớn trong nhóm",
                "reason: text_only | yesno_dropdown | matching_ui",
            ],
        },
        "implementation": {
            "shouldAttachSnapshot": "hasIllustration only",
            "legacyRule": "is_illustration_question() — chỉ khớp 'Hình ảnh này…', bỏ sót Q2/Q3",
        },
    }

    OUT_RULES.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_REPORT.write_text(
        json.dumps(
            {
                "byReason": dict(by_reason),
                "withIllustration": with_img,
                "withoutIllustration": without[:30],
                "all": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=== Quy luật hình ảnh IC3 PDF ===\n")
    print(f"Tổng câu (marker Question): {len(rows)}")
    print(f"  Có ảnh trong PDF (MD): {len(with_img)}")
    print(f"  Chỉ chữ / không ảnh:   {len(without)}\n")
    print("Loại câu có ảnh:")
    for kind, keys in by_kind.items():
        print(f"  {kind}: {len(keys)} câu")
    print("\nPhân loại chi tiết (reason):")
    for k, v in sorted(by_reason.items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")
    print(f"\nĐã ghi: {OUT_RULES}")
    print(f"Chi tiết: {OUT_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
