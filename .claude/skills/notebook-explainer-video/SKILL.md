---
name: notebook-explainer-video
description: 用 HyperFrames 把「文案 + 配图 + 配乐」做成卡拍的横屏科普短片（风格 A · 野外记录本：纸页、冲印照片当证据、墨线示意盖章、左下角大字），从扒拍子、按和弦剪配乐、写分镜.md、把照片烤成相纸、搭合成、排音效，到渲染、换掉渲染器的声音、逐项验收和交付，带着在真实项目里验证过的脚本。只要用户要做科普/知识类/解说类视频、要写分镜脚本、要“镜头卡在拍子上”、给了 bgm 让剪、要加钟表滴答之类的音效、提到野外记录本/样图风格/动效导演/HyperFrames 出片，或者要在这个仓库里做下一支片子、改这支片子，都用这个技能——即使用户没说“技能”两个字。
---

# 卡拍科普短片 · 风格 A（野外记录本）

做法的核心只有三句：

1. **先把配乐的拍点网格定死**，切点、屏内动作、音效全部对齐到这张网格。观众说不出为什么舒服，但错半拍立刻觉得“不对劲”。
2. **证据和示意一眼分开**：真实照片 = 证据，做成贴在本子上的冲印相纸；示意 = 墨线手绘，角上盖「示意」章。科普片的可信度靠这个。
3. **声音最后自己把关**：用自己混好的母带替换渲染器的声音，逐项量过再交付（HyperFrames 0.8.168 会把整条声音压低 7–9 dB，见第 8 步）。

完整的范例就在这个仓库：`分镜.md`（36 屏、2:06.6）、`成片/`（HyperFrames 项目）、`成片/assets/说明.md`（素材来源和处理）。拿不准时直接翻范例。

## 输入和产出

| 输入 | 用途 |
|---|---|
| `文案.md` | 逐屏的字（一字不改地照抄）、每段的音乐提示、需要的数字和换算 |
| `找图.md` + `图片/` | 配图，以及每张图的使用限制（能不能加圈、能不能写“真化石”……）——这些限制比好看更重要 |
| `样图/` | 风格的参照（字号、纸面、照片卡的样子） |
| `bgm.mp3` | 配乐。先确认版权（这次是原创） |

产出：`分镜.md` → `成片/`（HyperFrames 项目）→ `成片/<片名>.mp4`，外加 `成片/assets/说明.md`。

## 流程（每步都有过关标准）

下文的 `scripts/`、`assets/`、`references/` 都指本技能目录 `.claude/skills/notebook-explainer-video/`。
（`成片/scripts/` 里另有项目自己的 `mixdown.py`、`finalize.py`，剪法写死在里面、参数也不同，只给这支片子用。）

| 步 | 做什么 | 工具 | 过关标准 |
|---|---|---|---|
| 0 | 读全部材料，记下每张图的限制 | — | 能说出每屏用哪张图、哪些不能做 |
| 1 | 扒拍子 | `scripts/beat_grid.py` | 恒速（四段 BPM 差 < 0.01），起音集中在整拍和半拍 |
| 2 | 按和弦剪配乐，定总长 | `scripts/splice_check.py` | 每个接口和声 ≥ 0.8，切在小节第 1 拍 |
| 3 | 写 `分镜.md`，**写完停下来等用户看** | `scripts/storyboard_check.mjs` | 0 警告，时长合计 = 总长，每屏过阅读下限 |
| 4 | 备素材：照片冲印、字体补字、音效 | `bake_prints.py`、`font_coverage.py`、`sfx_track.py` | 字体不缺字；音效最响那一下落在拍点后约 20 ms |
| 5 | 搭合成：一幕一页 + 覆盖层 | `assets/page-template.html` | `npx hyperframes check` 0 错误 |
| 6 | 看帧：每屏最后状态 + 动作中间 | `hyperframes snapshot`、`endstate_sheet.py` | 没有遮挡、露边、错位、替换字体 |
| 7 | 混音：配乐剪辑 + 音效 → 一条母带 | `scripts/mixdown.py`、`sfx_track.py mask` | 约 −13.5 LUFS，真峰值 ≤ −1.5 dBTP，音效听得清 |
| 8 | 渲染 → 换音轨 → 验收 | `hyperframes render`、`finalize.py`、`audio_qc.py` | 增益差 ≈ 0 dB，接口偏移 0 ms，静音段纯静音 |
| 9 | 提交、推送、把文件发给用户 | git、SendUserFile | 用户不用自己找文件 |

下面逐步说要点。细节在 `references/` 里，按需读。

### 0. 读材料

把 `找图.md` 的限制逐条抄进分镜的“自查”一节，搭建时逐条对。这次的例子：伊苏阿岩石只许出现在屏 8、帽天山照片上不加年份、纳罗虫不写“就是这块”、提塔利克鱼不标骨骼名称、撞击坑图不调色（颜色代表海拔）、复原图必须标「复原图」。**位置核实不了的东西不画圈**（屏 21 的“手腕”、屏 32 的头骨都改成了字下划线或慢推）：圈错比不圈更伤可信度。

### 1. 扒拍子

```bash
python3 scripts/beat_grid.py bgm.mp3 --out grid.json
```

看三样：直线拟合的 BPM 和四段 BPM（恒速才能用固定网格）、起音相位分布（应集中在整拍和半拍两格）、段落新奇度峰值的 mod 4（推出小节第 1 拍）。脚本输出的 `t0` 就是第 1 小节第 1 拍在原曲里的秒数，剪辑的 `media_start` 都从它算。

**别信自动测速**：`npx hyperframes beats` 这次报 152 BPM（把半拍的起音也数进去了），实际 128。以直线拟合为准。

128 BPM 的常用数：1 拍 = 0.46875 s = 14.0625 帧（30 fps），4 小节 = 7.5 s = 225 帧整，48 kHz 下 1 拍 = 22500 采样整。全片第 n 拍起点帧 = round(n × 14.0625)。

### 2. 剪配乐、定总长

原曲通常比文案长，而且段落顺序不对。按 4 小节一轮的和弦重排：

```bash
python3 scripts/splice_check.py bgm.mp3 grid.json --chords          # 看每小节和弦、几小节一轮
python3 scripts/splice_check.py bgm.mp3 grid.json 16:32 27:32 32:41  # 第 x 小节结尾接第 y 小节
```

- 接口只放在小节第 1 拍，且两边在和弦轮里的位置相同（这次的轮是 G–G–E♭–F，接口都落在一轮的开头或同位置）。和声 ≥ 0.9 听不出，0.8 左右可以，再低会跳和弦。
- 总长只能按 4 小节（7.5 s）加减。同时守住**阅读下限：每屏时长 ≥ 字数 ÷ 5 秒，且 ≥ 2 秒**。两条一起卡，最接近文案的就是答案（这次 2:06.6，比文案长 4.1 s，在分镜第 0 节说明理由）。
- 想要“骤停”就在接口处留整拍的静音（这次屏 10 前留 2 拍），比任何音效都有力。
- 剪辑表写成 `edit.json`（格式见 `scripts/mixdown.py` 顶部），第 7 步直接用。

### 3. 写分镜（写完先停）

格式见 `references/storyboard.md`，要点：

- HyperFrames storyboard 格式：顶部 front matter，每屏一个 `## Frame N — 标题`，下面 `scene / duration / transition_in / src / status`，再加时间、音乐、字、图、图片处理、转场，最后一张“拍 | 帧 | 动作”表。
- 切点只在整拍上；幕与幕的切换放在段落第 1 拍；屏内动作在拍或半拍上。字在切点那一帧出现，于是阅读时间 = 整屏时长。
- 前面放：配乐分析和剪辑表、风格规则、时间总表、自查清单、**需要用户拍板的事**（总长、和文案冲突的地方、核实不了的东西、音效来源、版权）。
- 用 `scripts/storyboard_check.mjs` 跑 HyperFrames 自己的解析器：0 警告、时长合计等于总长。
- **写完停下来，等用户检查**。用户放权之后（“你自行判断”），再一口气做到成片。

### 4. 备素材

- **照片 → 相纸**（`references/style-a.md` 的 A1–A5）：先裁好（≤ 1920×1080，只要照片本身，不要论文图的深色底），再烤：
  ```bash
  python3 scripts/bake_prints.py --grading assets/print-grading.json --out 成片/assets/images  a.jpg b.jpg
  ```
  调色配方是 vintage-wash 下限（intensity 0.5，颗粒 0.08），存在 `assets/print-grading.json`。**不要在片子里实时挂调色**：没显卡的机器上整片渲染慢约 15 倍；烤出来像素一样、颗粒静止。
- **字体**：用片中字的子集。章上的字（「示意」「复原图」）最容易漏，漏了浏览器会悄悄换系统字体：
  ```bash
  python3 scripts/font_coverage.py --fonts 成片/assets/fonts/*.woff2 --html 成片/index.html 成片/compositions/*.html
  ```
  缺字就从 Fontsource 的同款字体分片里用 `pyftsubset` 只取这几个字，加一条带 `unicode-range` 的 `@font-face`。
- **音效**：找公有领域或可商用的（这次是 Wikimedia Commons 的 Clock ticking.ogg，公有领域）。存 FLAC 不存 MP3（MP3 开头有编码器延迟，会错位）。
  ```bash
  python3 scripts/sfx_track.py analyze clock.ogg --at 2.032 3.042   # 最响那一下在采样里的位置 → lead_ms
  python3 scripts/sfx_track.py build sfx.json ticks.flac            # 按拍排好，每段音量做进文件
  ```
  **对拍对的是最响那一下，不是采样开头**。这次采样开头到主响有 80 ms 的起势，直接对齐开头会整体晚 2 帧，和画面的“咔”对不上。

### 5. 搭合成

结构和代码套路见 `references/hyperframes-patterns.md`，模板是 `assets/page-template.html`（已过 `check`）。要点：

- **一幕 = 一页纸 = 一个子合成**；翻页用整页平移 1920 px、8 帧、power4.out，从切点那一帧开始，前后两页各在自己的合成里动，宿主重叠 8 帧。
- **常驻元素（小钟、问号）放一个覆盖层合成**，压在所有页上面；要“交给”某一页时，在同一帧用一模一样的元素替换。
- 时间都用拍号写：`at(b) = (b − B0) × T`。表格里的“+2”“+2.5”直接变成 `at(B0 + 2)`。
- 一个合成一条暂停的 GSAP 时间线，注册到 `window.__timelines[id]`。**同一个元素不要同时有 CSS transform 和 GSAP transform**（lint 会报 `gsap_css_transform_conflict`）：倾斜写在外层包装上，或者写进补间里。
- 子合成太长（> 500 行）就按幕拆开（这次第 6 幕拆成两页，正好在反向推页处）。

### 6. 看帧

`npx hyperframes check` 只能查结构，问题要靠看：

```bash
python3 scripts/endstate_sheet.py 成片.mp4 分镜.md --out sheets/     # 每屏最后状态，12 屏一张
npx hyperframes snapshot 成片 --at 34.4,65.5,77.5                     # 渲染前看某几个时刻
```

这次在截图里抓到的：时间轴末端圆点露半个、铲子停在照片卡上、海岸线从卡片下沿露出一截、圈和角落的问号撞上、`non-scaling-stroke` 让描线断掉、章上的字换了字体。**每处修完都要重新截图确认**。清单见 `references/qa.md`。

### 7. 混音

```bash
python3 scripts/mixdown.py edit.json 成片/assets/audio/mix.flac
python3 scripts/sfx_track.py mask music_only.flac ticks.flac sfx.json   # 每一下音效会不会被音乐盖住
```

- 片子里**只放一条音轨**（这条母带），剪法和音量都在 `edit.json` / `sfx.json` 里。
- 音效音量按段定：音乐越满的地方加得越多（这次屏 9 和屏 17 底下最满，前一版几乎听不见）。和鼓同拍的那几下会和鼓混在一起，可以接受。
- 母带 4 倍过采样限幅到 −1.5 dBTP，响度在 −13.5 LUFS 左右，适合网络视频。

### 8. 渲染、换音轨、验收

```bash
cd 成片 && npx hyperframes render -q delivery -o renders/render.mp4 > render.log 2>&1
python3 scripts/finalize.py renders/render.mp4 assets/audio/mix.flac <片名>.mp4
python3 scripts/audio_qc.py <片名>.mp4 assets/audio/mix.flac --at <每个配乐接口后一点> --silence <静音段> --render-log render.log
```

- **HyperFrames 0.8.168 的声音不能直接用**：音频管线会在片头第 8–15 ms 左声道冒出一下 3 倍音量的尖峰（多条、单条音轨都有），渲染器为守 −1 dBTP 把整条声音压低 7–9 dB（成片只剩 −21 LUFS）。日志里会有 “Audio lowered by X dB”。`finalize.py` 画面原样拷贝、声音换成母带（AAC 256k；192k 会让真峰值冒 1.5 dB）。
- 验收标准：增益差 ≈ 0 dB、每个接口偏移 0.0 ms、静音段最大值 0、响度约 −13.4 LUFS、真峰值 ≤ −1 dBTP、片头 30 ms 峰值不高于母带。画面：3797 帧这类帧数和分镜一致，`ffprobe` 看 1920×1080、30 fps、音画起点都是 0。
- 渲染时间参考：2 分钟 1080p30，4 核、软件渲染，约 7 分钟。先跑 `check`，渲染期间去更新文档。

### 9. 交付

- 成片 < 100 MB 可以直接提交进仓库（这次 69 MB）。`renders/` 和 `.hyperframes/` 放 `.gitignore`。
- 用 SendUserFile 把成片发给用户，**不要让用户自己去找文件**。
- 分镜要和成片一致：搭建时改过的地方（换掉的圈、拆开的幕、加的音效）回写进 `分镜.md`，`status` 改成 `animated`。
- 汇报：做了哪些决定、音效来源和许可、验收数字、还有什么要用户确认的。

## 脚本和参考文档

| 文件 | 做什么 |
|---|---|
| `scripts/beat_grid.py` | BPM、t0、段落、每小节能量 |
| `scripts/splice_check.py` | 配乐接口的和声/音色相似度，每小节和弦 |
| `scripts/storyboard_check.mjs` | 用 HyperFrames 解析器检查 分镜.md |
| `scripts/bake_prints.py` | 照片烤成相纸（media-treatment 只跑一次） |
| `scripts/font_coverage.py` | 字体子集缺哪些字、对应 unicode-range |
| `scripts/sfx_track.py` | 音效：找主响位置、按拍排轨、查遮蔽 |
| `scripts/mixdown.py` | 剪辑表 → 一条母带（4 倍过采样限幅） |
| `scripts/finalize.py` | 渲染画面 + 母带 → 成片，守真峰值 |
| `scripts/audio_qc.py` | 成片声音逐项验收 |
| `scripts/endstate_sheet.py` | 每屏最后状态的对照表 |
| `assets/page-template.html` | 风格 A 一页纸的子合成模板（含 drop/draw/pop/tapes/stamp/flick） |
| `assets/print-grading.json` | 相纸调色配方 |
| `references/style-a.md` | 风格 A 的颜色、字、版式、图片处理、动作词汇、卡拍规则 |
| `references/storyboard.md` | 分镜.md 的结构和每屏格式 |
| `references/hyperframes-patterns.md` | 项目结构、时间换算、覆盖层交接、lint 的坑 |
| `references/audio.md` | 拍子、剪辑、音效、混音、渲染器的声音问题 |
| `references/qa.md` | 看帧和验收清单 |

脚本都在这支片子的数据上跑过：`mixdown.py` 和片中母带逐采样相同，`bake_prints.py` 和片中相纸平均差 0.7 个灰阶，`finalize.py` 和交付成片的声音逐字节相同。依赖：ffmpeg、numpy、librosa（1、2 步）、Pillow、fontTools、npx（HyperFrames 0.8.168）。
