"""把 HyperFrames 渲染出的画面和 mix.flac 合成最终成片。

为什么不直接用渲染器出的声音：HyperFrames 0.8.168 的音频管线会在片头第 8–15 毫秒、左声道冒出一下尖峰
（是正常音量的 3 倍），渲染器为守 −1 dBTP 会把整条声音压低 7–9 dB，成片只剩 −21 LUFS 左右。
所以这里画面原样拷贝，声音换成 mix.flac 重新编码，再把真峰值守在 −1 dBTP 以下（只压需要的那一点）。

用法（在 成片/ 目录下，需要 ffmpeg）：
  npx hyperframes render -q delivery -o renders/render.mp4
  python3 scripts/mixdown.py
  python3 scripts/finalize.py renders/render.mp4 这道题的答案，一直在变.mp4
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIX = ROOT / "assets" / "audio" / "mix.flac"
CEILING_DBTP = -1.0
MARGIN_DB = 0.1


def true_peak(path):
    err = subprocess.run(
        ["ffmpeg", "-nostats", "-hide_banner", "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr
    return float(re.findall(r"^\s*Peak:\s*([+-]?[\d.]+) dBFS$", err, re.M)[-1])


def mux(video, out, gain_db):
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(MIX),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-af", f"volume={gain_db:.2f}dB", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
            "-movflags", "+faststart", str(out),
        ],
        check=True,
    )


def main():
    video, out = Path(sys.argv[1]), Path(sys.argv[2])
    gain = 0.0
    for _ in range(4):
        mux(video, out, gain)
        tp = true_peak(out)
        print(f"gain {gain:+.2f} dB -> true peak {tp:+.1f} dBTP")
        if tp <= CEILING_DBTP:
            break
        gain -= tp - CEILING_DBTP + MARGIN_DB
    else:
        raise SystemExit("true peak still above the ceiling")
    print("wrote", out)


if __name__ == "__main__":
    main()
