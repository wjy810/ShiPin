"""从成片里截每一屏的最后状态，拼成对照表，逐屏看有没有遮挡、错位、多余的东西。

用法：
  python3 endstate_sheet.py 成片.mp4 分镜.md --bpm 128 --out sheets/        # 从分镜里读“全片第 a–b 拍”
  python3 endstate_sheet.py 成片.mp4 --times 4.6 9.3 12.1 --out sheets/     # 直接给时刻

每屏取切点前 3 帧（这一屏所有东西都到位了、下一屏还没进来），每张表 12 屏（4×3），左上角标屏号和秒数。
想看动作过程，就用 --times 给中间时刻。需要 ffmpeg 和 Pillow。
"""

import argparse
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("storyboard", nargs="?")
    ap.add_argument("--bpm", type=float, default=128)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--times", type=float, nargs="*")
    ap.add_argument("--out", default="sheets")
    ap.add_argument("--width", type=int, default=480)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.times:
        shots = [(i + 1, t) for i, t in enumerate(args.times)]
    else:
        md = open(args.storyboard, encoding="utf-8").read()
        T = 60 / args.bpm
        found = re.findall(r"## Frame (\d+) — .*?全片第 (\d+)–(\d+) 拍", md, re.S)
        shots = [(int(n), round((int(b) + 1) * T - 3 / args.fps, 3)) for n, a, b in found]
    ims = []
    for n, t in shots:
        f = out / f"s{n:02d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", args.video, "-frames:v", "1",
                        "-vf", f"scale={args.width}:-1", str(f)], check=True)
        im = Image.open(f).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 64, 22], fill="black")
        d.text((4, 4), f"{n} {t:.1f}", fill="white")
        ims.append(im)
    w, h = ims[0].size
    for k in range(0, len(ims), 12):
        sheet = Image.new("RGB", (w * 4, h * 3), "white")
        for i, im in enumerate(ims[k:k + 12]):
            sheet.paste(im, ((i % 4) * w, (i // 4) * h))
        p = out / f"sheet{k // 12 + 1}.jpg"
        sheet.save(p)
        print("wrote", p)


if __name__ == "__main__":
    main()
