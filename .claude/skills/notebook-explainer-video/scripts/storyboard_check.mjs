// 用 HyperFrames 自己的 storyboard 解析器检查 分镜.md：Frame 数、警告、时长合计，以及每个 Frame 的 src/status。
//
// 用法（解析器在 @hyperframes/core 里，要先装在一个临时目录）：
//   mkdir -p /tmp/sb && cd /tmp/sb && npm i --silent @hyperframes/core@0.8.168
//   cp <技能目录>/scripts/storyboard_check.mjs /tmp/sb/ && node /tmp/sb/storyboard_check.mjs /path/to/分镜.md [总秒数]
//
// 过关标准：0 条警告；时长合计等于全片总长（给了第二个参数就自动比）。
import { readFileSync } from "node:fs";
import * as sb from "@hyperframes/core/storyboard";

const [file, total] = process.argv.slice(2);
const m = sb.parseStoryboard(readFileSync(file, "utf8"));
console.log("全局：", JSON.stringify({ format: m.globals.format, extra: Object.keys(m.globals.extra || {}) }));
console.log(`Frame ${m.frames.length} 个，警告 ${m.warnings.length} 条`);
for (const w of m.warnings) console.log("  警告", JSON.stringify(w));
const sum = m.frames.reduce((s, f) => s + (f.durationSeconds || 0), 0);
console.log(`时长合计 ${sum} 秒`);
if (total && Math.abs(sum - Number(total)) > 1e-6) {
  console.log(`  ✗ 和全片总长 ${total} 秒对不上`);
  process.exitCode = 1;
}
const bad = m.frames.filter((f) => !f.src || !f.durationSeconds);
for (const f of bad) console.log(`  ✗ Frame ${f.number} 缺 src 或 duration`);
const status = {};
for (const f of m.frames) status[f.status] = (status[f.status] || 0) + 1;
console.log("状态：", JSON.stringify(status));
