# 看帧和验收清单

`npx hyperframes check` 只查结构（lint、运行时、版式、对比度）。这支片子里真正的问题，全是在截图里看出来的。每改一处都重新截图确认，别凭代码推断“应该好了”。

## 1. 渲染前

- [ ] `npx --yes hyperframes@0.8.168 check`：0 错误；warning 和 info 逐条确认是故意的（见 hyperframes-patterns.md 第 6 节）
- [ ] `font_coverage.py`：0 个缺字（章上的字最容易漏）
- [ ] `storyboard_check.mjs`：0 警告，时长合计 = 总长；`src` 指向实际文件
- [ ] 每屏最后状态截图（渲染前用 `hyperframes snapshot` 给一串时刻，渲染后用 `endstate_sheet.py`）
- [ ] 动作中间截图：推页中间、照片弹出中间、钟飞行中间、交接那一帧前后

## 2. 截图里要找的东西（这次真遇到的）

| 找什么 | 这次的例子 | 改法 |
|---|---|---|
| 东西从卡片/裁切边露出一截 | 时间轴卷完后左端的锈红点露出半个；屏 20 的海岸线从照片卡下沿露出 | 用完就 `tl.set(..., {opacity: 0})` |
| 道具停在不该在的地方 | 铲子停在照片卡上 | 让它“抛走”再隐藏 |
| 两个元素撞上 | 选项卡 C 的圈碰到角落常驻的问号 | 整组挪开（三张卡整体左移 50–70 px） |
| 描线断了、只描一半 | `1980年` 的框用了 `non-scaling-stroke` | 改像素坐标 viewBox |
| 遮罩里的线看不见 | 遮罩路径继承了 `visibility: hidden` | 内联 `visibility: visible` |
| 字体变细、变成黑体 | 「示意」「复原图」不在子集里 | 补字子集 + `unicode-range` |
| 圈的位置说不准 | 提塔利克鱼的“手腕”、Irhoud 10 的头骨 | 不圈：字下划线、慢推 |
| 字被挡、对比度不够 | —— | check 的对比度一项；照片上不放字 |
| 页与页接缝 | 推页时露桌面、两页错位 | 推页两边同一帧、同一缓动、宿主重叠 8 帧 |

## 3. 成片验收

```bash
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,nb_frames,sample_rate,channels,start_time -of default=nw=1 成片.mp4
python3 audio_qc.py 成片.mp4 assets/audio/mix.flac --at <每个配乐接口后一点> --silence <骤停区间> --render-log render.log
python3 endstate_sheet.py 成片.mp4 分镜.md --out sheets/
```

- [ ] 帧数 = 分镜总帧数（这次 3797），1920×1080，30 fps，H.264 + AAC 48 kHz 立体声
- [ ] 音画 `start_time` 都是 0
- [ ] 增益差 ≈ 0 dB，接口偏移 0.000 ms，骤停最大值 0
- [ ] 响度约 −14 LUFS（−13 到 −15），真峰值 ≤ −1 dBTP
- [ ] 片头 30 ms 峰值不高于母带片头（高了就是渲染器那下尖峰没被换掉）
- [ ] 36 屏对照表逐张看过，和分镜一致
- [ ] 抽几个动作时刻看画面和滴答同时到

## 4. 交付

- [ ] 成片放进仓库（< 100 MB），`renders/` 不提交
- [ ] `分镜.md` 回写成片的改动，`status: animated`
- [ ] `assets/说明.md`：每张图的来源和处理、字体许可、音效来源和许可、混音做法
- [ ] 提交、推送到指定分支
- [ ] SendUserFile 把成片发给用户
- [ ] 汇报：做了哪些决定、验收数字、还要用户确认什么
