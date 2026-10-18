"""扒配乐的拍点网格：BPM、第 0 拍的位置、段落边界、每小节的能量。

用法：
  python3 beat_grid.py bgm.mp3 --out grid.json [--bpm-hint 128]

输出：
  - 拟合出的 BPM 和 t0（第 1 小节第 1 拍在原曲里的秒数），以及拍点相对直线网格的残差（判断是不是恒速）
  - 四段分别拟合的 BPM（判断有没有漂）
  - 每小节的响度 / 低频 / 高频（看段落：前奏、高潮、间奏……）
  - 段落新奇度峰值（拍号、mod 4、mod 16），段落一般从这些拍开始
  - 起音落在网格上的相位分布：几乎全落在 0 和 0.5 拍上，说明网格是对的

注意：自动测速常把半拍的起音也数进去，报出错的 BPM（这次 `hyperframes beats` 报 152，实际 128）。
以这里的直线拟合 + 相位分布为准；必要时用 --bpm-hint 给个大概值。
需要 librosa 和 numpy。
"""

import argparse
import json

import numpy as np
import librosa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--out", default="grid.json")
    ap.add_argument("--bpm-hint", type=float, default=None)
    ap.add_argument("--beats-per-bar", type=int, default=4)
    args = ap.parse_args()

    y, sr = librosa.load(args.audio, sr=44100, mono=True)
    dur = len(y) / sr
    hop = 128
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    kw = {"start_bpm": args.bpm_hint} if args.bpm_hint else {}
    tempo, bf = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, hop_length=hop, tightness=400, **kw)
    bt = librosa.frames_to_time(bf, sr=sr, hop_length=hop)
    i = np.arange(len(bt))
    A = np.vstack([np.ones_like(i), i]).T
    (t0, T), *_ = np.linalg.lstsq(A, bt, rcond=None)
    # 把 t0 挪到第一个非负拍上
    k0 = int(np.ceil(-t0 / T)) if t0 < 0 else -int(t0 // T)
    t0 = t0 + k0 * T
    res = bt - (bt[0] + T * i) - ((bt - (bt[0] + T * i)).mean())
    print(f"时长 {dur:.3f} s；librosa 估计 {float(np.atleast_1d(tempo)[0]):.2f} BPM，{len(bt)} 拍")
    print(f"直线拟合：BPM {60 / T:.3f}，1 拍 {T:.5f} s，t0 {t0:.4f} s；残差最大 {abs(res).max() * 1000:.1f} ms，均方根 {res.std() * 1000:.1f} ms")
    for q in range(4):
        sl = slice(q * len(bt) // 4, (q + 1) * len(bt) // 4)
        (_, b), *_ = np.linalg.lstsq(A[sl], bt[sl], rcond=None)
        print(f"  第 {q + 1} 段 BPM {60 / b:.3f}")

    onsets = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, hop_length=hop, units="time")
    ph = ((onsets - t0) / T + 1 / 16) % 1  # 每格以 0、1/8、2/8……拍为中心
    hist = np.histogram(ph, bins=8, range=(0, 1))[0]
    print("起音相位分布（一拍分 8 格，第 1 格是整拍、第 5 格是半拍，应集中在这两格）：", hist.tolist())
    d = (onsets - t0) / T
    near = np.abs(d - np.round(d)) < 0.1
    print(f"整拍附近的起音相对网格：中位 {np.median((d - np.round(d))[near]) * T * 1000:+.1f} ms")

    # 每拍一个特征向量，算段落新奇度
    hop2 = 256
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop2))
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)
    tt = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=hop2)
    nb = int((tt[-1] - t0) / T)
    edges = [int(np.searchsorted(tt, t0 + k * T)) for k in range(nb + 1)]
    mf = librosa.feature.mfcc(S=librosa.power_to_db(librosa.feature.melspectrogram(S=S**2, sr=sr)), n_mfcc=20)
    ch = librosa.feature.chroma_stft(S=S**2, sr=sr)
    X = np.array([np.r_[mf[:, edges[k]:edges[k + 1]].mean(1), 3 * ch[:, edges[k]:edges[k + 1]].mean(1)] for k in range(nb)])
    X = (X - X.mean(0)) / (X.std(0) + 1e-9)
    R = np.corrcoef(X)
    K = 8
    ker = np.kron(np.array([[1, -1], [-1, 1]]), np.ones((K, K)))
    nov = np.zeros(nb)
    for k in range(K, nb - K):
        nov[k] = (R[k - K:k + K, k - K:k + K] * ker).sum()
    peaks = [k for k in range(1, nb - 1) if nov[k] > nov[k - 1] and nov[k] >= nov[k + 1] and nov[k] > np.percentile(nov, 90)]
    print("段落新奇度峰值（段落多半从这些拍开始；mod 4 一致的那个相位就是小节第 1 拍）：")
    for k in peaks:
        print(f"  第 {k:3d} 拍  {t0 + k * T:7.3f} s  mod4={k % 4}  mod16={k % 16}  {nov[k]:.1f}")

    def band(lo, hi):
        return S[(f >= lo) & (f < hi)].mean(axis=0)

    rms = np.sqrt((S**2).mean(axis=0))
    low, high = band(40, 150), band(5000, 11000)
    bpb = args.beats_per_bar
    # 小节第 1 拍：段落新奇度峰值里最常见的 mod 相位
    phase = int(np.bincount([k % bpb for k in peaks], minlength=bpb).argmax()) if peaks else 0
    t0 = t0 + phase * T
    print(f"判断小节第 1 拍在相位 {phase}，第 1 小节从 {t0:.4f} s 开始（这就是剪辑时 data-media-start 的基准）")
    edges = edges[phase:]
    nb -= phase
    bars = []
    print(f"每小节（{bpb} 拍一小节；数值是相对全曲最大值）：")
    for b in range(nb // bpb):
        a, z = edges[bpb * b], edges[min(bpb * b + bpb, nb)]
        row = {"bar": b + 1, "t": round(t0 + bpb * b * T, 4), "rms": round(float(rms[a:z].mean() / rms.max()), 3),
               "low": round(float(low[a:z].mean() / low.max()), 3), "high": round(float(high[a:z].mean() / high.max()), 3)}
        bars.append(row)
        print(f"  小节 {row['bar']:3d}  {row['t']:7.2f} s  响度 {row['rms']:.2f}  低频 {row['low']:.2f}  高频 {row['high']:.2f}")

    json.dump({"bpm": 60 / T, "T": T, "t0": t0, "beats_per_bar": bpb, "novelty_peaks_from_t0": [k - phase for k in peaks], "bars": bars},
              open(args.out, "w"), ensure_ascii=False, indent=1)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
