"""按剪辑表把配乐和音效混成一条音轨（片子里只放这一条）。

用法：
  python3 mixdown.py edit.json out.flac

edit.json（路径相对这个 json 文件）：
{
  "sample_rate": 48000,          // 128 BPM 时 1 拍 = 22500 采样，切点都落在整采样上；别的 BPM 自己核一下
  "total": 126.5625,             // 全片秒数
  "ceiling_dbtp": -1.5,          // 4 倍过采样限幅的上限。成片用 AAC 256k 编码基本不再冒，192k 会冒 1.5 dB
  "music": "bgm.mp3",
  "clips": [                     // 配乐剪辑：片中起点、时长、原曲起点（都按拍点网格算），淡入淡出默认 8 毫秒
    {"start": 0, "dur": 30, "media_start": 0.484},
    {"start": 122.8125, "dur": 3.75, "media_start": 45.484, "fade_out": 3.75}
  ],
  "layers": [                    // 其他整条音轨，比如已经排好拍子的滴答声；gain 是线性倍数
    {"src": "ticks.flac", "start": 0, "gain": 1.0}
  ]
}

需要 ffmpeg 和 numpy。
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def decode(path, sr, channels):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", str(channels), "-ar", str(sr), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).astype(np.float64)


def main():
    spec_path, out = Path(sys.argv[1]), Path(sys.argv[2])
    spec = json.load(open(spec_path, encoding="utf-8"))
    base = spec_path.parent
    sr = spec.get("sample_rate", 48000)

    def samples(sec):
        n = sec * sr
        if abs(n - round(n)) > 1e-6:
            print(f"注意：{sec} 秒不在整采样上（{n:.3f}），四舍五入")
        return int(round(n))

    total = samples(spec["total"])
    mix = np.zeros((total, 2))
    music = decode(base / spec["music"], sr, 2)
    for c in spec["clips"]:
        a, n, m = samples(c["start"]), samples(c["dur"]), samples(c["media_start"])
        seg = music[m:m + n].copy()
        if len(seg) < n:
            raise SystemExit(f"原曲不够长：{c}")
        g = np.ones(n)
        fi, fo = samples(c.get("fade_in", 0.008)), samples(c.get("fade_out", 0.008))
        if fi:
            g[:fi] = np.arange(fi) / fi
        if fo:
            g[n - fo:] = np.minimum(g[n - fo:], 1 - np.arange(1, fo + 1) / fo)
        end = min(a + n, total)
        mix[a:end] += (seg * g[:, None])[:end - a]
    for layer in spec.get("layers", []):
        # 单声道素材原样放进两个声道（ffmpeg 自己升混会压低约 3 dB）
        ch = int(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", str(base / layer["src"])],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
        x = decode(base / layer["src"], sr, 1 if ch == 1 else 2) * layer.get("gain", 1.0)
        if x.shape[1] == 1:
            x = np.repeat(x, 2, axis=1)
        a = samples(layer.get("start", 0))
        end = min(a + len(x), total)
        mix[a:end] += x[:end - a]

    ceiling = 10 ** (spec.get("ceiling_dbtp", -1.5) / 20)
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "2", "-i", "-",
         "-af", f"aresample={sr * 4},alimiter=limit={ceiling:.4f}:attack=1:release=80:level=0:latency=1,aresample={sr}",
         "-t", f"{spec['total']}", "-c:a", "flac", "-sample_fmt", "s16", "-y", str(out)],
        input=mix.astype(np.float32).tobytes(), capture_output=True,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.decode())
    print("wrote", out)


if __name__ == "__main__":
    main()
