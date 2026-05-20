"""
Rebuild question bank: 1 câu = 1 marker "Question X of Y" (đủ đáp án, tick xanh).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import uuid
from collections import defaultdict
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "packages" / "ic3-answer-detect"))
from image_question_rules import (  # noqa: E402
    classify_image_kind,
    enrich_group_blocks,
    md_image_counts_for_groups,
    should_attach_snapshot as snap_for_kind,
    use_option_images_only,
)
from detector import (  # noqa: E402
    detect_correct_option_indices,
    green_check_centroids,
    row_dropdown_is_yes,
)
from vn_ocr import (  # noqa: E402
    INSTRUCTION_ONLY_RE,
    clean_option_text,
    clean_prompt_text,
    is_junk_option,
    is_junk_question,
    normalize_vn,
)

PDF_PATH = ROOT / "data" / "ic3_unlocked.pdf"
OCR_DIR = ROOT / "data" / "mineru_out_full" / "ic3_unlocked" / "ocr"
OUT_DIR = ROOT / "data" / "quiz-visual"
OUT_JSON = OUT_DIR / "questions.json"
CURATED_PATH = ROOT / "data" / "curated-answers.json"
CURATED = (
    json.loads(CURATED_PATH.read_text(encoding="utf-8"))
    if CURATED_PATH.exists()
    else {}
)

Q_RE = re.compile(r"Question\s*(\d+)\s*(?:of|0f)\s*(\d+)", re.I)
TOPIC_RE = re.compile(
    r"CHU\s*D[EÊỀ]\s*(\d+|M[OỞ]\s*R[OỘ]NG)\s*[-–]\s*TE?ST\s*(\d+)",
    re.I,
)
CHON2_RE = re.compile(r"ch[oơ]n\s*2|\(ch[oơ]n\s*2\)", re.I)
CHON3_RE = re.compile(r"ch[oơ]n\s*3|\(ch[oơ]n\s*3\)", re.I)
YESNO_CO_PROMPT_RE = re.compile(
    r"ch[oơ]n\s*c[oó]|c[oó]\s+n[eê]u.*d[uú]ng|kh[oô]ng\s+n[eê]u.*sai|"
    r"cho\s+m[oỗ]i\s|chon\s+co\s+hoac",
    re.I,
)
YESNO_DUNG_PROMPT_RE = re.compile(
    r"ch[oơ]n\s*[dđ][uú]ng|[dđ][uú]ng\s+n[eê]u|[dđ][uú]ng\s+ho[aă]c\s*sai|"
    r"sai\s+n[eê]u.*[dđ][uú]ng|dung.*sai",
    re.I,
)
YESNO_FACT_PROMPT_RE = re.compile(
    r"th[uự]c\s*t|thyc\s*t|ý\s*ki|y\s*ki",
    re.I,
)
ONLY_CO_KHONG = re.compile(r"^(c[oó]|kh[oô]ng|co|khong)$", re.I)
ONLY_OPINION_LABEL = re.compile(r"^(ý\s*ki|y\s*ki|opinion)", re.I)
ONLY_FACT_LABEL = re.compile(r"^(th[uự]c\s*t|thyc\s*t|fact)", re.I)
YESNO_PREFIX_OPINION = re.compile(r"^(ý\s*ki|y\s*ki|opinion)\s+(.+)", re.I)
YESNO_PREFIX_FACT = re.compile(r"^(th[uự]c\s*t|thyc\s*t|fact)\s+(.+)", re.I)
YESNO_PREFIX_CO = re.compile(r"^(c[oó]|kh[oô]ng|co|khong)\s+(.+)", re.I)
ONLY_DUNG_SAI = re.compile(r"^[dđ][uú]ng$|^sai$|^dung$", re.I)
ONLY_MANH_LABEL = re.compile(r"^(m[aạ]nh|manh)$", re.I)
ONLY_YEU_LABEL = re.compile(r"^(y[eé]u|yeu|y[eě]u)$", re.I)
PASSWORD_LIKE = re.compile(r"[@*#0-9A-Za-z]{6,}")
YESNO_PREFIX_DUNG = re.compile(r"^([dđ][uú]ng|sai|dung)\s+(.+)", re.I)
MATCH_HINT = re.compile(
    r"gh[eé]p|n[oố]i\s+m[oỗ]i|kéo|di chuy|chuy[eê]n t",
    re.I,
)
IMAGE_MC_RE = re.compile(r"h[iì]nh\s*[àa]nh|hinh\s*anh|bi[eể]u\s*tu[oơ]ng", re.I)
SKIP_MARKER = re.compile(r"^Resources\s", re.I)
PDF_HEADER_RE = re.compile(
    r"TTNNTH|IC3\s*GS6|TAI\s*LIEU\s*ON\s*THI|Page\s+\d+\s+of",
    re.I,
)


def content_blocks_for_snapshot(blocks: list[dict]) -> list[dict]:
    """Bỏ header/footer PDF khỏi vùng crop snapshot."""
    out = []
    for b in blocks:
        if b.get("type") not in ("text", "image"):
            continue
        t = (b.get("text") or "").strip()
        if t and PDF_HEADER_RE.search(t):
            continue
        if SKIP_MARKER.search(t):
            continue
        out.append(b)
    return out or blocks


def parse_topic(text: str, default: tuple[str, str]) -> tuple[str, str]:
    m = TOPIC_RE.search(text.upper().replace("Ề", "E"))
    if not m:
        return default
    raw = m.group(1).lower()
    if "mo" in raw or "rong" in raw:
        return "topic-extended", f"test-{m.group(2)}"
    num = re.search(r"\d+", raw)
    return f"topic-{num.group() if num else '1'}", f"test-{m.group(2)}"


def _bbox_area(bbox: list[float]) -> float:
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


def group_bbox_union(
    blocks: list[dict], pad_y: int = 90, pad_x: int = 30, include_images: bool = True
) -> list[float]:
    """Hộp bao toàn bộ câu (đề + đáp án + ảnh minh họa)."""
    types = ("text", "image") if include_images else ("text",)
    bbs = [b["bbox"] for b in blocks if b.get("type") in types and b.get("bbox")]
    if not bbs:
        return [50, 80, 950, 900]
    return [
        max(0, min(b[0] for b in bbs) - pad_x),
        max(0, min(b[1] for b in bbs) - pad_y),
        min(1000, max(b[2] for b in bbs) + pad_x),
        min(1000, max(b[3] for b in bbs) + pad_y),
    ]


def is_illustration_question(prompt: str) -> bool:
    """Kiểu A: 'Hình ảnh này cho biết…'"""
    n = normalize_vn(prompt)
    return bool(re.search(r"hinh\s*anh\s*nay", n, re.I))


def should_attach_snapshot(
    prompt: str, qtype: str, image_kind: str = "none", hide_snapshot: bool = False
) -> bool:
    return snap_for_kind(image_kind, hide_snapshot, qtype)


def snapshot_bbox_for_group(blocks: list[dict], prompt: str) -> list[float]:
    """Câu có ảnh minh họa: ưu tiên khung ảnh lớn nhất + dòng đề."""
    if not is_illustration_question(prompt):
        return group_bbox_union(blocks)

    img_blocks = [b for b in blocks if b.get("type") == "image" and b.get("bbox")]
    if not img_blocks:
        return group_bbox_union(blocks)

    main = max(img_blocks, key=lambda b: _bbox_area(b["bbox"]))
    text_bbs = [
        b["bbox"]
        for b in blocks
        if b.get("type") == "text"
        and b.get("bbox")
        and len((b.get("text") or "").strip()) > 12
    ]
    # Chỉ lấy dòng đề (thường ở phía trên ảnh, y nhỏ hơn)
    img_y0 = main["bbox"][1]
    prompt_bbs = [bb for bb in text_bbs if bb[3] <= img_y0 + 80] or text_bbs[:2]
    bbs = [main["bbox"], *prompt_bbs[:3]]
    pad_y, pad_x = 40, 25
    return [
        max(0, min(b[0] for b in bbs) - pad_x),
        max(0, min(b[1] for b in bbs) - pad_y),
        min(1000, max(b[2] for b in bbs) + pad_x),
        min(1000, max(b[3] for b in bbs) + pad_y),
    ]


def question_key(g: dict) -> str:
    return f"{g['topic']}|{g['testId']}|{g['index']}"


def blocks_on_page(blocks: list[dict], page_idx: int) -> list[dict]:
    """Chỉ giữ block thuộc đúng trang marker — tránh bbox lệch trang."""
    return [b for b in blocks if b.get("page_idx", page_idx) == page_idx]


def _marker_y0(blocks: list[dict]) -> float | None:
    for b in blocks:
        if b.get("bbox") and Q_RE.search((b.get("text") or "")):
            return float(b["bbox"][1])
    return None


def build_page_y_bounds(groups: list[dict]) -> dict[str, tuple[float, float]]:
    """
    Cắt dọc từng câu trên cùng một trang PDF: từ marker Question N → trước Question N+1.
    Trả về y0,y1 (thang 0–1000) theo key topic|test|index.
    """
    by_page: dict[int, list[dict]] = defaultdict(list)
    for g in groups:
        by_page[int(g["page_idx"])].append(g)

    bounds: dict[str, tuple[float, float]] = {}
    for page_idx, pgs in by_page.items():
        pgs.sort(key=lambda x: x["index"])
        for i, g in enumerate(pgs):
            raw = blocks_on_page(g.get("blocks") or [], page_idx)
            snap_blocks = content_blocks_for_snapshot(raw)
            my0 = _marker_y0(raw)
            y0 = max(0.0, (my0 - 25.0) if my0 is not None else 65.0)

            y1 = 995.0
            if i + 1 < len(pgs):
                nxt = blocks_on_page(pgs[i + 1].get("blocks") or [], page_idx)
                ny0 = _marker_y0(nxt)
                if ny0 is not None:
                    y1 = min(y1, ny0 - 12.0)

            bbs = [b["bbox"] for b in snap_blocks if b.get("bbox")]
            if bbs:
                y0 = max(y0, min(b[1] for b in bbs) - 30.0)
                y1 = min(y1, max(b[3] for b in bbs) + 45.0)
            if y1 <= y0 + 40:
                y1 = min(1000.0, y0 + 320.0)

            bounds[question_key(g)] = (max(0.0, y0), min(1000.0, y1))
    return bounds


def snapshot_bbox_for_question(
    g: dict,
    blocks: list[dict],
    prompt: str,
    page_bounds: dict[str, tuple[float, float]],
) -> list[float]:
    """Snapshot khớp đúng một câu (ưu tiên lát dọc theo trang)."""
    if is_illustration_question(prompt):
        return snapshot_bbox_for_group(blocks, prompt)

    key = question_key(g)
    snap_blocks = content_blocks_for_snapshot(blocks)
    bbs = [b["bbox"] for b in snap_blocks if b.get("bbox")]

    if key in page_bounds:
        y0, y1 = page_bounds[key]
        if bbs:
            x0 = max(0.0, min(b[0] for b in bbs) - 30.0)
            x1 = min(1000.0, max(b[2] for b in bbs) + 30.0)
        else:
            x0, x1 = 35.0, 965.0
        return [x0, y0, x1, y1]

    return group_bbox_union(snap_blocks)


def copy_illustration_snapshot(
    blocks: list[dict], ocr_dir: Path, snap_path: Path
) -> bool:
    """Dùng ảnh MinerU trích riêng làm snapshot (chính xác nhất)."""
    img_blocks = [b for b in blocks if b.get("type") == "image" and b.get("img_path")]
    if not img_blocks:
        return False
    main = max(img_blocks, key=lambda b: _bbox_area(b.get("bbox") or [0, 0, 0, 0]))
    src = ocr_dir / str(main["img_path"]).replace("/", "\\")
    if not src.exists():
        return False
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, snap_path)
    return True


def bbox_to_pixels(bbox: list[float], w: int, h: int, pad: int = 10) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    return (
        max(0, int(x0 / 1000 * w) - pad),
        max(0, int(y0 / 1000 * h) - pad),
        min(w, int(x1 / 1000 * w) + pad),
        min(h, int(y1 / 1000 * h) + pad),
    )


def group_questions(blocks: list[dict]) -> list[dict]:
    """Một nhóm = từ 'Question X of Y' đến trước marker tiếp theo."""
    groups: list[dict] = []
    current: dict | None = None
    pending: list[dict] = []
    topic = ("topic-1", "test-1")

    for b in blocks:
        text = (b.get("text") or "").strip()
        if text:
            topic = parse_topic(text, topic)

        if b.get("type") in ("header", "footer", "page_number", "aside_text"):
            continue

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
            if b.get("type") == "image" or (
                text and "CHU DE" not in text.upper()
            ):
                current["blocks"].append(b)
        else:
            if b.get("type") == "image" or text:
                pending.append(b)

    if current:
        groups.append(current)
    return groups


def split_prompt_options(blocks: list[dict]) -> tuple[str, list[dict]]:
    """text_level=2 → prompt; còn lại (ngắn, không marker) → đáp án."""
    texts: list[dict] = []
    for b in blocks:
        if b.get("type") != "text":
            continue
        t = (b.get("text") or "").strip()
        if not t or Q_RE.search(t) or SKIP_MARKER.search(t):
            continue
        if TOPIC_RE.search(t.upper()):
            continue
        texts.append(b)

    prompt_parts: list[str] = []
    options: list[dict] = []

    for b in texts:
        t = (b.get("text") or "").strip()
        if b.get("text_level") == 2:
            prompt_parts.append(t)
        elif CHON2_RE.search(t) or CHON3_RE.search(t) or "?" in t:
            if not prompt_parts:
                prompt_parts.append(t)
            elif len(t) > 40:
                prompt_parts.append(t)
            else:
                options.append(b)
        else:
            options.append(b)

    prompt = " ".join(prompt_parts).strip()

    if not prompt and texts:
        # Prompt không có text_level: dòng dài nhất có ? hoặc CHON
        scored = []
        for b in texts:
            t = (b.get("text") or "").strip()
            score = len(t)
            if "?" in t:
                score += 500
            if CHON2_RE.search(t) or CHON3_RE.search(t):
                score += 300
            if MATCH_HINT.search(t):
                score += 200
            scored.append((score, b))
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            best = scored[0][1]
            prompt = (best.get("text") or "").strip()
            options = [b for b in texts if b is not best]

    return prompt, options


def is_yesno_prompt(prompt: str) -> bool:
    n = normalize_vn(prompt)
    return bool(
        YESNO_CO_PROMPT_RE.search(n)
        or YESNO_DUNG_PROMPT_RE.search(n)
        or _is_fact_opinion_prompt(n)
        or _is_manh_yeu_prompt(n)
    )


def _is_fact_opinion_prompt(prompt: str) -> bool:
    return bool(
        re.search(r"ch[oơ]n|hay\s+chon", prompt, re.I)
        and YESNO_FACT_PROMPT_RE.search(prompt)
        and re.search(r"th[uự]c|thyc", prompt, re.I)
        and re.search(r"ki[eế]n|opinion", prompt, re.I)
    )


def _is_manh_yeu_prompt(prompt: str) -> bool:
    n = normalize_vn(prompt)
    return bool(
        re.search(r"mat\s*khau|mật\s*khẩu", n, re.I)
        and re.search(r"manh|mạnh", n, re.I)
        and re.search(r"yeu|yếu", n, re.I)
    )


def yesno_label_mode(prompt: str) -> str:
    if _is_manh_yeu_prompt(prompt):
        return "manh-yeu"
    if _is_fact_opinion_prompt(prompt):
        return "fact-opinion"
    if YESNO_DUNG_PROMPT_RE.search(prompt):
        return "dung-sai"
    return "co-khong"


def _is_dropdown_label_only(t: str, mode: str) -> bool:
    if mode == "fact-opinion":
        return bool(ONLY_OPINION_LABEL.match(t) or ONLY_FACT_LABEL.match(t))
    if mode == "dung-sai":
        return bool(ONLY_DUNG_SAI.match(t))
    if mode == "manh-yeu":
        return bool(ONLY_MANH_LABEL.match(t) or ONLY_YEU_LABEL.match(t))
    return bool(ONLY_CO_KHONG.match(t))


def _is_fact_from_label(label_text: str, vis_yes: bool | None) -> bool:
    """Chữ xanh trên nhãn = đáp án đúng là nhãn đang hiển thị."""
    opinion = bool(ONLY_OPINION_LABEL.match(label_text.strip()))
    fact = bool(ONLY_FACT_LABEL.match(label_text.strip()))
    if vis_yes is None:
        return not opinion if opinion else True
    if opinion:
        return not vis_yes
    if fact:
        return vis_yes
    return vis_yes


def _label_is_yes_co(label: str) -> bool:
    low = label.lower()
    return low.startswith("c") and not low.startswith("kh")


def _label_is_yes_dung(label: str) -> bool:
    return not label.lower().startswith("s")


def _strip_label_prefix(t: str, mode: str) -> tuple[bool | None, str]:
    """Trả về (is_yes/is_fact, statement) nếu có prefix."""
    # OCR hay dính nhãn "Có" vào đầu mệnh đề — chỉ bỏ prefix, không suy đáp án từ chữ
    if mode == "co-khong":
        m = YESNO_PREFIX_CO.match(t)
        if m and (m.group(2) or "").strip():
            return None, (m.group(2) or "").strip()
        if ONLY_CO_KHONG.match(t):
            return None, ""
    if mode == "fact-opinion":
        if ONLY_OPINION_LABEL.match(t):
            return False, ""
        if ONLY_FACT_LABEL.match(t):
            return True, ""
        mo = YESNO_PREFIX_OPINION.match(t)
        if mo:
            return False, (mo.group(2) or "").strip()
        mf = YESNO_PREFIX_FACT.match(t)
        if mf:
            return True, (mf.group(2) or "").strip()
        return None, t
    if mode == "dung-sai":
        if ONLY_DUNG_SAI.match(t):
            return _label_is_yes_dung(t), ""
        m = YESNO_PREFIX_DUNG.match(t)
        if m:
            return _label_is_yes_dung(m.group(1)), (m.group(2) or "").strip()
        return None, t
    if ONLY_CO_KHONG.match(t):
        return _label_is_yes_co(t), ""
    m = YESNO_PREFIX_CO.match(t)
    if m:
        return _label_is_yes_co(m.group(1)), (m.group(2) or "").strip()
    return None, t


def build_yesno_options_manh_yeu_pairs(
    option_blocks: list[dict],
    page_img: np.ndarray,
    page_h: int,
    page_w: int,
) -> list[dict]:
    """Nhãn Mạnh/Yếu + mật khẩu ở dòng kế — đúng PDF Question 8."""
    items: list[dict] = []
    blocks = [ob for ob in option_blocks if len((ob.get("text") or "").strip()) >= 2]
    i = 0
    while i < len(blocks):
        t = (blocks[i].get("text") or "").strip()
        if _is_dropdown_label_only(t, "manh-yeu"):
            label_bbox = blocks[i].get("bbox")
            vis = (
                row_dropdown_is_yes(page_img, label_bbox, page_h, page_w)
                if label_bbox
                else None
            )
            is_manh_label = bool(ONLY_MANH_LABEL.match(t))
            # Chữ xanh trên nhãn đang hiển thị = đáp án đúng là nhãn đó
            if vis is not None:
                pick_manh = vis if is_manh_label else not vis
            else:
                pick_manh = is_manh_label
            i += 1
            while i < len(blocks):
                nt = (blocks[i].get("text") or "").strip()
                if _is_dropdown_label_only(nt, "manh-yeu"):
                    break
                if PASSWORD_LIKE.search(nt) and not Q_RE.search(nt):
                    items.append(
                        {
                            "text": nt.replace("\\*", "*"),
                            "isCorrect": pick_manh,
                            "bbox": label_bbox,
                        }
                    )
                    i += 1
                    break
                i += 1
        else:
            i += 1
    return items


def build_yesno_options_fact_pairs(
    option_blocks: list[dict],
    page_img: np.ndarray,
    page_h: int,
    page_w: int,
) -> list[dict]:
    """Nhãn dropdown (Ý kiến) tách block — ghép với mệnh đề block kế tiếp."""
    items: list[dict] = []
    blocks = [ob for ob in option_blocks if len((ob.get("text") or "").strip()) >= 2]
    i = 0
    while i < len(blocks):
        t = (blocks[i].get("text") or "").strip()
        if _is_dropdown_label_only(t, "fact-opinion"):
            label_bbox = blocks[i].get("bbox")
            vis = (
                row_dropdown_is_yes(page_img, label_bbox, page_h, page_w)
                if label_bbox
                else None
            )
            is_fact = _is_fact_from_label(t, vis)
            parts: list[str] = []
            i += 1
            while i < len(blocks):
                nt = (blocks[i].get("text") or "").strip()
                if _is_dropdown_label_only(nt, "fact-opinion"):
                    break
                if len(nt) > 3 and not Q_RE.search(nt):
                    parts.append(nt)
                i += 1
            stmt = " ".join(parts).strip()
            if stmt:
                items.append(
                    {"text": stmt, "isCorrect": is_fact, "bbox": label_bbox}
                )
        else:
            i += 1
    return items


def build_yesno_options(
    option_blocks: list[dict],
    page_img: np.ndarray,
    page_h: int,
    page_w: int,
    mode: str,
) -> list[dict]:
    """Gom mệnh đề; màu chữ dropdown hoặc prefix OCR."""
    if mode == "manh-yeu":
        paired = build_yesno_options_manh_yeu_pairs(
            option_blocks, page_img, page_h, page_w
        )
        if len(paired) >= 1:
            return paired

    if mode == "fact-opinion":
        paired = build_yesno_options_fact_pairs(
            option_blocks, page_img, page_h, page_w
        )
        if len(paired) >= 1:
            return paired

    items: list[dict] = []
    pending_yes: bool | None = None

    for ob in option_blocks:
        t = (ob.get("text") or "").strip()
        if not t or len(t) < 2:
            continue
        bbox = ob.get("bbox")
        prefix_yes, rest = _strip_label_prefix(t, mode)

        vis_yes = None
        if bbox and mode in ("dung-sai", "fact-opinion"):
            vis_yes = row_dropdown_is_yes(page_img, bbox, page_h, page_w)

        if prefix_yes is not None:
            if mode == "fact-opinion" and vis_yes is not None:
                is_yes = _is_fact_from_label(t, vis_yes)
            else:
                is_yes = vis_yes if vis_yes is not None else prefix_yes
            if rest and len(rest) > 2:
                items.append(
                    {"text": rest, "isCorrect": is_yes, "bbox": bbox}
                )
                pending_yes = None
            else:
                pending_yes = is_yes
        elif pending_yes is not None:
            is_yes = vis_yes if vis_yes is not None else pending_yes
            items.append({"text": t, "isCorrect": is_yes, "bbox": bbox})
            pending_yes = None
        elif items:
            items[-1]["text"] = (items[-1]["text"] + " " + t).strip()
            if vis_yes is not None:
                items[-1]["isCorrect"] = vis_yes
        elif len(t) > 12:
            is_yes = vis_yes if vis_yes is not None else True
            items.append({"text": t, "isCorrect": is_yes, "bbox": bbox})

    return [it for it in items if len(it.get("text", "")) > 4]


def classify_type(prompt: str) -> str:
    if is_yesno_prompt(prompt):
        return "yesno"
    if CHON2_RE.search(prompt) or CHON3_RE.search(prompt):
        return "multiple"
    if MATCH_HINT.search(prompt):
        return "matching"
    return "single"


def cap_correct_by_prompt(prompt: str, options: list[dict]) -> None:
    """Đề ghi Chọn 2/3: giới hạn số tick nếu detector đọc thừa."""
    correct_idx = [i for i, o in enumerate(options) if o.get("isCorrect")]
    if not correct_idx:
        return
    p = normalize_vn(prompt)
    if CHON2_RE.search(p) and len(correct_idx) > 2:
        keep = correct_idx[:2]
    elif CHON3_RE.search(p) and len(correct_idx) > 3:
        keep = correct_idx[:3]
    else:
        return
    for o in options:
        o["isCorrect"] = False
    for i in keep:
        options[i]["isCorrect"] = True


def infer_mc_type(qtype: str, prompt: str, options: list[dict]) -> str:
    """
    Loại câu sau khi đã gắn tick xanh / curated:
    - >= 2 tick xanh (đáp án đúng) → multiple
    - còn lại → single (kể cả đề ghi Chọn 2 nếu PDF chỉ có 1 tick)
    """
    if qtype in ("yesno", "matching"):
        return qtype
    if is_yesno_prompt(prompt):
        return "yesno"
    if MATCH_HINT.search(prompt):
        return "matching"
    n_ok = sum(1 for o in options if o.get("isCorrect"))
    if n_ok >= 2:
        return "multiple"
    return "single"


def detect_correct_per_row(
    page_img: np.ndarray,
    option_bboxes: list,
    page_h: int,
    page_w: int,
) -> list[int]:
    """Tick xanh theo từng dòng đáp án (bbox OCR)."""
    correct: list[int] = []
    for i, bbox in enumerate(option_bboxes):
        if not bbox:
            continue
        y0 = max(0, int(bbox[1] / 1000 * page_h) - 12)
        y1 = min(page_h, int(bbox[3] / 1000 * page_h) + 12)
        x1 = min(page_w, int(page_w * 0.38))
        if y1 <= y0:
            continue
        strip = page_img[y0:y1, 0:x1]
        if strip.size == 0:
            continue
        if green_check_centroids(strip):
            correct.append(i)
    return correct


def detect_correct_on_page(
    page_img: np.ndarray, option_bboxes: list[list], page_h: int
) -> list[int]:
    centers = []
    for bbox in option_bboxes:
        if not bbox:
            centers.append(0)
            continue
        cy = int((bbox[1] + bbox[3]) / 2000 * page_h)
        centers.append(cy)
    if not centers:
        return []
    return detect_correct_option_indices(centers, page_img)


def build_image_options(
    blocks: list[dict],
    ocr_dir: Path,
    page_img: np.ndarray,
    page_h: int,
    page_w: int,
) -> list[dict]:
    """Kiểu B: mỗi ảnh MinerU = một đáp án."""
    imgs = [
        b
        for b in blocks
        if b.get("type") == "image" and b.get("img_path")
    ]
    imgs.sort(key=lambda b: ((b.get("bbox") or [0, 0, 0, 0])[1], (b.get("bbox") or [0])[0]))
    if len(imgs) < 2:
        return []

    assets = OUT_DIR / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    options: list[dict] = []
    bboxes: list[list[float] | None] = []

    for b in imgs:
        img_path = str(b.get("img_path", ""))
        name = Path(img_path).name
        src = ocr_dir / img_path.replace("/", "\\")
        if src.exists():
            shutil.copy2(src, assets / name)
        oid = chr(65 + len(options))
        options.append(
            {
                "id": oid,
                "text": f"Lựa chọn {oid}",
                "imageUrl": f"/quiz-visual/assets/{name}",
                "isCorrect": False,
            }
        )
        bboxes.append(b.get("bbox"))

    correct_idx = detect_correct_per_row(page_img, bboxes, page_h, page_w)
    if not correct_idx:
        correct_idx = detect_correct_on_page(page_img, bboxes, page_h)
    for i in correct_idx:
        if 0 <= i < len(options):
            options[i]["isCorrect"] = True
    return options


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


def build_question(
    g: dict,
    doc: fitz.Document,
    ocr_dir: Path,
    page_bounds: dict[str, tuple[float, float]] | None = None,
) -> dict | None:
    page_idx = int(g["page_idx"])
    raw_blocks = g.get("blocks") or []
    blocks = blocks_on_page(raw_blocks, page_idx)
    seen = {id(b) for b in blocks}
    for b in raw_blocks:
        if b.get("type") == "image" and id(b) not in seen:
            blocks.append(b)
            seen.add(id(b))
    page_bounds = page_bounds or {}
    prompt, option_blocks = split_prompt_options(blocks)
    prompt = clean_prompt_text(prompt)

    page = doc[page_idx]
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat)
    page_img = np.array(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
    page_h = pix.height
    page_w = pix.width
    yn_mode = yesno_label_mode(prompt) if is_yesno_prompt(prompt) else None

    key = f"{g['topic']}|{g['testId']}|{g['index']}"
    image_kind = g.get("_image_kind") or classify_image_kind(
        key, prompt, int(g.get("_md_images") or 0), normalize_vn
    )

    qtype_hint = classify_type(prompt)
    options = []
    bboxes = []

    if use_option_images_only(image_kind):
        img_opts = build_image_options(blocks, ocr_dir, page_img, page_h, page_w)
        if len(img_opts) >= 2:
            options = img_opts
            bboxes = []

    if qtype_hint == "yesno":
        for i, it in enumerate(
            build_yesno_options(
                option_blocks, page_img, page_h, page_w, yn_mode or "co-khong"
            )
        ):
            oid = chr(65 + i)
            options.append(
                {
                    "id": oid,
                    "text": it["text"],
                    "imageUrl": None,
                    "isCorrect": it["isCorrect"],
                }
            )
            if it.get("bbox"):
                bboxes.append(it["bbox"])
    elif not options:
        for ob in option_blocks:
            t = clean_option_text((ob.get("text") or "").strip())
            if len(t) < 2 or is_junk_option(t):
                continue
            if INSTRUCTION_ONLY_RE.match(t):
                continue
            oid = chr(65 + len(options))
            bbox = ob.get("bbox")
            bboxes.append(bbox)
            options.append(
                {
                    "id": oid,
                    "text": t,
                    "imageUrl": None,
                    "isCorrect": False,
                }
            )

    if (
        not options
        and qtype_hint != "yesno"
        and IMAGE_MC_RE.search(normalize_vn(prompt))
    ):
        y_start = int(page_h * 0.22)
        crop = page_img[y_start:, :]
        n_opts = 4
        correct_idx = detect_correct_on_crop(crop, n_opts)
        band_h = crop.shape[0] / n_opts
        for i in range(n_opts):
            oid = chr(65 + i)
            options.append(
                {
                    "id": oid,
                    "text": f"Lựa chọn {oid}",
                    "imageUrl": None,
                    "isCorrect": i in correct_idx,
                }
            )
            bboxes.append(
                [40, int((y_start + i * band_h) / page_h * 1000),
                 900, int((y_start + (i + 1) * band_h) / page_h * 1000)]
            )

    text_option_count = len(options)
    skip_extra_images = image_kind == "C_ui_screenshot_context" and text_option_count >= 2

    if not use_option_images_only(image_kind) and not skip_extra_images:
        for b in blocks:
            if b.get("type") != "image":
                continue
            img_path = b.get("img_path", "")
            if not img_path:
                continue
            name = Path(img_path).name
            assets = OUT_DIR / "assets"
            assets.mkdir(parents=True, exist_ok=True)
            src = ocr_dir / img_path.replace("/", "\\")
            if src.exists():
                shutil.copy2(src, assets / name)
            oid = chr(65 + len(options))
            options.append(
                {
                    "id": oid,
                    "text": f"Lựa chọn {oid}",
                    "imageUrl": f"/quiz-visual/assets/{name}",
                    "isCorrect": False,
                }
            )

    if not prompt and not options:
        return None

    if is_junk_question(prompt, options):
        return None

    hide_snapshot = False
    if key in CURATED:
        c = CURATED[key]
        if c.get("prompt"):
            prompt = c["prompt"]
        hide_snapshot = bool(c.get("hideSnapshot"))
        if "snapshotUrl" in c and c.get("snapshotUrl") is None:
            hide_snapshot = True
        if c.get("options"):
            prev_by_id = {o["id"]: o for o in options if o.get("imageUrl")}
            options = []
            correct_ids = c.get("correct", [])
            for o in c["options"]:
                if "correct" in o:
                    is_ok = bool(o["correct"])
                elif isinstance(correct_ids, list) and correct_ids:
                    is_ok = o["id"] in correct_ids
                else:
                    is_ok = False
                img_url = o.get("imageUrl") or prev_by_id.get(o["id"], {}).get(
                    "imageUrl"
                )
                options.append(
                    {
                        "id": o["id"],
                        "text": o["text"],
                        "imageUrl": img_url,
                        "isCorrect": is_ok,
                    }
                )
        elif c.get("correctIndices") and options:
            for i in c["correctIndices"]:
                if 0 <= i < len(options):
                    options[i]["isCorrect"] = True
        elif c.get("correct") and options:
            for o in options:
                if o["id"] in c["correct"]:
                    o["isCorrect"] = True
        qtype = c.get("type", classify_type(prompt))
        if c.get("yesNoMode"):
            yn_mode = c["yesNoMode"]
        elif qtype == "yesno":
            yn_mode = yesno_label_mode(prompt)
    else:
        qtype = classify_type(prompt)
        if qtype != "yesno":
            correct_idx = detect_correct_per_row(
                page_img, bboxes, page_h, page_w
            )
            if not correct_idx:
                correct_idx = detect_correct_on_page(page_img, bboxes, page_h)
        else:
            correct_idx = []
        if not correct_idx and options and qtype != "yesno":
            # Fallback: crop toàn câu
            all_bb = [bb for bb in bboxes if bb]
            if all_bb:
                ux0 = min(b[0] for b in all_bb)
                uy0 = min(b[1] for b in all_bb) - 60
                ux1 = max(b[2] for b in all_bb)
                uy1 = max(b[3] for b in all_bb) + 30
                union = [max(0, ux0), max(0, uy0), min(1000, ux1), min(1000, uy1)]
            else:
                union = [50, 80, 950, 900]
            x0, y0, x1, y1 = bbox_to_pixels(union, pix.width, pix.height, pad=14)
            crop = page_img[y0:y1, x0:x1]
            correct_idx = detect_correct_on_crop(crop, len(options))
        for i in correct_idx:
            if 0 <= i < len(options):
                options[i]["isCorrect"] = True

    if qtype not in ("yesno", "matching") and options:
        cap_correct_by_prompt(prompt, options)
        qtype = infer_mc_type(qtype, prompt, options)

    if qtype == "single" and len(options) < 2:
        if not prompt:
            return None

    if qtype == "yesno" and len(options) < 1:
        return None

    if qtype == "multiple" and len(options) < 2:
        return None

    snapshot_url: str | None = None
    attach_snap = should_attach_snapshot(
        prompt, qtype, image_kind, hide_snapshot
    )

    if attach_snap:
        snap = f"q_{g['topic']}_{g['testId']}_{g['index']}.jpg"
        (OUT_DIR / "assets").mkdir(parents=True, exist_ok=True)
        snap_path = OUT_DIR / "assets" / snap
        use_mineru_copy = image_kind in (
            "A_single_illustration",
            "C_ui_screenshot_context",
        )
        used_mineru_img = (
            copy_illustration_snapshot(blocks, ocr_dir, snap_path)
            if use_mineru_copy
            else False
        )
        snap_blocks = content_blocks_for_snapshot(blocks)
        if used_mineru_img:
            crop_img = Image.open(snap_path).convert("RGB")
        else:
            union = (
                snapshot_bbox_for_group(snap_blocks, prompt)
                if image_kind == "C_ui_screenshot_context"
                else snapshot_bbox_for_question(g, snap_blocks, prompt, page_bounds)
            )
            x0, y0, x1, y1 = bbox_to_pixels(union, pix.width, pix.height, pad=8)
            crop_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).crop(
                (x0, y0, x1, y1)
            )
            crop_img.save(snap_path, quality=88)
        snapshot_url = f"/quiz-visual/assets/{snap}"
        if qtype not in ("yesno", "matching") and options:
            has_any = any(o["isCorrect"] for o in options)
            if not has_any:
                snap_arr = np.array(crop_img)
                snap_correct = detect_correct_on_crop(snap_arr, len(options))
                for i in snap_correct:
                    if 0 <= i < len(options):
                        options[i]["isCorrect"] = True
                if qtype not in ("yesno", "matching"):
                    qtype = infer_mc_type(qtype, prompt, options)

    out: dict = {
        "id": str(uuid.uuid4()),
        "topic": g["topic"],
        "testId": g["testId"],
        "prompt": prompt,
        "type": qtype,
        "imageKind": image_kind if image_kind != "none" else None,
        "snapshotUrl": snapshot_url,
        "page": page_idx + 1,
        "indexInTest": g["index"],
        "totalInTest": g["total"],
        "options": options,
        "images": [o["imageUrl"] for o in options if o.get("imageUrl")],
    }
    if qtype == "yesno" and yn_mode:
        out["yesNoMode"] = yn_mode
    return out


def dedupe(questions: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for q in questions:
        key = f"{q['topic']}|{q['testId']}|{q['indexInTest']}"
        prev = best.get(key)
        if prev is None:
            best[key] = q
            continue
        score = len(q["options"]) + (50 if q.get("prompt") else 0)
        prev_score = len(prev["options"]) + (50 if prev.get("prompt") else 0)
        if score > prev_score:
            best[key] = q
    return sorted(
        best.values(),
        key=lambda x: (x["topic"], x["testId"], x.get("indexInTest", 0)),
    )


def main():
    cl_path = OCR_DIR / "ic3_unlocked_content_list.json"
    if not cl_path.exists():
        print("Missing MinerU output:", cl_path)
        return 1

    blocks = json.loads(cl_path.read_text(encoding="utf-8"))
    groups = group_questions(blocks)
    page_bounds = build_page_y_bounds(groups)
    md_counts = md_image_counts_for_groups(groups, Q_RE, parse_topic)
    for g in groups:
        enrich_group_blocks(g, blocks, page_bounds)
        key = question_key(g)
        g["_md_images"] = md_counts.get(key, 0)
        g["_image_kind"] = classify_image_kind(
            key, "", g["_md_images"], normalize_vn
        )
    doc = fitz.open(PDF_PATH)

    questions = []
    for g in groups:
        prompt_preview, _ = split_prompt_options(
            blocks_on_page(g.get("blocks") or [], int(g["page_idx"]))
        )
        key = question_key(g)
        g["_image_kind"] = classify_image_kind(
            key, clean_prompt_text(prompt_preview), g.get("_md_images", 0), normalize_vn
        )
        q = build_question(g, doc, OCR_DIR, page_bounds)
        if not q:
            continue
        if not q["options"] and not q["prompt"]:
            continue
        if q["type"] == "single" and len(q["options"]) == 1:
            if not q["prompt"]:
                continue
        questions.append(q)

    doc.close()
    questions = dedupe(questions)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 3,
        "source": "rebuild_from_mineru v5 — ảnh A/B/C theo pdf-image-rules",
        "total": len(questions),
        "questions": questions,
    }
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    multi = sum(1 for q in questions if q["type"] == "multiple")
    match = sum(1 for q in questions if q["type"] == "matching")
    yesno = sum(1 for q in questions if q["type"] == "yesno")
    print(f"Rebuilt {len(questions)} questions -> {OUT_JSON}")
    print(f"  single/multiple/matching/yesno: "
          f"{len(questions) - multi - match - yesno}/{multi}/{match}/{yesno}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
