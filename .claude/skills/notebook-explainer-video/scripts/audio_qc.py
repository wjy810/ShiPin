"""成片声音验收：拿成片和混音母带（mix.flac）逐项比。

用法：
  python3 audio_qc.py 成片.mp4 mix.flac --at 0.5 30.2 33 40.5 --silence 31.9-32.79 [--render-log render.log]

查这些：
  - 时长、整体增益差（应该 ≈ 0 dB；−7 dB 这种就是渲染器把声音压低了）
  - --at 给的每个时刻前后 2 秒的偏移（配乐接口处取接口后一点，应该全是 0.0 ms）
  - --silence 给的区间是不是纯静音（“骤停”）
  - 片头 30 毫秒的峰值和全片峰值（片头明显更高就是渲染器的那下尖峰）
  - 响度（LUFS）和真峰值（dBTP），网络视频一般 −14 LUFS 左右、真峰值 ≤ −1 dBTP
  - --render-log：渲染日志里有没有 “Audio lowered by …”

需要 ffmpeg 和 numpy。
"""

import argparse
import re
import subprocess

import numpy as np

SR = 48000


def dec(f):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def loudness(f):
    err = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", f, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summ = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s*([-\d.]+) LUFS", summ)
    p = re.search(r"Peak:\s*([-+\d.]+) dBFS", summ)
    return float(i.group(1)), float(p.group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("final")
    ap.add_argument("mix")
    ap.add_argument("--at", type=float, nargs="*", default=[])
    ap.add_argument("--silence", nargs="*", default=[], help="a-b，单位秒")
    ap.add_argument("--render-log")
    args = ap.parse_args()

    r, m = dec(args.final), dec(args.mix)
    n = min(len(r), len(m))
    print(f"时长：成片 {len(r) / SR:.4f} s，母带 {len(m) / SR:.4f} s")
    g = np.sqrt((r[:n] ** 2).mean() / (m[:n] ** 2).mean())
    print(f"整体增益差：{20 * np.log10(g):+.2f} dB")

    def lag_at(a, w=2 * SR, ml=int(0.02 * SR)):
        best, bl = -1e18, 0
        for L in range(-ml, ml + 1):
            if a + L < 0 or a + L + w > len(r):
                continue
            c = np.dot(r[a + L:a + L + w, 0], m[a:a + w, 0])
            if c > best:
                best, bl = c, L
        return bl / SR * 1000

    for t in args.at:
        print(f"  {t:8.3f} s 处偏移 {lag_at(int(t * SR)):+.3f} ms")
    for s in args.silence:
        a, b = (float(v) for v in s.split("-"))
        print(f"  静音 {a}–{b} s：最大 {np.abs(r[int(a * SR):int(b * SR)]).max():.5f}")
    head = np.abs(r[:int(0.03 * SR)]).max()
    print(f"片头 30 ms 峰值 {head:.3f}，全片峰值 {np.abs(r).max():.3f}（母带片头 {np.abs(m[:int(0.03 * SR)]).max():.3f}）")
    lufs, tp = loudness(args.final)
    print(f"响度 {lufs:.1f} LUFS，真峰值 {tp:+.1f} dBTP")
    if args.render_log:
        hits = re.findall(r"Audio lowered by ([\d.]+) dB", open(args.render_log, encoding="utf-8", errors="replace").read())
        print("渲染日志：" + (f"渲染器把声音压低了 {hits[-1]} dB（成片要用 finalize.py 换掉声音）" if hits else "没有压低声音"))


if __name__ == "__main__":
    main()
