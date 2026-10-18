"""把照片“冲印”成风格 A 的相纸：用 HyperFrames 的 media-treatment 调色，但只跑一次，存成 *-print.jpg。

为什么要烤成图片：这套调色是 WebGL 着色器，没有显卡的机器只能软件渲染，实时用会让整片渲染慢约 15 倍。
每张图跑一次、片子里直接用结果，像素和实时调色一样，颗粒是静止的（证据照片不该闪）。

用法：
  python3 bake_prints.py --grading ../assets/print-grading.json --out assets/images  a.jpg b.jpg ...
  （输出 assets/images/a-print.jpg、b-print.jpg；每张图不能大于 1920×1080，先裁好再烤）

做法：临时建一个 HyperFrames 项目，每张图按原尺寸贴在左上角当 1 秒的片段、挂上 data-color-grading，
用 `hyperframes snapshot` 在每秒中间截一帧，再按原尺寸裁回来。需要 npx 和 Pillow。
"""

import argparse
import html
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

HF = "hyperframes@0.8.168"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--grading", required=True, help="data-color-grading 的 JSON 文件")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hf", default=HF)
    args = ap.parse_args()

    grade = html.escape(json.dumps(json.load(open(args.grading)), separators=(",", ":")), quote=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "assets").mkdir()
        (d / "meta.json").write_text(json.dumps({"id": "bake", "name": "bake"}))
        (d / "package.json").write_text(json.dumps({"name": "bake", "private": True, "type": "module"}))
        clips, items = [], []
        for i, src in enumerate(args.images):
            src = Path(src)
            w, h = Image.open(src).size
            if w > 1920 or h > 1080:
                raise SystemExit(f"{src} 是 {w}×{h}，大于 1920×1080，先裁小再烤")
            name = f"img{i}{src.suffix.lower()}"
            shutil.copy(src, d / "assets" / name)
            clips.append(f'<img id="i{i}" class="clip" src="assets/{name}" alt="" data-start="{i}" data-duration="1" '
                         f'data-track-index="0" style="position:absolute;left:0;top:0;width:{w}px;height:{h}px" '
                         f'data-color-grading="{grade}" />')
            items.append((src, w, h))
        n = len(items)
        (d / "index.html").write_text(f'''<!doctype html>
<html><head><meta charset="UTF-8" /><meta name="viewport" content="width=1920, height=1080" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>html,body{{margin:0;width:1920px;height:1080px;overflow:hidden;background:#000}}#root{{position:relative;width:100%;height:100%;overflow:hidden;background:#000}}</style>
</head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{n}" data-width="1920" data-height="1080">
{chr(10).join(clips)}
</div>
<script>window.__timelines = window.__timelines || {{}}; window.__timelines["main"] = gsap.timeline({{ paused: true }});</script>
</body></html>''', encoding="utf-8")
        at = ",".join(f"{i + 0.5}" for i in range(n))
        subprocess.run(["npx", "--yes", args.hf, "snapshot", str(d), "--at", at, "--output", str(d / "shots"), "--describe", "false"],
                       check=True)
        # snapshot 会在最后多截一张收尾帧，所以按时刻找：frame-NN-at-{i+0.5}s.png
        shots = []
        for i in range(n):
            hit = list((d / "shots").glob(f"frame-*-at-{i + 0.5:g}s.png"))
            if not hit:
                raise SystemExit(f"没找到第 {i + 0.5:g} 秒的截图")
            shots.append(hit[0])
        for (src, w, h), shot in zip(items, shots):
            im = Image.open(shot).convert("RGB").crop((0, 0, w, h))
            p = out / f"{src.stem}-print.jpg"
            im.save(p, quality=92)
            print("wrote", p)


if __name__ == "__main__":
    main()
