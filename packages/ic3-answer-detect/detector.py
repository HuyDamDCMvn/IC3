"""Nhận diện dấu tick xanh (đáp án đúng) trên ảnh câu hỏi IC3 Review."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def load_image_rgb(path: str | Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def green_check_centroids(
    img_rgb: np.ndarray, max_x_ratio: float = 0.42
) -> list[tuple[int, int]]:
    """
    Trả về tọa độ (y, x) các tick xanh bên trái đáp án.
    Khớp quy ước PDF ôn thi: tick xanh = đúng, đỏ = sai.
    """
    g = img_rgb[:, :, 1].astype(int)
    r = img_rgb[:, :, 0].astype(int)
    b = img_rgb[:, :, 2].astype(int)
    mask = (g > 140) & (g > r + 35) & (g > b + 35) & (r < 130) & (g < 230)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return []

    w = img_rgb.shape[1]
    max_x = max(80, int(w * max_x_ratio))
    points = sorted(zip(ys.tolist(), xs.tolist()), key=lambda p: p[0])
    clusters: list[list[tuple[int, int]]] = []
    for y, x in points:
        if x > max_x:
            continue
        if not clusters or abs(y - clusters[-1][0][0]) > 25:
            clusters.append([(y, x)])
        else:
            clusters[-1].append((y, x))

    centroids: list[tuple[int, int]] = []
    for cl in clusters:
        cy = int(sum(p[0] for p in cl) / len(cl))
        cx = int(sum(p[1] for p in cl) / len(cl))
        if cx < max_x:
            centroids.append((cy, cx))
    return centroids


def row_dropdown_is_yes(
    img_rgb: np.ndarray,
    bbox: list[float],
    page_h: int,
    page_w: int,
    label_width_ratio: float = 0.18,
) -> bool | None:
    """
    Vùng dropdown bên trái mỗi dòng (Đúng/Sai hoặc Có/Không).
    Chữ xanh lá = đáp án đúng là Đúng/Có; chữ đỏ = đáp án đúng là Sai/Không.
    """
    if not bbox or page_h <= 0 or page_w <= 0:
        return None
    y0 = max(0, int(bbox[1] / 1000 * page_h) - 2)
    y1 = min(page_h, int(bbox[3] / 1000 * page_h) + 2)
    x1 = max(40, int(page_w * label_width_ratio))
    if y1 <= y0:
        return None
    crop = img_rgb[y0:y1, 0:x1]
    if crop.size == 0:
        return None

    g = crop[:, :, 1].astype(int)
    r = crop[:, :, 0].astype(int)
    b = crop[:, :, 2].astype(int)
    green = (g > 130) & (g > r + 28) & (g > b + 28) & (r < 140)
    red = (r > 140) & (r > g + 35) & (g < 110) & (b < 110)
    green_n = int(green.sum())
    red_n = int(red.sum())
    if green_n < 15 and red_n < 15:
        return None
    if red_n > green_n * 1.15 and red_n >= 20:
        return False
    if green_n >= 20:
        return True
    return None


def detect_correct_option_indices(
    option_centers_y: list[int],
    img_rgb: np.ndarray,
    tolerance: int = 35,
) -> list[int]:
    """
    Với mỗi đáp án có tọa độ Y (từ OCR/layout), trả về index đáp án có tick xanh.
    """
    green_ys = [c[0] for c in green_check_centroids(img_rgb)]
    correct: list[int] = []
    for i, oy in enumerate(option_centers_y):
        if any(abs(oy - gy) < tolerance for gy in green_ys):
            correct.append(i)
    return correct
