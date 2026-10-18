"""音效轨：把一两下采样按拍点排成一整条，并检查对拍和会不会被音乐盖住。

三个子命令：

  python3 sfx_track.py analyze clock.ogg --at 2.032 3.042 [--dur 0.24]
      每一下采样里“最响那一下”离采样开头多少毫秒。采样开头往往有一段起势，
      直接把开头放在拍点上，听感会晚 40–80 毫秒（这次就是）。用这个数定 lead_ms：
      让最响那一下落在拍点后约 20 毫秒，正好对上画面 3 帧的急停。

  python3 sfx_track.py build sfx.json out.flac
      按 sfx.json 排一整条单声道音轨，每段音量直接做进文件。

  python3 sfx_track.py mask music_only.wav out.flac sfx.json
      每一下音效和同一时刻的音乐比：分 6 个频段算能量差，取最有利的那个频段。
      ≥ +3 dB 听得清；0 dB 左右会和鼓混在一起；< 0 dB 基本听不见，要加音量
      （注意叠上去别削波，最后的混音会限幅）。music_only 用不带音效的配乐剪辑（mixdown.py 去掉 layers 即可）。

sfx.json：
{
  "sample_rate": 44100, "total": 126.5625, "bpm": 128,
  "source": "clock.ogg",
  "grabs": [{"at": 2.032}, {"at": 3.042}],      // 采样起点（秒），交替使用
  "grab_dur": 0.24, "pre_roll_ms": 6, "tail_fade_ms": 40,
  "lead_ms": 60,                                  // 整条提前多少毫秒（见 analyze）
  "events": [                                     // beat 是全片第几拍（从 0 数），gain 是这一下的峰值
    {"beats": [0, 2, 4, 6], "gain": 0.42},
    {"beats": [64, 64.5, 65], "gain": 0.58}
  ]
}
需要 ffmpeg 和 numpy。
"""

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

BANDS = [(100, 300), (300, 700), (700, 1500), (1500, 3000), (3000, 6000), (6000, 12000)]


def decode(path, sr, extra_af=None):
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr)]
    if extra_af:
        cmd += ["-af", extra_af]
    raw = subprocess.run(cmd + ["-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def grab(y, sr, at, dur, pre_ms, fade_ms):
    a = int(round(at * sr)) - int(pre_ms / 1000 * sr)
    seg = y[a:a + int(dur * sr)].copy()
    fade = int(fade_ms / 1000 * sr)
    seg[-fade:] *= np.linspace(1, 0, fade)
    seg -= seg[:int(0.003 * sr)].mean()  # 去掉起势前那一点直流
    return seg / np.abs(seg).max()


def cmd_analyze(args):
    sr = 44100
    hp = decode(args.source, sr, "highpass=f=2000")
    for at in args.at:
        a = int(round(at * sr)) - int(0.006 * sr)
        n = int(args.dur * sr)
        env = np.abs(hp[a:a + n])
        win = int(0.003 * sr)
        sm = np.convolve(env, np.ones(win) / win, mode="same")
        pk = int(np.argmax(sm))
        first = int(np.argmax(sm > 0.25 * sm[pk]))
        # build 时 at 这个点对准拍点，所以从 at 算起（减掉 6 ms 的预留）
        f_ms, p_ms = first / sr * 1000 - 6, pk / sr * 1000 - 6
        print(f"采样 @{at:.3f}s：拍点后 {f_ms:5.1f} ms 第一下起来，{p_ms:5.1f} ms 最响"
              f"（建议 lead_ms ≈ {p_ms - 20:.0f}，让最响那一下落在拍点后 20 ms）")


def build(spec, base):
    sr, T = spec["sample_rate"], 60 / spec["bpm"]
    y = decode(base / spec["source"], sr)
    grabs = [grab(y, sr, g["at"], spec.get("grab_dur", 0.24), spec.get("pre_roll_ms", 6), spec.get("tail_fade_ms", 40))
             for g in spec["grabs"]]
    track = np.zeros(int(round(spec["total"] * sr)))
    lead = int(round(spec.get("lead_ms", 0) / 1000 * sr))
    pre = int(spec.get("pre_roll_ms", 6) / 1000 * sr)
    events = sorted((b, grp["gain"]) for grp in spec["events"] for b in grp["beats"])
    for i, (b, gain) in enumerate(events):
        s = grabs[i % len(grabs)] * gain
        a = int(round(b * T * sr)) - pre - lead
        if a < 0:
            s, a = s[-a:], 0
        end = min(a + len(s), len(track))
        track[a:end] += s[:end - a]
    return track, events


def cmd_build(args):
    spec = json.load(open(args.spec, encoding="utf-8"))
    track, events = build(spec, Path(args.spec).parent)
    if np.abs(track).max() > 0.99:
        raise SystemExit("峰值超过 0 dBFS，把 gain 调小")
    pcm = np.clip(np.round(track * 32767), -32768, 32767).astype(np.int16)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(spec["sample_rate"]), "-ac", "1", "-i", "-",
                    "-c:a", "flac", args.out], input=pcm.tobytes(), check=True)
    print(f"wrote {args.out}：{len(events)} 下，峰值 {np.abs(track).max():.3f}")


def cmd_mask(args):
    spec = json.load(open(args.spec, encoding="utf-8"))
    sr, T = 44100, 60 / spec["bpm"]
    m, t = decode(args.music, sr), decode(args.sfx, sr)
    f = np.fft.rfftfreq(int(0.093 * sr), 1 / sr)
    w = np.hanning(int(0.093 * sr))

    def bands(x):
        X = np.abs(np.fft.rfft(x * w)) ** 2
        return np.array([X[(f >= lo) & (f < hi)].sum() for lo, hi in BANDS])

    for grp in spec["events"]:
        for b in grp["beats"]:
            a = int((b * T - 0.03) * sr)
            if a < 0:
                continue
            seg = slice(a, a + len(w))
            d = 10 * np.log10((bands(t[seg]) + 1e-12) / (bands(m[seg]) + 1e-12))
            best = int(np.argmax(d))
            verdict = "清楚" if d[best] >= 3 else ("和鼓混在一起" if d[best] >= -1 else "听不见，要加音量")
            print(f"第 {b:6.1f} 拍  最有利频段 {BANDS[best][0]}–{BANDS[best][1]} Hz {d[best]:+5.1f} dB  {verdict}"
                  f"   各频段 " + " ".join(f"{v:+.0f}" for v in d))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("source")
    a.add_argument("--at", type=float, nargs="+", required=True)
    a.add_argument("--dur", type=float, default=0.24)
    b = sub.add_parser("build")
    b.add_argument("spec")
    b.add_argument("out")
    c = sub.add_parser("mask")
    c.add_argument("music")
    c.add_argument("sfx")
    c.add_argument("spec")
    args = ap.parse_args()
    {"analyze": cmd_analyze, "build": cmd_build, "mask": cmd_mask}[args.cmd](args)


if __name__ == "__main__":
    main()
