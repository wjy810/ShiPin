"""把生图（AI 原图，1672×941 / 1254×1254 PNG）处理成片子里用的 JPEG。

- 黑底发光的图（花纹、光斑、鹦鹉螺、指纹、夜景、金色 1、卡片插画）：先把黑位压到纯黑（低于阈值的亮度归零、其余线性拉开），
  再按亮度抠成带透明通道的 WebP：alpha = max(R,G,B)，颜色 = 原色 / alpha。这样用普通叠放画上去，效果和“滤色（screen）”几乎一样，
  而且不受图层隔离影响（场景外层有不透明度 / 模糊动画，会把 mix-blend-mode 隔离在场景内部，黑底会露成方框）。
- 当背景用的图：只缩放，不改颜色；暗化由画面上的不透明度控制。
- 尺寸：16:9 的放大到 1920×1080（LANCZOS，约 1.15 倍），方图按用途缩小。

用法：python3 scripts/prep_images.py <原图目录>      （在 v2/ 目录下，需要 Pillow、numpy）
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "images" / "ai"

# 文件名: (原图, 尺寸, 黑位阈值 0–255；None 表示不压黑、不抠图，输出普通 JPEG)
JOBS = {
    "rosette.webp": ("rosette-a.png", (1200, 1200), 14),
    "guilloche.webp": ("guilloche-wide-a.png", (1920, 1080), 14),
    "flare.webp": ("flare-a.png", (1920, 1080), 6),
    "study-1881.jpg": ("study-1881-a.png", (1920, 1080), None),
    "lab-1938.jpg": ("lab-1938-a.png", (1920, 1080), None),
    "nautilus.webp": ("nautilus-a.png", (1920, 1080), 12),
    "slide-rule.jpg": ("slide-rule-a.png", (1920, 1080), None),
    "earth-night.webp": ("earth-night-b.png", (1920, 1080), 8),
    "fingerprint.webp": ("fingerprint-a.png", (1000, 1000), 14),
    "sieve.webp": ("sieve-a.png", (640, 640), 10),
    "one-gold.webp": ("one-gold-a.png", (1920, 1080), 10),
    "paper.jpg": ("paper-a.png", (600, 800), None),
    # v3 新增
    "nebula.webp": ("nebula-a.png", (1920, 1080), 10),
    "burst.webp": ("burst-a.png", (1000, 1000), 10),
    **{f"ce-{k}.webp": (f"ce-{k}.png", (400, 400), 14) for k in ["height", "exam", "phone"]},
    **{f"icon-{k}.webp": (f"icon-{k}.png", (400, 400), 14)
       for k in ["river", "town", "pendulum", "newspaper", "molecule", "atom", "doors", "hourglass"]},
}


def crush(im, t):
    a = np.asarray(im).astype(np.float32)
    a = np.clip((a - t) * 255.0 / (255.0 - t), 0, 255)
    return Image.fromarray(a.round().astype(np.uint8))


def keyed(im):
    """黑底 → 透明：alpha = max(R,G,B)，颜色反预乘。"""
    a = np.asarray(im).astype(np.float32) / 255.0
    alpha = a.max(axis=2, keepdims=True)
    rgb = np.where(alpha > 1e-3, a / np.maximum(alpha, 1e-3), 0)
    out = np.concatenate([rgb, alpha], axis=2)
    return Image.fromarray((np.clip(out, 0, 1) * 255).round().astype(np.uint8), "RGBA")


def main():
    src = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (raw, size, t) in JOBS.items():
        im = Image.open(src / raw).convert("RGB")
        if abs(im.width / im.height - size[0] / size[1]) > 0.02:  # 比例不同时居中裁切
            r = size[0] / size[1]
            w, h = (im.width, round(im.width / r)) if im.width / im.height < r else (round(im.height * r), im.height)
            im = im.crop(((im.width - w) // 2, (im.height - h) // 2, (im.width + w) // 2, (im.height + h) // 2))
        im = im.resize(size, Image.LANCZOS)
        if t is not None:
            im = keyed(crush(im, t))
            im.save(OUT / name, quality=90, alpha_quality=95, method=6)
        else:
            im.save(OUT / name, quality=90, optimize=True, progressive=True)
        corner = np.asarray(im)[:24, :24, -1 if t is not None else 0].mean()
        print(f"{name:22s} {size[0]}×{size[1]}  角落亮度 {corner:5.1f}  {(OUT / name).stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
