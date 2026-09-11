from __future__ import annotations

import base64
import io
import unittest

from PIL import Image, ImageDraw

from icpquery_mcp.core.captcha import _piece_side, match_slider_offset


def _encode(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _build_pair(decoy: tuple[int, int, int, int] | None, gap: tuple[int, int, int, int] | None) -> tuple[str, str]:
    """构造 500x190 大图 + 70x70 RGBA 滑块图。

    decoy/gap 为矩形 [x0, y0, x1, y1]；50x100 的干扰块缩放后为 50x50（面积 2500），
    大于真缺口 34x34（面积 1156），用于复现"被更大同色块带偏"的缺陷。
    """
    big = Image.new("RGB", (500, 190), (255, 255, 255))
    draw = ImageDraw.Draw(big)
    if decoy is not None:
        draw.rectangle(list(decoy), fill=(0, 0, 128))
    if gap is not None:
        draw.rectangle(list(gap), fill=(0, 0, 0))

    small = Image.new("RGBA", (70, 70), (0, 0, 0, 0))
    ImageDraw.Draw(small).rectangle([0, 0, 67, 67], fill=(0, 0, 0, 255))
    return _encode(small), _encode(big)


class SliderOffsetTests(unittest.TestCase):
    def test_piece_side_uses_opaque_bbox(self) -> None:
        small = Image.new("RGBA", (70, 70), (0, 0, 0, 0))
        ImageDraw.Draw(small).rectangle([0, 0, 67, 67], fill=(0, 0, 0, 255))

        self.assertEqual(_piece_side(small), 68)

    def test_prefers_gap_over_larger_decoy(self) -> None:
        # 干扰块缩放后 50x50（面积 2500）> 真缺口 34x34（面积 1156），
        # 且起始 x 满足 seg.start > sw//4 守卫；旧算法会误选它并返回 60。
        small_b64, big_b64 = _build_pair(decoy=(60, 40, 160, 140), gap=(180, 60, 248, 128))

        matched, offset = match_slider_offset(small_b64, big_b64)

        self.assertTrue(matched)
        self.assertEqual(offset, 180)

    def test_falls_back_to_largest_near_square_when_no_sized_candidate(self) -> None:
        # 无符合 piece 尺寸的候选时应保留旧的"最大近方形"行为，避免漏检。
        small_b64, big_b64 = _build_pair(decoy=(60, 40, 160, 140), gap=None)

        matched, offset = match_slider_offset(small_b64, big_b64)

        self.assertTrue(matched)
        self.assertEqual(offset, 60)


if __name__ == "__main__":
    unittest.main()
