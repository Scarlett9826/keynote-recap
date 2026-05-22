#!/usr/bin/env python3
"""帧画面评分器：判断一张图是否是「PPT/产品 demo」（高分）还是「演讲者特写/会场远景/过场」（低分）。

只用 PIL，不依赖 OpenCV。

评分维度：
- 文字/图表密度 (锐利边缘): 0~40
- 大色块占比 (PPT 纯色背景): 0~20
- 信息密度 (颜色丰富度): 0~20
- 肤色占比 (演讲者): -100 ~ 0
- 单一颜色占比 (过场): -50 ~ 0
- 会场远景 (低饱和度 + 大量观众/座椅特征): -30 ~ 0

Usage (test):
    python frame_scorer.py <image_path>            # 给单张图打分并解释
    python frame_scorer.py <dir>                   # 给整个目录每张图打分
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


def is_skin_color(r: int, g: int, b: int) -> bool:
    """收紧的肤色检测：排除大量暖色调误报（米色 PPT 背景、木头、舞台）。

    人脸肤色特征：
    - 红 > 绿 > 蓝（明显梯度）
    - 不能太亮（PPT 米色背景接近 250）
    - 不能太暗（舞台阴影）
    - 红绿差 / 红蓝差有特定比例
    """
    # 太亮（接近白/米色 PPT 背景）
    if r > 220 and g > 200 and b > 180:
        return False
    # 太暗
    if r < 80 or g < 50 or b < 30:
        return False
    # 必须 R > G > B
    if not (r > g > b):
        return False
    # 红绿差应该 15~50 之间（典型肤色）
    rg = r - g
    if rg < 15 or rg > 60:
        return False
    # 绿蓝差 5~50
    gb = g - b
    if gb < 5 or gb > 55:
        return False
    # 红蓝差 25~100
    rb = r - b
    if rb < 25 or rb > 110:
        return False
    # YCbCr 严格范围
    cb = -0.169 * r - 0.331 * g + 0.500 * b + 128
    cr = 0.500 * r - 0.419 * g - 0.081 * b + 128
    return 80 <= cb <= 120 and 135 <= cr <= 170


def edge_density(img: Image.Image) -> float:
    """边缘密度（0~1）。文字/图表密集时这个值高。"""
    # 转灰度，过滤边缘
    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    # 计算高于阈值的像素比例
    pixels = list(edges.getdata())
    high = sum(1 for p in pixels if p > 40)
    return high / len(pixels)


def skin_ratio_center(img: Image.Image, sample_step: int = 3) -> float:
    """画面**正中央 35%** 区域的肤色占比。
    演讲者特写中央肤色 > 25%；PPT 里的小演讲者剪影 < 5%。"""
    w, h = img.size
    cx0, cy0 = int(w * 0.32), int(h * 0.30)
    cx1, cy1 = int(w * 0.68), int(h * 0.85)
    rgb = img.convert("RGB")
    total = 0
    skin = 0
    for y in range(cy0, cy1, sample_step):
        for x in range(cx0, cx1, sample_step):
            r, g, b = rgb.getpixel((x, y))
            total += 1
            if is_skin_color(r, g, b):
                skin += 1
    return skin / total if total else 0


def skin_ratio_global(img: Image.Image, sample_step: int = 4) -> float:
    """**全图**肤色占比。观众席远景全图 > 25%；普通 PPT < 8%。"""
    w, h = img.size
    rgb = img.convert("RGB")
    total = 0
    skin = 0
    for y in range(0, h, sample_step):
        for x in range(0, w, sample_step):
            r, g, b = rgb.getpixel((x, y))
            total += 1
            if is_skin_color(r, g, b):
                skin += 1
    return skin / total if total else 0


def skin_ratio(img: Image.Image, sample_step: int = 4) -> float:
    """兼容旧调用（保留接口名）。"""
    return skin_ratio_center(img, sample_step)


def dominant_color_ratio(img: Image.Image) -> float:
    """最大色块占整图比例（量化到 16 色）。"""
    small = img.resize((80, 45)).convert("RGB").quantize(colors=16)
    pixels = list(small.getdata())
    counts: dict[int, int] = {}
    for p in pixels:
        counts[p] = counts.get(p, 0) + 1
    if not counts:
        return 0
    return max(counts.values()) / len(pixels)


def color_richness(img: Image.Image) -> float:
    """色彩丰富度（不同颜色数量 / 像素数）。PPT 鲜艳时较高。"""
    small = img.resize((80, 45)).convert("RGB")
    return len(set(small.getdata())) / (80 * 45)


def saturation_mean(img: Image.Image) -> float:
    """平均饱和度（0~255 范围）。"""
    hsv = img.convert("HSV")
    s = hsv.split()[1]
    return ImageStat.Stat(s).mean[0]


def brightness_std(img: Image.Image) -> float:
    """亮度标准差。文字密集图通常较高。"""
    gray = img.convert("L")
    return ImageStat.Stat(gray).stddev[0]


def score_image(img_path: str, verbose: bool = False) -> dict:
    img = Image.open(img_path).convert("RGB")
    # 缩小以加速
    img.thumbnail((640, 360))

    metrics = {
        "edge_density": edge_density(img),
        "skin_ratio": skin_ratio_center(img),
        "skin_ratio_global": skin_ratio_global(img),
        "dominant_color": dominant_color_ratio(img),
        "color_richness": color_richness(img),
        "saturation": saturation_mean(img),
        "brightness_std": brightness_std(img),
    }

    score = 0.0
    breakdown = {}

    # 1) 边缘密度 (文字/图表) → 0~40
    e = metrics["edge_density"]
    edge_pts = min(40, e * 400)  # 0.1 → 40
    score += edge_pts
    breakdown["edge_pts"] = edge_pts

    # 2) 信息密度 (色彩丰富度) → 0~20
    cr = metrics["color_richness"]
    rich_pts = min(20, cr * 100)  # 0.2 → 20
    score += rich_pts
    breakdown["rich_pts"] = rich_pts

    # 3) 大色块占比 → 0~20 (PPT 通常 30~60% 是纯色背景)
    dc = metrics["dominant_color"]
    if 0.25 <= dc <= 0.7:
        block_pts = 20
    elif dc < 0.25:
        block_pts = dc * 80  # 0~20
    else:  # > 0.7 太单调（过场）
        block_pts = max(0, (1.0 - dc) * 60)  # 0.7 -> 18, 1.0 -> 0
    score += block_pts
    breakdown["block_pts"] = block_pts

    # 4) 中央肤色占比 → 一票否决
    # 演讲者特写中央 30~70%；PPT 小演讲者剪影 < 8%
    sk = metrics["skin_ratio"]
    if sk > 0.30:
        skin_penalty = -100
    elif sk > 0.20:
        skin_penalty = -70
    elif sk > 0.12:
        skin_penalty = -30
    else:
        skin_penalty = 0
    score += skin_penalty
    breakdown["skin_penalty"] = skin_penalty

    # 5) 极端单调 (过场) → 重罚
    # M4: 用户反馈仍有大量过场被选；之前 0.85 / 0.75 阈值太宽松，加严。
    # PPT 通常 dominant 0.4-0.65（一种背景色 + 各种 UI 元素）；过场页 0.7+。
    if dc > 0.80:
        mono_penalty = -120     # was -50; bump to "definitely rejected"
    elif dc > 0.70:
        mono_penalty = -50      # was -20
    elif dc > 0.65:
        mono_penalty = -15      # new tier
    else:
        mono_penalty = 0
    score += mono_penalty
    breakdown["mono_penalty"] = mono_penalty

    # 5b) 「纯标题页 / slogan」检测：低边缘密度 + 大色块 + 少颜色
    # 特征：1-3 个大字 + 渐变背景。edge 低（无表格无图）+ dc 高 + cr 极低。
    if (
        e < 0.05               # very few edges (no graph/table)
        and dc > 0.55          # large dominant color block
        and metrics["color_richness"] < 0.20  # few unique colors
        and metrics["brightness_std"] < 60    # low contrast
    ):
        slogan_penalty = -80
    else:
        slogan_penalty = 0
    score += slogan_penalty
    breakdown["slogan_penalty"] = slogan_penalty

    # 6) 远景会场（饱和度低 + 边缘密度也低 + 亮度方差中等）
    if metrics["saturation"] < 50 and e < 0.04 and 30 < metrics["brightness_std"] < 70:
        venue_penalty = -30
    else:
        venue_penalty = 0
    score += venue_penalty
    breakdown["venue_penalty"] = venue_penalty

    # 7) 观众席远景（高纹理 + 高色彩噪声 + 中央肤色不高）
    #    特征：edge_density 高（密集人头），但色彩极其杂乱（color_richness 高），
    #    且没有明显大色块（dominant_color 低），中央也没大块肤色
    if (
        e > 0.06
        and metrics["color_richness"] > 0.55
        and metrics["dominant_color"] < 0.18
        and metrics["skin_ratio"] < 0.15
    ):
        crowd_penalty = -90
    else:
        crowd_penalty = 0
    score += crowd_penalty
    breakdown["crowd_penalty"] = crowd_penalty

    return {
        "path": img_path,
        "score": round(score, 1),
        "metrics": {k: round(v, 4) for k, v in metrics.items()},
        "breakdown": {k: round(v, 1) for k, v in breakdown.items()},
    }


def label(score: float) -> str:
    if score >= 50:
        return "✅ PPT/Demo (高质量)"
    if score >= 25:
        return "🟡 可能可用"
    if score >= 0:
        return "⚠️  偏弱"
    return "❌ 排除 (演讲者/过场/会场)"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = Path(sys.argv[1])
    if target.is_dir():
        imgs = sorted(target.glob("*.jpg")) + sorted(target.glob("*.png"))
        for p in imgs:
            r = score_image(str(p))
            print(f"{r['score']:6.1f}  {label(r['score']):25s}  {p.name}")
    else:
        r = score_image(str(target), verbose=True)
        print(f"\n=== {target.name} ===")
        print(f"得分: {r['score']}  {label(r['score'])}\n")
        print("维度指标:")
        for k, v in r["metrics"].items():
            print(f"  {k:18s}: {v}")
        print("\n打分明细:")
        for k, v in r["breakdown"].items():
            print(f"  {k:18s}: {v:+6.1f}")


if __name__ == "__main__":
    main()
