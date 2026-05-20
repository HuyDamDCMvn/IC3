"""Thư viện nhận diện đáp án đúng (tick xanh) từ ảnh/screenshot IC3 Review."""

from .detector import (
    detect_correct_option_indices,
    green_check_centroids,
    load_image_rgb,
)

__all__ = [
    "detect_correct_option_indices",
    "green_check_centroids",
    "load_image_rgb",
]
