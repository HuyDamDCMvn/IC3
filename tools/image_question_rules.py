"""Quy tắc câu có ảnh (A/B/C) — dùng chung rebuild + analyze."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "data" / "pdf-image-rules.json"
OCR_MD = ROOT / "data" / "mineru_out_full" / "ic3_unlocked" / "ocr" / "ic3_unlocked.md"

PROMPT_IMAGE_NAY = re.compile(r"hinh\s*anh\s*nay", re.I)
PROMPT_OPTIONS_ARE_IMAGES = re.compile(
    r"hinh\s*anh\s*nao\s+sau.*la\s*hinh|"
    r"hai\s+thiet\s+bi\s+nao.*\(chon\s*2\)|"
    r"hinh\s*anh\s*nao\s+duoi",
    re.I,
)
MATCHING = re.compile(r"gh[eé]p|kéo.*sang|di chuy[eê]n t", re.I)
YESNO = re.compile(
    r"chon\s*co|chon\s*dung|phat\s*bieu|dung\s+hoac\s+sai",
    re.I,
)

_KIND_BY_KEY: dict[str, str] | None = None


def _load_kind_map() -> dict[str, str]:
    global _KIND_BY_KEY
    if _KIND_BY_KEY is not None:
        return _KIND_BY_KEY
    out: dict[str, str] = {}
    if RULES_PATH.exists():
        data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        by_kind = data.get("withIllustration", {}).get("byKind", {})
        for kind, keys in by_kind.items():
            for k in keys:
                out[k] = kind
    _KIND_BY_KEY = out
    return out


def md_image_counts_for_groups(groups: list[dict], q_re, parse_topic) -> dict[str, int]:
    if not OCR_MD.exists():
        return {}
    lines = OCR_MD.read_text(encoding="utf-8").splitlines()
    topic = ("topic-1", "test-1")
    secs: list[dict] = []
    cur: dict = {"imgs": 0, "q": 0}
    for line in lines:
        t = line.strip()
        if t:
            topic = parse_topic(t, topic)
        m = q_re.search(t)
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


def classify_image_kind(
    key: str, prompt: str, md_count: int, normalize_vn
) -> str:
    """A = snapshot giữa màn; B = ảnh trên đáp án; C = screenshot; none."""
    mapped = _load_kind_map().get(key)
    if mapped:
        return mapped

    n = normalize_vn(prompt)
    if MATCHING.search(n) or YESNO.search(n):
        return "none"
    if md_count <= 0:
        return "none"
    if PROMPT_IMAGE_NAY.search(n):
        return "A_single_illustration"
    if PROMPT_OPTIONS_ARE_IMAGES.search(n) or (
        md_count >= 2 and re.search(r"hinh\s*anh\s*nao", n, re.I)
    ):
        return "B_options_are_images"
    return "C_ui_screenshot_context"


def should_attach_snapshot(
    kind: str, hide_snapshot: bool, qtype: str
) -> bool:
    if hide_snapshot or qtype in ("yesno", "matching"):
        return False
    if kind == "A_single_illustration":
        return True
    if kind == "C_ui_screenshot_context":
        return True
    return False


def use_option_images_only(kind: str) -> bool:
    return kind == "B_options_are_images"


def images_in_y_band(
    all_blocks: list[dict], page_idx: int, y0: float, y1: float
) -> list[dict]:
    out = []
    for b in all_blocks:
        if b.get("type") != "image" or not b.get("img_path"):
            continue
        if int(b.get("page_idx", -1)) != page_idx:
            continue
        bb = b.get("bbox") or [0, 0, 0, 0]
        cy = (bb[1] + bb[3]) / 2
        if y0 - 25 <= cy <= y1 + 25:
            out.append(b)
    return out


def enrich_group_blocks(
    g: dict,
    all_blocks: list[dict],
    page_bounds: dict[str, tuple[float, float]],
) -> None:
    """Gắn block image MinerU vào nhóm câu (group_questions hay bỏ sót)."""
    key = f"{g['topic']}|{g['testId']}|{g['index']}"
    page_idx = int(g["page_idx"])
    y0, y1 = page_bounds.get(key, (0.0, 1000.0))
    have = {b.get("img_path") for b in g.get("blocks") or [] if b.get("img_path")}
    for b in images_in_y_band(all_blocks, page_idx, y0, y1):
        if b.get("img_path") not in have:
            g.setdefault("blocks", []).append(b)
            have.add(b.get("img_path"))
