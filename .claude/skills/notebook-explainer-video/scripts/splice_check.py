"""给配乐剪辑的接口打分：从第 x 小节结尾直接接到第 y 小节，听起来顺不顺。

做法：比较“原曲里第 x 小节后面本来接的那一小节（x+1）”和“要接上去的第 y 小节”的
和声（chroma）和音色（MFCC）相似度。和声 ≥ 0.9 基本听不出接口，0.8 左右可以接，
再低就会跳和弦。音色相似度为负，说明配器差很多（比如鼓突然没了），要么故意要这个效果，要么换一处接。

用法：
  python3 beat_grid.py bgm.mp3 --out grid.json
  python3 splice_check.py bgm.mp3 grid.json 16:32 27:32 32:41 64:69
  python3 splice_check.py bgm.mp3 grid.json --chords        # 先看每小节的主和弦和几小节一轮

小节号从 1 数，和 beat_grid.py 打印的一致。需要 librosa 和 numpy。
"""

import argparse
import json

import numpy as np
import librosa

NAMES = "C C# D D# E F F# G G# A A# B".split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("grid")
    ap.add_argument("pairs", nargs="*", help="x:y，表示第 x 小节结尾接第 y 小节开头")
    ap.add_argument("--chords", action="store_true", help="打印每小节最强的两个音级，以及隔 1/2/4/8 小节的和声相似度")
    args = ap.parse_args()

    g = json.load(open(args.grid))
    t0, T, bpb = g["t0"], g["T"], g.get("beats_per_bar", 4)
    y, sr = librosa.load(args.audio, sr=22050, mono=True)
    hop = 512
    C = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr, hop_length=hop)
    M = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop, n_mfcc=20)
    tt = librosa.frames_to_time(np.arange(C.shape[1]), sr=sr, hop_length=hop)
    nb = int((len(y) / sr - t0) / (bpb * T))

    def per_bar(F):
        out = []
        for k in range(nb):
            a = t0 + k * bpb * T
            m = (tt >= a) & (tt < a + bpb * T)
            out.append(F[:, m].mean(1))
        return np.array(out)

    Cb = per_bar(C)
    Cb /= np.linalg.norm(Cb, axis=1, keepdims=True)
    Mb = per_bar(M)
    Mb = (Mb - Mb.mean(0)) / (Mb.std(0) + 1e-9)
    Mb /= np.linalg.norm(Mb, axis=1, keepdims=True)

    if args.chords:
        print("每小节最强的两个音级：")
        cells = [f"{k + 1}:{NAMES[np.argsort(Cb[k])[-1]]}/{NAMES[np.argsort(Cb[k])[-2]]}" for k in range(nb)]
        for i in range(0, nb, 8):
            print("  " + "  ".join(cells[i:i + 8]))
        for L in (1, 2, 4, 8):
            s = [Cb[k] @ Cb[k + L] for k in range(nb - L)]
            print(f"隔 {L} 小节的平均和声相似度 {np.mean(s):.3f}（最高的那个就是和弦一轮的长度）")

    for p in args.pairs:
        x, yb = (int(v) for v in p.split(":"))
        if not (1 <= x < nb and 1 <= yb <= nb):
            print(f"{p}: 小节号超出范围（1–{nb}）")
            continue
        nat = x  # 第 x+1 小节在数组里的下标是 x
        c = float(Cb[nat] @ Cb[yb - 1])
        m = float(Mb[nat] @ Mb[yb - 1])
        verdict = "顺" if c >= 0.9 else ("可以" if c >= 0.78 else "会跳和弦")
        print(f"第 {x:3d} 小节 → 第 {yb:3d} 小节：和声 {c:.3f}  音色 {m:+.3f}  {verdict}"
              f"（原曲里接在后面的是第 {x + 1} 小节；第 {yb} 小节在原曲 {t0 + (yb - 1) * bpb * T:.3f} s）")


if __name__ == "__main__":
    main()
