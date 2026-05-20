"""Chuẩn hóa chữ OCR tiếng Việt (MinerU/PDF) trước khi regex và lọc câu."""
from __future__ import annotations

import re
import unicodedata

# Ký tự OCR lệch → ASCII/VN chuẩn (thường gặp trong MinerU)
_OCR_CHAR_MAP = str.maketrans(
    {
        "\u1ecd": "o",  # ơ hook
        "\u1ecb": "i",
        "\u1ec7": "e",
        "\u1ec5": "e",
        "\u1ec3": "e",
        "\u1ec1": "e",
        "\u1ebf": "e",
        "\u1eb9": "e",
        "\u1ea3": "a",
        "\u1ea1": "a",
        "\u1ea7": "a",
        "\u1ea5": "a",
        "\u01b0": "u",
        "\u01a1": "o",
        "\u0111": "d",
        "\u0110": "D",
        "\u0300": "",
        "\u0301": "",
        "\u0303": "",
        "\u0309": "",
        "\u0323": "",
    }
)

JUNK_PROMPT_RE = re.compile(
    r"hu[oơ]ng\s*d[ăaâ]n\s*on\s*thi|ic3\s*gs6\s*spark|ngu[oô]n\s*tai\s*lieu|"
    r"hoc\s*sinh\s*chu\s*y.*dap\s*an",
    re.I,
)
JUNK_OPTION_RE = re.compile(
    r"ngu[oô]n\s*tai\s*lieu|iig\s*viet|ic3\s*review|dap\s*an\s*dung\s*la\s*dau|"
    r"hoc\s*sinh\s*chu\s*y|check\s*mau\s*xanh|mau\s*xanh\s*green",
    re.I,
)
INSTRUCTION_ONLY_RE = re.compile(
    r"^(resources|question\s+\d+)", re.I
)


def normalize_vn(text: str) -> str:
    if not text:
        return ""
    s = text.translate(_OCR_CHAR_MAP)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = unicodedata.normalize("NFC", s)
    return s


def clean_option_text(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^[O○●◯]\s+", "", t, flags=re.I)
    t = re.sub(r"^[●◦]\s*", "", t)
    return t.strip()


def clean_prompt_text(prompt: str) -> str:
    p = (prompt or "").strip()
    norm = normalize_vn(p)
    if JUNK_PROMPT_RE.search(norm) and len(norm) > 80:
        m = re.search(
            r"(ban\s|em\s|hay\s|tuy\s|chon\s|máy\s|một\s|ghép|kéo|"
            r"di\s+chuy|doi\s|phương|thuật|mỗi\s)",
            norm,
            re.I,
        )
        if m and m.start() > 10:
            p = p[m.start():]
    return p.strip()


def is_junk_option(text: str) -> bool:
    return bool(JUNK_OPTION_RE.search(normalize_vn(text)))


def is_junk_question(prompt: str, options: list[dict]) -> bool:
    norm = normalize_vn(prompt)
    if JUNK_PROMPT_RE.search(norm) and not re.search(
        r"\?\s*$|chon\s*[23]|\(chon", norm
    ):
        return True
    junk_opts = sum(
        1 for o in options if is_junk_option(o.get("text", ""))
    )
    if junk_opts >= 2:
        return True
    return False
