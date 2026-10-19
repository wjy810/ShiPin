"""配乐（降速版）+ 音效 → 片子的整条母带 assets/audio/mix.flac。

降速：0.8 倍，黑胶式（音高跟着降约 3.9 个半音），128 BPM → 102.4 BPM。
剪辑：原曲第 1–32 小节（前奏、第一段高潮、间奏、滚奏）→ 第 41–64 小节（第二段高潮、重低音段前半）
     → 第 73 小节到结尾（最终高潮）。两个接口都在小节第 1 拍、和弦轮同位置（和声相似度 0.990、0.997）。
混响：合成的立体声房间（RT60 约 2.2 s），湿声 16%，给“降速版”那种空气感；结尾让混响自然收掉。
音效：全部用 numpy 合成（没有外部素材、没有版权问题），事件表在 SFX_EVENTS，时间用全片拍号。

用法：python3 scripts/build_audio.py        （在 成片/ 目录下，需要 ffmpeg、numpy、scipy）
"""

import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "assets" / "audio"
SR = 48000
SPEED = 0.8
BEAT = 60 / (128 * SPEED)  # 0.5859375 s = 28125 采样
BAR = 4 * BEAT  # 2.34375 s
TOTAL = 157.5  # 全片秒数（最后 7.5 秒是文献线索，混响收尾）

# 剪辑表（全部按降速后的时间）：(片中起点秒, 时长秒或 None=到原曲结束, 原曲小节号)
T0_ORIG = 0.484  # 原曲第 1 小节第 1 拍（秒，未降速）
CLIPS = [
    (0.0, 32 * BAR, 1),
    (32 * BAR, 24 * BAR, 41),
    (56 * BAR, None, 73),
]


def decode(path, sr=SR, ch=2):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", str(ch), "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, ch).astype(np.float64)


def slowed_music():
    # 黑胶式降速：先重采样到 48k（原文件是 44.1k，asetrate 作用在滤镜链当时的采样率上），
    # 再把 48k 的采样当成 38.4k 播放，最后重采样回 48k
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(AUDIO / "bgm.mp3"), "-ac", "2", "-ar", str(SR),
                          "-af", f"aresample={SR}:resampler=soxr,asetrate={int(SR * SPEED)},aresample={SR}:resampler=soxr", "-f", "f32le", "-"],
                         capture_output=True)
    if raw.returncode:  # 没有 soxr 就用默认重采样
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(AUDIO / "bgm.mp3"), "-ac", "2", "-ar", str(SR),
                              "-af", f"aresample={SR},asetrate={int(SR * SPEED)},aresample={SR}", "-f", "f32le", "-"],
                             capture_output=True, check=True)
    return np.frombuffer(raw.stdout, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def s(sec):
    return int(round(sec * SR))


def edit(music):
    out = np.zeros((s(TOTAL), 2))
    fade = s(0.010)
    for start, dur, bar in CLIPS:
        m = s((T0_ORIG + (bar - 1) * 4 * 60 / 128) / SPEED)
        seg = music[m:] if dur is None else music[m:m + s(dur)]
        seg = seg.copy()
        g = np.ones(len(seg))
        g[:fade] = np.linspace(0, 1, fade)
        if dur is not None:
            g[-fade:] = np.minimum(g[-fade:], np.linspace(1, 0, fade))
        a = s(start)
        n = min(len(seg), len(out) - a)
        out[a:a + n] += (seg * g[:, None])[:n]
    return out


def reverb(x, rt60=2.2, wet=0.16, seed=7):
    rng = np.random.default_rng(seed)
    n = s(rt60 * 1.3)
    t = np.arange(n) / SR
    env = 10 ** (-3 * t / rt60)
    ir = np.stack([rng.standard_normal(n) * env, rng.standard_normal(n) * env], axis=1)
    sos = butter(2, 6500, "low", fs=SR, output="sos")  # 高频衰减快一点，像真房间
    ir = sosfilt(sos, ir, axis=0)
    ir[: s(0.025)] = 0  # 25 ms 预延迟
    ir /= np.sqrt((ir ** 2).sum(axis=0, keepdims=True))
    hp = butter(2, 180, "high", fs=SR, output="sos")  # 低频不进混响，免得糊
    send = sosfilt(hp, x, axis=0)
    w = np.stack([fftconvolve(send[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return x * (1 - wet * 0.5) + w * wet * 3.0


def eq(x):
    # 降速后高频变暗：5 kHz 以上提 2.5 dB 找回空气感；25 Hz 以下切掉
    hp = butter(2, 25, "high", fs=SR, output="sos")
    x = sosfilt(hp, x, axis=0)
    hs = butter(1, 5000, "high", fs=SR, output="sos")
    return x + sosfilt(hs, x, axis=0) * (10 ** (2.5 / 20) - 1)


# ---------------- 音效（合成） ----------------
def env_exp(n, decay):
    return np.exp(-np.arange(n) / SR / decay)


def sfx_impact(gain=1.0):
    """电影感低频冲击：正弦从 70 Hz 掉到 38 Hz + 一点噪声瞬态。用在大揭晓。"""
    n = s(1.8)
    t = np.arange(n) / SR
    f = 38 + 32 * np.exp(-t / 0.12)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * env_exp(n, 0.55)
    rng = np.random.default_rng(1)
    click = sosfilt(butter(2, [80, 1800], "band", fs=SR, output="sos"), rng.standard_normal(n)) * env_exp(n, 0.03) * 0.5
    y = (body + click) * gain
    return np.stack([y, y], 1)


def sfx_whoosh(dur=0.9, gain=1.0, seed=2):
    """气流声：带通噪声中心频率上扫，结尾正好落在事件点上（所以放置时提前 dur）。"""
    n = s(dur)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((n, 2))
    out = np.zeros((n, 2))
    blocks = 24
    for b in range(blocks):
        a, z = b * n // blocks, (b + 1) * n // blocks
        fc = 250 * (14 ** (b / (blocks - 1)))
        sos = butter(2, [fc * 0.6, min(fc * 1.6, 20000)], "band", fs=SR, output="sos")
        out[a:z] = sosfilt(sos, noise[a:z], axis=0)
    t = np.linspace(0, 1, n)
    env = (t ** 2.2) * (1 - t ** 8)
    return out * env[:, None] * 0.6 * gain


def sfx_chime(freq=1318.5, gain=1.0):
    """金属钟片：不谐和泛音，给金色数字落定。"""
    n = s(2.2)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for ratio, amp, dec in [(1, 1, 1.4), (2.76, 0.45, 0.6), (5.4, 0.22, 0.3), (8.93, 0.1, 0.15)]:
        y += amp * np.sin(2 * np.pi * freq * ratio * t) * np.exp(-t / dec)
    y *= np.minimum(1, t / 0.002)
    y *= 0.25 * gain
    return np.stack([y * 0.9, y], 1)


def sfx_tick(gain=1.0, seed=3):
    """很短的咔哒：数字翻牌、计数。"""
    n = s(0.05)
    rng = np.random.default_rng(seed)
    y = sosfilt(butter(2, [2000, 9000], "band", fs=SR, output="sos"), rng.standard_normal(n)) * env_exp(n, 0.006)
    y *= 0.35 * gain
    return np.stack([y, y], 1)


def sfx_riser(dur=2.3, gain=1.0, seed=4):
    """上升音：噪声 + 正弦上滑，进下一段之前。放置时提前 dur。"""
    n = s(dur)
    t = np.arange(n) / SR
    f = 180 * (8 ** (t / dur))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3
    rng = np.random.default_rng(seed)
    noise = sosfilt(butter(2, 1500, "high", fs=SR, output="sos"), rng.standard_normal(n)) * 0.25
    env = (t / dur) ** 2.5
    y = (tone + noise) * env * gain
    return np.stack([y, y * 0.95], 1)


def sfx_paper(gain=1.0, seed=5):
    """翻书页：带通噪声 + 稀疏的噼啪。"""
    n = s(0.45)
    rng = np.random.default_rng(seed)
    base = sosfilt(butter(2, [700, 6000], "band", fs=SR, output="sos"), rng.standard_normal(n))
    crackle = (rng.random(n) > 0.997) * rng.standard_normal(n) * 3
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t) ** 1.5
    y = (base + crackle) * env * 0.22 * gain
    return np.stack([y, y * 0.9], 1)


def sfx_shimmer(gain=1.0, seed=6):
    """一串高音闪光：金属字扫光。"""
    n = s(1.4)
    out = np.zeros((n, 2))
    rng = np.random.default_rng(seed)
    for k in range(9):
        f = 2093 * (2 ** (rng.integers(0, 12) / 12))
        a = s(k * 0.07)
        c = sfx_chime(f, 0.18)
        m = min(len(c), n - a)
        out[a:a + m] += c[:m] * (0.6 if k % 2 else 1.0)
    return out * gain


SFX = {"impact": sfx_impact, "whoosh": sfx_whoosh, "chime": sfx_chime, "tick": sfx_tick,
       "riser": sfx_riser, "paper": sfx_paper, "shimmer": sfx_shimmer}

# 事件表：(全片拍号, 音效, 参数)。whoosh / riser 的末端对准拍号，其余从拍号开始。拍号和合成里的 at(b) 一一对应。
SFX_GAIN = 10 ** (-9 / 20)  # 音效总电平：压在音乐底下，只给画面“落点”
CHANGES = [40, 64, 96, 136.5, 160, 176, 192, 248]  # 转场气流
SFX_EVENTS = (
    [(b, "whoosh", {"dur": 0.8, "gain": 1.0, "seed": 10 + k}) for k, b in enumerate(CHANGES)]
    + [
        # S1–S2：首位变金、飞向槽位、穿过“1”进片名
        (8, "chime", {"freq": 1318.5, "gain": 0.45}),
        (17, "whoosh", {"dur": 1.0, "gain": 0.8, "seed": 30}),
        (18, "tick", {"gain": 1.2}),
        (32, "riser", {"dur": 2.0, "gain": 0.35}),
        (32, "impact", {"gain": 0.6}),
        (34, "shimmer", {"gain": 1.1}),
        # S4 1881：先看 2 秒书房照片，对数表再一页页飞进来
        (43, "paper", {"gain": 0.7, "seed": 41}),
        (43.75, "paper", {"gain": 0.8, "seed": 42}),
        (44.5, "paper", {"gain": 0.6, "seed": 43}),
        (56, "tick", {"gain": 1.6, "seed": 56}),
        # S5 1938：粒子流进柱子，30.1% 落定
        (72.5, "whoosh", {"dur": 0.7, "gain": 0.7, "seed": 72}),
        (82, "impact", {"gain": 0.5}),
        (82, "chime", {"freq": 1318.5, "gain": 0.6}),
        (88, "tick", {"gain": 1.4, "seed": 88}),
    ]
    # S6：计数器从 100 涨到 1000，首位每换一次响一下——间隔先长后短，耳朵也能“听见”对数
    + [(100.5 + 12 * np.log10(d), "tick", {"gain": 0.75, "seed": 100 + d}) for d in range(2, 10)]
    + [
        (112.5, "chime", {"freq": 1568.0, "gain": 0.5}),
        (128, "riser", {"dur": 2.3, "gain": 0.3}),
        # S7：2 的 1–1000 次幂越跑越快，停在 301
        (151, "riser", {"dur": 3.5, "gain": 0.25, "seed": 151}),
        (151, "impact", {"gain": 0.35}),
        (151, "chime", {"freq": 1318.5, "gain": 0.55}),
        # S8 反例：三张卡、数量级标尺
        (161, "tick", {"gain": 1.0, "seed": 161}),
        (162.5, "tick", {"gain": 1.0, "seed": 162}),
        (164, "tick", {"gain": 1.0, "seed": 164}),
        (168, "chime", {"freq": 659.25, "gain": 0.65}),
        # S9 217 国人口：31.3% 落定
        (184, "impact", {"gain": 0.55}),
        (184, "chime", {"freq": 1318.5, "gain": 0.55}),
        # S10 指纹、证据
        (199, "tick", {"gain": 1.4, "seed": 199}),
        (204, "tick", {"gain": 1.0, "seed": 204}),
        (208, "tick", {"gain": 1.0, "seed": 208}),
        (212, "tick", {"gain": 1.0, "seed": 212}),
        # S11 筛子
        (224, "riser", {"dur": 2.3, "gain": 0.3, "seed": 224}),
        (225, "tick", {"gain": 1.0, "seed": 225}),
        (226.5, "tick", {"gain": 1.0, "seed": 226}),
        (228, "tick", {"gain": 1.0, "seed": 228}),
        (232, "chime", {"freq": 523.25, "gain": 0.6}),
        # S12 收尾：大“1”、扫光、片名回归
        (240, "impact", {"gain": 0.65}),
        (241, "shimmer", {"gain": 0.5, "seed": 241}),
        (249, "shimmer", {"gain": 1.2, "seed": 249}),
    ]
)


def place_sfx(out):
    for beat, name, kw in SFX_EVENTS:
        y = SFX[name](**kw)
        t = beat * BEAT
        if name in ("whoosh", "riser"):
            t -= len(y) / SR
        a = s(t)
        if a < 0:
            y, a = y[-a:], 0
        n = min(len(y), len(out) - a)
        out[a:a + n] += y[:n] * SFX_GAIN
    return out


def kweight(x):
    """近似 BS.1770 的 K 计权：低切 + 1.5 kHz 以上抬 4 dB，比纯 RMS 更接近耳朵听到的响度。"""
    x = sosfilt(butter(2, 60, "high", fs=SR, output="sos"), x, axis=0)
    return x + sosfilt(butter(1, 1500, "high", fs=SR, output="sos"), x, axis=0) * (10 ** (4 / 20) - 1)


def report(music, sfx):
    """每个事件点：音效最响的 50 ms 比周围 400 ms 音乐的平均响度高/低多少（K 计权 dB）。"""
    km, ks = kweight(music), kweight(sfx)
    w, h = s(0.4), s(0.05)
    for beat, name, kw in sorted(SFX_EVENTS, key=lambda e: e[0]):
        t = beat * BEAT
        lo, hi = (t - kw.get("dur", 0.8), t) if name in ("whoosh", "riser") else (t, t + 0.6)
        seg = ks[s(lo):s(hi)]
        peak = max(np.sqrt(np.mean(seg[i:i + h] ** 2)) for i in range(0, max(1, len(seg) - h), h // 2)) + 1e-9
        c = s(t)
        rm = np.sqrt(np.mean(km[max(0, c - w // 2):c + w // 2] ** 2)) + 1e-9
        print(f"  拍 {beat:7.2f}  {name:8s} 音效峰比音乐 {20 * np.log10(peak / rm):+6.1f} dB")


def main():
    music = edit(slowed_music())
    music = eq(music)
    music = reverb(music)
    # 结尾淡出：音乐在 154.7 s 左右结束，混响尾巴到 157.5 s 前收掉
    fo = s(2.5)
    music[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
    music *= 10 ** (-1.5 / 20)  # 给限幅留点余量，整体落在 −14 LUFS 左右
    sfx = place_sfx(np.zeros_like(music))
    report(music, sfx)
    mix = music + sfx
    ceiling = 10 ** (-1.5 / 20)
    for name, data in [("music_only.flac", music), ("mix.flac", mix)]:
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
             "-af", f"aresample={SR * 4},alimiter=limit={ceiling:.4f}:attack=1:release=80:level=0:latency=1,aresample={SR}",
             "-t", f"{TOTAL}", "-c:a", "flac", "-sample_fmt", "s16", "-y", str(AUDIO / name)],
            input=data.astype(np.float32).tobytes(), capture_output=True)
        if proc.returncode:
            raise SystemExit(proc.stderr.decode())
        print("wrote", AUDIO / name)


if __name__ == "__main__":
    main()
