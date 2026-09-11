from __future__ import annotations

import base64
import io
from collections import Counter
from dataclasses import dataclass

from PIL import Image


@dataclass(frozen=True)
class Segment:
    start: int
    end: int


def match_slider_offset(small_img_b64: str, big_img_b64: str) -> tuple[bool, int]:
    small_img = _decode_base64_image(small_img_b64)
    big_img = _decode_base64_image(big_img_b64)

    sw, sh = small_img.size
    resized = big_img.resize((max(big_img.width // 2, 1), max(big_img.height // 2, 1)), Image.Resampling.NEAREST).convert("RGB")
    w, h = resized.size
    min_side = max(int(min(sw, sh) * 0.25), 1)
    max_side = max(min_side * 3, int(min(sw, sh) * 0.75))

    # 缺口在缩放图中的边长与滑块块体尺寸一致（约为其一半）。以其为硬约束，
    # 避免背景中"更大、更平坦的同色区域"盖过真实缺口而返回错误偏移。
    target_side = max(_piece_side(small_img) // 2, 1)
    tolerance = max(2, target_side // 10)

    color_ids: list[list[int]] = []
    counter: Counter[int] = Counter()
    pixels = resized.load()
    for y in range(h):
        row: list[int] = []
        for x in range(w):
            r, g, b = pixels[x, y]
            color_id = (r // 4 * 4) + (g // 4 * 4) * 256 + (b // 4 * 4) * 65536
            row.append(color_id)
            counter[color_id] += 1
        color_ids.append(row)

    best_area = 0
    best_x = 0
    fallback_area = 0
    fallback_x = 0
    for color, _count in counter.most_common(5):
        col_run = [[0 for _ in range(w)] for _ in range(h)]
        for x in range(w):
            if color_ids[0][x] == color:
                col_run[0][x] = 1
        for y in range(1, h):
            for x in range(w):
                if color_ids[y][x] == color:
                    col_run[y][x] = col_run[y - 1][x] + 1

        for y in range(min_side, h):
            row = [col_run[y][x] >= min_side for x in range(w)]
            if not any(row):
                continue
            for seg in _true_runs(row):
                run_w = seg.end - seg.start
                if seg.start <= sw // 4:
                    continue
                run_h = col_run[y][seg.start]
                if run_h <= 0:
                    continue
                ratio = run_w / run_h
                if not 0.7 < ratio < 1.4:
                    continue
                area = run_w * run_h
                # 宽松回退：保留原有"最大近方形同色块"行为，避免尺寸约束过严时漏检。
                if run_w <= max_side and area > fallback_area:
                    fallback_area = area
                    fallback_x = seg.start
                # 严格命中：宽高都贴合滑块块体的实际尺寸。
                if (
                    abs(run_w - target_side) <= tolerance
                    and abs(run_h - target_side) <= tolerance
                    and area > best_area
                ):
                    best_area = area
                    best_x = seg.start

    if best_area:
        return True, best_x * 2
    if fallback_area:
        return True, fallback_x * 2
    return False, 0


def _piece_side(small_img: Image.Image) -> int:
    """滑块块体的实际边长：优先取不透明内容的包围盒。"""
    if small_img.mode in ("RGBA", "LA"):
        bbox = small_img.getchannel("A").getbbox()
        if bbox:
            return max(bbox[2] - bbox[0], bbox[3] - bbox[1])
    return min(small_img.size)


def _decode_base64_image(value: str) -> Image.Image:
    marker = ";base64,"
    if marker in value:
        value = value.split(marker, 1)[1]
    data = base64.b64decode(value)
    return Image.open(io.BytesIO(data))


def _true_runs(row: list[bool]) -> list[Segment]:
    segments: list[Segment] = []
    in_run = False
    start = 0
    for index, value in enumerate(row):
        if value and not in_run:
            start = index
            in_run = True
        elif not value and in_run:
            segments.append(Segment(start, index))
            in_run = False
    if in_run:
        segments.append(Segment(start, len(row)))
    return segments
