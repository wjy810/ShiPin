"""查字体子集有没有漏字：列出合成里用到、但字体文件里没有的字。

字体子集漏字不会报错，浏览器会悄悄换成系统字体（字重、字形都不对），截图里很难一眼看出来。
这次「示」「意」「复」「原」就漏了（「示意」「复原图」两种章要用）。

用法：
  python3 font_coverage.py --fonts assets/fonts/*.woff2 --html index.html compositions/*.html [--text 文案.md]

只看 <template> 里 <style>/<script> 以外的可见文字和 CSS content。补字的办法：从 Fontsource 发布的同一款字体
（比如 @fontsource-variable/noto-serif-sc）里找到含这些字的分片，用 pyftsubset 只取这几个字，
再加一条 @font-face，用 unicode-range 指定这几个字。需要 fontTools（woff2 还要 brotli）。
"""

import argparse
import re

from fontTools.ttLib import TTFont


def visible_text(html):
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    html = re.sub(r"<(script|style|title)\b.*?</\1>", "", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", nargs="+", required=True)
    ap.add_argument("--html", nargs="*", default=[])
    ap.add_argument("--text", nargs="*", default=[], help="其他要覆盖的纯文本文件（比如文案）")
    args = ap.parse_args()

    have = set()
    for f in args.fonts:
        have |= set(TTFont(f).getBestCmap().keys())
    used = {}
    for f in args.html:
        for ch in visible_text(open(f, encoding="utf-8").read()):
            used.setdefault(ch, set()).add(f)
    for f in args.text:
        for ch in open(f, encoding="utf-8").read():
            used.setdefault(ch, set()).add(f)
    missing = sorted(ch for ch in used if ord(ch) > 0x2E7F and ord(ch) not in have)  # 只管 CJK 及之后（拉丁、标点一般有系统字体兜底）
    if not missing:
        print(f"字体覆盖完整：{len([c for c in used if ord(c) > 0x2E7F])} 个中文字符都在字体里")
        return
    print(f"字体里缺 {len(missing)} 个字：" + "".join(missing))
    print("unicode-range: " + ", ".join(f"U+{ord(c):04X}" for c in missing))
    for ch in missing:
        print(f"  {ch} U+{ord(ch):04X}  用在 " + "、".join(sorted(used[ch])))


if __name__ == "__main__":
    main()
