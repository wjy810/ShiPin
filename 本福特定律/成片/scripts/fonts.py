"""字体：把全片用到的中文字从思源宋体可变字重版里子集化成一个文件，并把 @font-face 写进每个合成。

为什么每个合成都要写：hyperframes lint 按文件检查“用了的字体有没有 @font-face”，子合成不能只靠 index.html。
思源宋体（Noto Serif SC，可变字重 200–900，SIL OFL 1.1）原文件来自 google/fonts 仓库 ofl/notoserifsc/NotoSerifSC[wght].ttf。

用法：python3 scripts/fonts.py <NotoSerifSC[wght].ttf 的路径>      （在 成片/ 目录下，需要 fontTools + brotli）
改了任何文字以后重跑一次；每个文件里 /* FONTS:BEGIN */ 和 /* FONTS:END */ 之间的内容会被整体替换。
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
OUT = FONTS / "noto-serif-sc-film.woff2"

LATIN = """@font-face { font-family: "Cormorant Garamond"; font-weight: 500; font-style: normal; font-display: block; src: url("assets/fonts/cormorant-garamond-latin-500-normal.woff2") format("woff2"); }
@font-face { font-family: "Cormorant Garamond"; font-weight: 600; font-style: normal; font-display: block; src: url("assets/fonts/cormorant-garamond-latin-600-normal.woff2") format("woff2"); }
@font-face { font-family: "Cormorant Garamond"; font-weight: 500; font-style: italic; font-display: block; src: url("assets/fonts/cormorant-garamond-latin-500-italic.woff2") format("woff2"); }
@font-face { font-family: "Cormorant Garamond"; font-weight: 600; font-style: italic; font-display: block; src: url("assets/fonts/cormorant-garamond-latin-600-italic.woff2") format("woff2"); }
@font-face { font-family: "Playfair Display"; font-weight: 600; font-style: normal; font-display: block; src: url("assets/fonts/playfair-display-latin-600-normal.woff2") format("woff2"); }
@font-face { font-family: "Playfair Display"; font-weight: 700; font-style: normal; font-display: block; src: url("assets/fonts/playfair-display-latin-700-normal.woff2") format("woff2"); }
@font-face { font-family: "JetBrains Mono"; font-weight: 400; font-style: normal; font-display: block; src: url("assets/fonts/jetbrains-mono-latin-400-normal.woff2") format("woff2"); }
@font-face { font-family: "JetBrains Mono"; font-weight: 500; font-style: normal; font-display: block; src: url("assets/fonts/jetbrains-mono-latin-500-normal.woff2") format("woff2"); }"""
CJK = """@font-face { font-family: "Noto Serif SC"; font-weight: 200 900; font-style: normal; font-display: block; src: url("assets/fonts/noto-serif-sc-film.woff2") format("woff2"); }"""

# 中文排版里常和汉字一起出现的标点，也从思源宋体取，保证字形一致
EXTRA = "，。、：；！？“”‘’（）《》—…·「」"


def files():
    return [ROOT / "index.html", *sorted((ROOT / "compositions").glob("*.html"))]


def used_chars():
    chars = set(EXTRA)
    for f in files():
        text = re.sub(r"/\* FONTS:BEGIN \*/.*?/\* FONTS:END \*/", "", f.read_text(encoding="utf-8"), flags=re.S)
        chars |= {c for c in text if ord(c) >= 0x2E80}
    return chars


def main():
    src = Path(sys.argv[1])
    chars = used_chars()
    codes = ",".join(f"U+{ord(c):04X}" for c in sorted(chars))
    for old in FONTS.glob("noto-serif-sc-*.woff2"):
        old.unlink()
    subprocess.run(["pyftsubset", str(src), f"--unicodes={codes}", "--flavor=woff2", f"--output-file={OUT}",
                    "--layout-features=*", "--no-hinting", "--desubroutinize"], check=True)
    from fontTools.ttLib import TTFont
    have = set(TTFont(OUT).getBestCmap())
    missing = [c for c in chars if ord(c) not in have]
    if missing:
        raise SystemExit("字体里没有这些字：" + "".join(missing))
    for f in files():
        html = f.read_text(encoding="utf-8")
        block = "/* FONTS:BEGIN */\n" + ((LATIN + "\n") if f.name == "index.html" else "") + CJK + "\n/* FONTS:END */"
        if "/* FONTS:BEGIN */" not in html:
            html, n = re.subn(r"(<style>)", r"\1\n/* FONTS:BEGIN */\n/* FONTS:END */", html, count=1)
            if n != 1:
                continue  # 没有 <style> 的文件不用字体
        html = re.sub(r"/\* FONTS:BEGIN \*/.*?/\* FONTS:END \*/", lambda m: block, html, flags=re.S)
        f.write_text(html, encoding="utf-8")
    print(f"{len(chars)} 个中文字符 → {OUT.name}，{OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
