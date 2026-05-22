# 复用指南：丢一个发布会链接，产出高质量复盘

这份文档面向**项目维护者本人**和**任何使用本仓库的协作者**——目标只有一个：

> 给定任意一个科技发布会（Google I/O / Apple WWDC / OpenAI DevDay / Meta Connect / NVIDIA GTC / Microsoft Build …）的 YouTube 链接，能在一次会话内（≤ 30 分钟）产出**接近 M2 v10 质量基线**的中文图文复盘，并在飞书可直接粘贴。

如果你只是想跑一次：照 § 1 走。
如果你要协作 / 维护 / 排查质量回归：从 § 2 起整篇读完。

---

## 1. 一键产出

### 1.1 准备环境（一次性）

```bash
# clone
git clone <repo-url> keynote-recap && cd keynote-recap

# 装依赖（用 uv，比 pip 快 10×；没有 uv 用 pip 也可以）
uv venv && source .venv/bin/activate
uv pip install -e .

# 装外部工具
brew install yt-dlp ffmpeg

# 配 LLM endpoint（任意 OpenAI 兼容）
export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://api.openai.com/v1
```

### 1.2 写一个 config（可选，用默认也能跑）

```bash
mkdir -p ~/.config/keynote-recap
cp docs/examples/config.example.yaml ~/.config/keynote-recap/config.yaml
# 按 § 3.1 调整模型与 endpoint
```

### 1.3 跑

```bash
keynote-recap recap https://www.youtube.com/watch?v=<id> \
  --output-dir ./out/<event-name> \
  --keep-video
```

产出：

| 文件 | 说明 |
|---|---|
| `report.md` | **主产物**——中文 markdown 复盘 |
| `report.html` | 自包含 HTML（base64 内嵌图，飞书可直接粘贴） |
| `frames/` | 入选关键帧 PNG（30-50 张） |
| `research_notes.md` | 联网补充的事实清单 + 信源 URL |
| `lint_report.md` | 自检报告（章节图覆盖 / caption / 反 AI 套话） |
| `state.json` | 流水线状态（断点续跑用） |

---

## 2. 给 AI 协作者：如何在新链接上保持高质量

> 当用户在本项目里新发一句「帮我处理这个发布会：<URL>」时，按下面的剧本走。

### 2.1 读懂当前项目状态（30 秒）

每次开工先做：

```bash
git log --oneline -5
ls docs/examples/  # 黄金标准
cat docs/configuration.md | head -30
```

确认：
- 当前在 main 上没未提交修改
- M2 baseline 仍然是 `5131914` 起步
- M3 进度（research 改造 / CI / docs）见 commit messages

### 2.2 不需要重写代码——除非已知 bug

当前 pipeline 已经能产出 M2 v10 baseline 质量。**绝大多数新发布会链接，直接跑就行**。

只有出现下列**可量化的回归**，才考虑改代码：

| 症状 | 触发的修复点 |
|---|---|
| 章节合并到 < 10 节 | `prompts/05-draft-outline.md` 反合并自检；`stages/draft.py::_detect_product_names()` |
| Caption 出现英文 / 与图无关 | `prompts/05-5-caption-verify.md`；`stages/verify.py` 5.5.2 |
| 图文件名编造（lint 报错 "filename not found"） | `stages/draft.py` whitelist 显式呈现；`stages/verify.py` 5.5.0 |
| 整体概要被 ```markdown 围栏包裹 | `prompts/05-draft-callout.md` 严格禁止 + `stages/draft.py` strip |
| 引用数 < 8 | `prompts/05-draft-write.md` 强化 ≥ 10 / 每章 ≥ 1 |
| 图覆盖率 < 80% 章节 | `stages/verify.py::_auto_fix_coverage()` |
| 出现禁用词（巨大 / 显著 / 不仅仅是 / …） | `methodology/anti-ai-lint.md`；`stages/verify.py` 5.5.3 |
| Research 引用全是 SEO 农场 / Wikipedia | `src/keynote_recap/official_channels.py` 注册新发布方 |

### 2.3 跑流水线的标准动作

```bash
# 0. 确认 venv + endpoint
source .venv/bin/activate
echo "$OPENAI_API_KEY" | head -c 8

# 1. 跑全流程
keynote-recap recap <URL> --output-dir /tmp/<event>-recap --keep-video

# 2. 看 lint
cat /tmp/<event>-recap/lint_report.md

# 3. 看产出
wc -l /tmp/<event>-recap/report.md
ls /tmp/<event>-recap/frames/ | wc -l

# 4. 飞书预览：浏览器打开 report.html，全选复制粘贴飞书文档
open /tmp/<event>-recap/report.html
```

### 2.4 断点续跑

state.json 保存每个 stage 的 `last_completed_stage`。改 prompt 后只重跑后续阶段：

```bash
# 例：stage 5 prompt 改了，从 stage 5 起重跑
keynote-recap recap <URL> --output-dir /tmp/<event>-recap --start-stage 5
```

### 2.5 提交节奏

每次质量提升一个 milestone（例如 lint L1 全清零、章节数从 7 提到 11、引用数到 10），就 commit。**commit message 格式固定**：

```
feat(m<X>-v<N>): <一句话总结，用数字而不是形容词>
```

例如：
- `feat(m2-v10): 11 citations met + 19 images + 0 wrong captions`
- `feat(m3): official-channel-first research + product detection`

---

## 3. 关键配置 & 已知坑

### 3.1 模型选型（按支出梯度）

| 场景 | 推荐模型 | 备选 | 备注 |
|---|---|---|---|
| `extract`（vision 筛图） | `claude-sonnet-4` | `gpt-4o`, `gemini-2.5-pro` | 必须支持 vision |
| `research`（联网总结） | `gpt-4o-mini` | `gemini-2.5-flash`, `claude-haiku` | 轻量，调用频次最高 |
| `draft`（主写作） | `claude-opus-4` | `gpt-4-turbo`, `gemini-2.5-pro` | 最贵但质量最关键 |
| `verify`（质检） | `claude-sonnet-4` | `gpt-4o-mini` | 需 vision（caption 核对） |

**全栈用 `gemini-2.5-pro` 也能跑**——M2 v10 就是这么跑的，单次 ~$0.40。

> ⚠ **ACME内部 endpoint** (`https://your-gateway.example.com/v1`)：claude 系列不兼容（需走 anthropic 端点）；gemini-2.5-pro / gpt-4o 全部支持。

### 3.2 视频质量（影响抽帧）

```yaml
video:
  resolution: 1080p60   # 默认。低于 720p 会显著影响 PPT 文字识别
  keep_video: true       # 默认。重跑零成本
```

### 3.3 抽帧密度（M2 v10 调过的最优值）

```yaml
frame_filter:
  candidate_count: 80       # frame_scorer 初筛保留多少
  final_count_min: 30       # Vision LLM 精筛下限
  final_count_max: 50       # Vision LLM 精筛上限
```

少于 30 张几乎必然导致章节缺图；多于 50 张会浪费 token。

### 3.4 Research 阶段（M3 核心改造）

> M3 把 research 从「DuckDuckGo 搜索 → fetch top result」改成「**官方渠道 URL 优先 fetch → 搜索作 fallback**」。

**它怎么工作**：

1. 自动从 video uploader / title / 字幕开头检测发布方（Google / OpenAI / Apple / …）
2. 从字幕里提取产品名（频率 ≥ 2 的 Capitalized phrase）
3. 按 `src/keynote_recap/official_channels.py` 里的注册表，组合官方域名 + URL 模板
   - 例：Google + "Gemini 3 Pro" → `https://blog.google/technology/google-deepmind/gemini-3-pro/`
4. 优先 webfetch 这些 URL，命中就用；命中不到才回退到搜索
5. 命中官方域名的 fact，confidence 自动 = high

**新发布方怎么加**：见 `src/keynote_recap/official_channels.py` 文件头注释。给一个 `OfficialChannel(domains=..., seed_urls=..., url_templates=...)` 即可。

---

## 4. 质量验收清单（每次产出必看）

跑完后照这张表逐项核对——不达标就回到 § 2.2 找对应修复点：

```
□ report.md 行数 ≥ 450（v10 是 486；目标 600+）
□ 章节数 ≥ 10（≥ 12 更佳）
□ 入选图数 ≥ 18（≥ 25 更佳）
□ 每节至少 1 张图（A8 硬约束）
□ 引用数 ≥ 8（v10 是 11）
□ 整体概要 callout 存在且不被代码围栏包裹
□ 文末「一点观察」+「未查到」节存在
□ lint_report.md 中 L1 错误 = 0
□ lint_report.md 中 caption 错误 = 0
□ lint_report.md 中 filename 错误 = 0
□ 无禁用词（巨大 / 显著 / 革命性 / 让我们 / 不仅仅是）
□ research_notes.md 中至少 5 条 confidence=high（官方渠道）
```

---

## 5. 常见问题排查

### 5.1 yt-dlp 拉不到字幕

字幕 fallback 到 Whisper 转写（`prompts/01-transcribe-fallback.md`）。如果字幕全空，stage 4-5 输出会大幅缩水——优先排查 yt-dlp。

```bash
yt-dlp --list-subs <URL> | grep -E "en|zh"
```

### 5.2 单次成本超过 $1

```bash
keynote-recap recap <URL> --debug --output-dir ...
```

debug 会输出每个 stage 的 token 消耗。常见超支点：
- `extract` 用了 opus 而非 sonnet
- `candidate_count` > 100
- 字幕未截断且 `draft` 用了重型模型（M2 v10 已修复：字幕全量 + 用 gemini-pro 1M 上下文）

### 5.3 LLM 回的 JSON 截断

`stages/research.py` 已有 recovery 逻辑（找最后一个 `},` 关闭数组）。如果还是失败，把 `max_tokens` 从 16K 调到 32K：

```yaml
llm:
  max_tokens: 32000
```

### 5.4 章节合并过度（11 → 7）

prompt 已强化「12-15 章硬约束 + 反合并自检」。如果还合并，看 `outline.md` 里 LLM 给的 reasoning，通常是字幕中产品名出现 < 2 次没被检测到。手动加：

```python
# stages/draft.py::_detect_product_names()
# 把 min_count=2 改 min_count=1（仅在产品名稀疏时）
```

---

## 6. 项目结构速查

```
src/keynote_recap/
├── cli.py                    # entrypoint
├── pipeline.py               # 7 阶段 orchestration
├── config.py                 # 5 层 config 解析
├── state.py                  # 流水线状态 + 断点续跑
├── llm_client.py             # OpenAI 兼容 client
├── search.py                 # 搜索 provider 抽象（DDG / Tavily）
├── official_channels.py      # ★ M3 新增：官方渠道注册表
├── frame_scorer.py           # PIL 初筛打分
├── cost_tracker.py           # token / 成本追踪
└── stages/
    ├── download.py           # Stage 1
    ├── segment.py            # Stage 2
    ├── extract.py            # Stage 3
    ├── research.py           # Stage 4 ← M3 改造点
    ├── draft.py              # Stage 5
    ├── verify.py             # Stage 5.5
    └── render.py             # Stage 6

prompts/                       # 9 份 stage prompts（改 prompt 不改代码）
methodology/                   # 5 份方法论（每条规则有理由）
docs/examples/                 # 黄金标准（人工产出 vs CLI 产出）
```

---

## 7. 历史包袱（有记忆好排查）

- **commit `6b6aee9`**：M0+M1+M2 v4 起步。
- **commit `a8ebb4e`**：M2 v5——产品名检测 + 反合并 prompt，章节从 7 提到 11。
- **commit `5131914`**：M2 v10 质量基线。19 图 / 11 引用 / 0 错误。
- **commit `7486418`**：M3 docs。configuration.md 256 行；README baseline 表。
- **本次 M3 改造**：research stage 加 official-channel-first，加 product-name detection。

每次开工记得 `git log --oneline -10` 看看最近发生了什么。
