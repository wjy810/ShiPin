"""把配乐剪辑和钟表滴答声混成一条 assets/audio/mix.flac，片子里只放这一条音轨。

混音全在这一个文件里：剪法写在下面的 CLIPS 里，滴答每段的音量已经做进 ticks.flac。改剪辑就改这里再跑一遍。
成片的声音不用渲染器混出来的那一条，而是由 scripts/finalize.py 直接把这个文件编码进去，原因见那里。

用法（需要 ffmpeg 和 numpy）：python3 scripts/mixdown.py   （在 成片/ 目录下跑）
"""

import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "assets" / "audio"
SR = 48000  # 128 BPM 下 1 拍 = 22500 个采样，所有切点都落在整采样上
TOTAL = 126.5625

# 配乐剪辑（同 分镜.md 第 1.3 节）：(片中起点秒, 时长秒, 原曲起点秒, 淡出秒)。淡入一律 8 毫秒。
# 31.875–32.8125 秒故意空着，是屏 10 的“骤停”。
CLIPS = [
    (0, 30, 0.484, 0.008),
    (30, 1.875, 58.609, 0.008),
    (32.8125, 5.625, 45.484, 0.008),
    (38.4375, 1.875, 58.609, 0.008),
    (40.3125, 45, 75.484, 0.008),
    (85.3125, 22.5, 127.984, 0.008),
    (107.8125, 13.125, 45.484, 0.008),
    (120.9375, 1.875, 51.109, 0.008),
    (122.8125, 3.75, 45.484, 3.75),
]
FADE_IN = 0.008

# 真峰值上限。渲染器要求成片 AAC 不超过 −1 dBTP，AAC 编码还会再冒一点，所以这里留到 −1.5。
CEILING_DBFS = -1.5


def decode(path, channels):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", str(channels), "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).astype(np.float64)


def samples(sec):
    n = sec * SR
    assert abs(n - round(n)) < 1e-6, f"{sec} 秒不在整采样上"
    return int(round(n))


def main():
    music = decode(AUDIO / "bgm.mp3", 2)
    out = np.zeros((samples(TOTAL), 2))
    for start, dur, media_start, fade_out in CLIPS:
        a, n, m = samples(start), samples(dur), samples(media_start)
        seg = music[m : m + n].copy()
        assert len(seg) == n, "原曲不够长"
        g = np.ones(n)
        fi, fo = samples(FADE_IN), samples(fade_out)
        g[:fi] = np.arange(fi) / fi
        g[n - fo :] = np.minimum(g[n - fo :], 1 - np.arange(1, fo + 1) / fo)
        out[a : a + n] += seg * g[:, None]

    # 滴答：单声道，每段音量和提前量已经做进 ticks.flac（见 assets/说明.md），两个声道各放一份
    ticks = decode(AUDIO / "ticks.flac", 1)[:, 0]
    n = min(len(ticks), len(out))
    out[:n] += ticks[:n, None]

    # 4 倍过采样后限幅，压住采样点之间的真峰值，再降回 48 kHz
    ceiling = 10 ** (CEILING_DBFS / 20)
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
            "-af", f"aresample={SR * 4},alimiter=limit={ceiling:.4f}:attack=1:release=80:level=0:latency=1,aresample={SR}",
            "-t", f"{TOTAL}", "-c:a", "flac", "-sample_fmt", "s16", "-y", str(AUDIO / "mix.flac"),
        ],
        input=out.astype(np.float32).tobytes(),
        capture_output=True,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.decode())
    print("wrote", AUDIO / "mix.flac")


if __name__ == "__main__":
    main()
