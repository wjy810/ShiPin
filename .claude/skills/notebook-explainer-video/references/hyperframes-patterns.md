# HyperFrames 搭建套路（0.8.168 实测）

范例：`成片/index.html`、`成片/compositions/act-*.html`、`成片/compositions/overlay.html`。
HyperFrames 本身的规则以它自带的技能（`/hyperframes-core`、`/hyperframes-animation`）为准；这里只写这类片子用得上的套路和踩过的坑。

## 目录

1. 项目结构
2. 时间换算
3. 一页纸的子合成
4. 覆盖层和交接
5. 常用效果的写法
6. lint / check 的坑
7. 渲染

## 1. 项目结构

```
成片/
├── index.html                 根合成：桌面底色 + 每幕一个宿主 + 覆盖层宿主 + 一条音轨
├── compositions/act-N.html    一幕一页纸（<template> 包起来）
├── compositions/overlay.html  常驻元素（钟、问号），z-index 压在所有页上
├── assets/images/*-print.jpg  烤好的相纸；paper-grain.png
├── assets/fonts/*.woff2       字体子集 + 补字子集；OFL.txt
├── assets/audio/mix.flac      混好的母带（片中唯一一条音轨）
├── scripts/                   mixdown.py、finalize.py
└── package.json               固定 hyperframes 版本（npx --yes hyperframes@0.8.168 …）
```

`.gitignore`：`成片/.hyperframes/`、`成片/renders/`、`node_modules/`。

## 2. 时间换算

- 拍长 `T = 60 / BPM`，帧长 `F = 1 / 30`。全片第 n 拍（从 0 数）起点 = n × T。
- 宿主：`data-start = B0 × T`，`data-duration = (END − B0) × T + 8 × F`（多出的 8 帧是翻页重叠；尾声 12 帧就加 12 × F）。例：第 1 幕 B0 = 0、END = 26 → 12.1875 + 0.266667 = 12.454167。
- 子合成里一律用全片拍号写：`const at = (b) => (b - B0) * T;`，分镜表的“+2.5”就是 `at(B0_屏 + 2.5)`。
- 半拍里的帧偏移写成 `at(b) + 3 * F`（比如第二行字晚 3 帧）。

## 3. 一页纸的子合成

模板：`assets/page-template.html`（过了 check，截图确认过）。要点：

- `<template>` 里：`<style>`（所有选择器以 `#act-N` 开头，避免串页）、根 `<div id="act-N" data-composition-id="act-N">`、`<script>`。宿主 id、内层根 id、时间线的 key 三者一样。
- 一个合成一条 `gsap.timeline({ paused: true })`，最后 `window.__timelines["act-N"] = tl`。
- 元素初始状态写在 CSS 里（`.w`、`.card`、`.stamp` 默认 `opacity: 0`；`svg.ink path` 默认 `visibility: hidden`），时间线里 `tl.set` 打开。这样任何时刻 seek 过去都对。
- 推页入场：`tl.fromTo("#aN-page", { x: 1920 }, { x: 0, duration: 8 * F, ease: "power4.out" }, 0)`；离场：`tl.to("#aN-page", { x: -1920, … }, at(END))`。两页在各自的合成里动，宿主重叠 8 帧，正好接上。
- 一幕超过 ~500 行就拆成两个文件，拆在推页处。

## 4. 覆盖层和交接

- 覆盖层宿主 `#overlay { z-index: 10 }`，从第一次出现一直挂到最后一次。钟的几个位置写成常量，用一个函数切换：

  ```js
  const BASE = { x: 0, y: 0, scale: 1 };
  const CORNER = { x: 432, y: -352, scale: 144 / 520 };
  const HERO = { x: 80, y: -50, scale: 420 / 520 };
  const moveClock = (pos, b, f = 6, ease = "power3.out") => tl.to("#ov-clock", { ...pos, duration: f * F, ease }, at(b));
  const step = (to, b) => tl.to("#ov-hand", { rotation: to, duration: 3 * F, ease: "power4.out" }, at(b)); // 指针跳格
  ```
- **交接**（常驻元素变成某一页的一部分，比如钟面变成纸上的圆形贴片、问号落进字里）：页里放一个一模一样、同位置的元素，在同一帧覆盖层的隐藏、页里的显示。之后它就跟着那一页一起拉远、推走。
- 指针角度用累计角度（360 + x），别让它倒着绕一大圈。

## 5. 常用效果的写法

- **描线**：搭建时量长度，`strokeDasharray = len`，`strokeDashoffset` 从 len 补间到 0，`ease: "none"`。
- **虚线沿轮廓描出**：虚线自己不能用 dash 描。做一个 `<mask maskUnits="userSpaceOnUse">`，里面一条同路径的白色实线（`stroke-width` 比虚线粗），对它做描线；虚线 `mask="url(#…)"`。**遮罩里的路径要内联 `visibility: visible`**，否则继承 `svg.ink path { visibility: hidden }`，什么都看不见。
- **方框、括号**：用像素坐标的 viewBox，别用 `preserveAspectRatio="none"` + `vector-effect: non-scaling-stroke`——那样 `getTotalLength()` 量的是未缩放的长度，描到一半就断。
- **天平、指针绕某点转**：SVG 里用 `svgOrigin: "1250 260"`；HTML 元素用 `transform-origin`。
- **推近到照片的某个部位**：外层包装做位移和整体缩放，里面 `.zoom` 层做 1 → 1.8 的放大，`transform-origin` 定在要看的那一点（像素）；再用 4 拍 power1.inOut 慢慢推到 1.95。
- **照片卡从地图的 × 里弹出**：`transform-origin` 设成 × 在卡片坐标里的位置。弹满以后把底下的地图收掉，不然会从卡片边上露出来。
- **铲子之类的道具**：用完要“抛走”（向上 520 px、转 24°、7 帧 power2.in，然后隐藏），别停在下一张卡上。
- **复原图白底**：`mix-blend-mode: multiply`。

## 6. lint / check 的坑

| 现象 | 原因和改法 |
|---|---|
| `gsap_css_transform_conflict` | 同一元素 CSS 里有 `transform`（倾斜），GSAP 又动它的 scale/x。倾斜写到外层包装（`.tilt`、`.optw`），或者把 `rotation` 写进补间的 from/to 里（盖章就是这样） |
| `duplicate_media_discovery_risk`（warning） | 同一张图同一时刻用了两次（比如一张卡片和放大镜里的同一张图）。确认是故意的就可以留 |
| `container_overflow` / `canvas_overflow`（info） | 慢推、推页让元素暂时出界。是故意的就留着，或加 `data-layout-allow-overflow` |
| 章上的字换了字体 | 字体子集漏字。跑 `font_coverage.py` |
| “Failed to download CDN script … gsap”（渲染时 warning） | 编译器（Node）没走代理，下不到 CDN；浏览器能下到，动画正常。看截图里字和线是不是一步步出来的就能确认 |
| 实时 `data-color-grading` 很慢 | 软件渲染 WebGL，整片慢约 15 倍。用 `bake_prints.py` 烤成图片 |

## 7. 渲染

- `npx --yes hyperframes@0.8.168 check`：0 错误再渲染。
- `npx --yes hyperframes@0.8.168 render -q delivery -o renders/render.mp4 > render.log 2>&1`，放后台跑。4 核软件渲染时 auto 只开 1 个 worker，2 分钟 1080p30 约 7 分钟。
- 渲染完 **看日志里的 “Audio lowered by”**，然后无论有没有都用 `finalize.py` 换上母带（原因见 audio.md）。
- 画面要改就改合成、重渲；声音要改就改 `edit.json`/`sfx.json`、重跑 `mixdown.py` 和 `finalize.py`，不用重渲画面。
