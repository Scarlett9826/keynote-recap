# 项目亮点

> 这份文档解释 **keynote-recap 与通用视频总结工具的区别**，以及每条差异背后解决了什么问题。
> 想看怎么用：[USAGE.md](USAGE.md)。想看项目结构：[README.md](README.md)。

## 一句话

YouTube 链接进，600 行图文复盘出。20 分钟 / $0.40，质量逼近人工版（差距 < 15%）。

## 5 个真正的创新点

### 1. 不是「视频总结」，是「发布会专用复盘」

通用视频总结工具产出的是要点清单——文字、扁平、没有结构。

但发布会的复盘有自己的体裁约定：

- 每个产品板块要配实拍图
- 要分清字幕原话、联网补充、独立判断三种来源
- 要有「整体概要 callout」开篇
- 要有「未查到的事实」透明声明节
- 数据要按「时间→数据」三段对比

**keynote-recap 把发布会复盘的「文体规则」写进了 7 阶段流水线里**，不是泛化的总结模板。

完整方法论见 [methodology/](methodology/) 5 份子文档。

### 2. 二级筛图链路：先 PIL 粗筛，再 Vision LLM 精筛

发布会 1.5 小时 = 5400 秒。每秒 60 帧 = 32 万帧。直接喂给 Vision LLM 既烧不起也跑不动。

- **Stage 2**：PIL 算每帧的「文本密度 + 边缘密度」打分，砍到 ~80 张候选
- **Stage 3**：Vision LLM 按「信息量 / 相关性 / 去重」三原则精筛到 30-50 张

**结果**：每板块至少 1 张关键帧（A8 硬约束），且都是 PPT/产品演示，不是演讲者特写、不是远景会场、不是过场。

筛图三原则详见 [methodology/filter-three-principles.md](methodology/filter-three-principles.md)。

### 3. Official-channel-first 研究：搜索引擎降级为 fallback

通用流程：搜「Gemini 3 Pro」→ DuckDuckGo 返回 SEO 农场和 Wikipedia → 引用质量崩了。

我的做法：**官方渠道是确定性的，无需赌搜索质量**。

- 注册了 7 大发布方（Google / OpenAI / Anthropic / Apple / Meta / Microsoft / NVIDIA）的官方域名 + URL 模板
- 自动从字幕提取产品名（频率 ≥ 2 的 Capitalized phrase）
- 直接构造 `https://blog.google/technology/google-deepmind/gemini-3-pro/` 之类的 URL 优先 fetch
- 命中即标 confidence=high
- 命中不到才 fallback 到搜索引擎，且查询自动加 `site:<official>` 限定

**新发布方 3 行代码就能加**——见 [src/keynote_recap/official_channels.py](src/keynote_recap/official_channels.py)。

### 4. Stage 5.5「三步质检」+ auto-fix：把质量验收变成代码

LLM 写出来的东西经常有 hallucination：编造图文件名、caption 跟图无关、章节缺图。我把这些都做成了**可运行的代码检查**：

| 子步骤 | 检查什么 | 失败如何处理 |
|---|---|---|
| **5.5.0 filename check** | 所有图引用 vs 实际抽出来的文件 whitelist | 编造的直接报错，进入 lint_report.md |
| **5.5.1 coverage check + auto-fix** | 每章节 ≥ 1 图（A8 硬约束） | 缺图自动把未使用的 selected frames 塞过去 |
| **5.5.2 caption verify** | Vision LLM 重读图 + 核对 caption 是否真的描述了图 | 错配的标记并报错 |
| **5.5.3 anti-AI lint** | 正则扫禁用词（巨大/显著/革命性/让我们/不仅仅是）+ 禁用 emoji | zero-tolerance，不通过则全部列出 |

**lint 不过的报告不会发出来**。详细禁用词清单见 [methodology/anti-ai-lint.md](methodology/anti-ai-lint.md)。

### 5. 可量化的质量基线 + 「黄金标准」对照

绝大多数 LLM 工具说「质量很好」全靠感觉。我的做法是：

- 先手工写一份 781 行的「黄金标准」复盘（耗时 6 小时，38 轮迭代）
- 把流水线产出 vs 黄金标准做**指标级对照**
- 每次代码改动跑一次，产生 v1 → v10 的可追溯演进路径

**M2 v10 baseline**（Google I/O '26 Keynote）：

| 指标 | 黄金标准（人工） | M2 v10（CLI） | 达成率 |
|---|---|---|---|
| 行数 | 783 | 486 | 62% |
| 章节数 | 14 | 11 | 79% |
| 图数 | 35 | 19 | 54% |
| 引用数 | — | 11 | ✓ (≥ 8) |
| L1 lint 错误 | 0 | 0 | ✓ |
| Caption 错误 | 0 | 0 | ✓ |
| Filename 错误 | 0 | 0 | ✓ |
| 单次成本 | ~$6（人工时间） | ~$0.20–0.50（LLM） | — |
| 单次耗时 | ~6 小时 | ~15–25 分钟 | — |

黄金标准产出见 [docs/examples/io26-keynote-recap.md](docs/examples/io26-keynote-recap.md)。

---

## 顺带值得一提的工程细节

- **OpenAI 兼容 endpoint**：用户自由换 LLM（任何 `/v1` 接口都能跑——OpenAI / Gemini / Anthropic / OpenRouter / 自建网关）
- **HTML 自包含**（base64 内嵌图）：飞书直接粘贴成图文，不依赖外链
- **断点续跑**：`state.json` 保留每个 stage 状态，改 prompt 后只重跑后续
- **5 层 config override**：内置默认 → 用户 yaml → CLI flag → env var → 优先级清晰
- **CI 矩阵**：Python 3.10–3.13 全绿，已测到 3.14 也兼容

---

## 适用场景

| 对方关心什么 | 该主推哪个创新点 |
|---|---|
| 内容创作者 / 媒体 | #1 文体规则 + #2 筛图（最直观） |
| 工程师 / AI 同行 | #3 official-channel-first + #4 三步质检 + auto-fix |
| 团队 leader / PM | #5 可量化质量基线（说明这不是 "vibe-driven" 的玩具） |
| 产品经理 | #1 + 飞书友好的 HTML 自包含粘贴 |

---

## 想自己跑一遍

```bash
git clone https://github.com/Scarlett9826/keynote-recap
cd keynote-recap
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
brew install yt-dlp ffmpeg

export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://api.openai.com/v1
keynote-recap recap https://www.youtube.com/watch?v=<id> \
  --output-dir ./out/<event> \
  --keep-video
```

详细指南：[USAGE.md](USAGE.md)
完整配置：[docs/configuration.md](docs/configuration.md)
