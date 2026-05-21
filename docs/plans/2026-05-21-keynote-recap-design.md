# keynote-recap 设计文档

**日期**：2026-05-21
**作者**：基于 Google I/O '26 Keynote 简报项目复盘
**目标**：把一次性 ad-hoc 工作流，固化为可复用的开源 CLI 工具

---

## 一、产品定位

一行话：**输入一个 YouTube/Bilibili 发布会链接，输出一份与 Google I/O '26 Keynote 简报同等质量的中文图文复盘报告。**

不是什么：
- 不是「视频字幕摘要工具」（市面已有十几款）
- 不是「自动剪辑工具」
- 不是 SaaS Web 应用

是什么：
- 一个**有 opinion 的 CLI 工具**，把发布会复盘的最佳实践方法论固化为产品默认值
- 一套**可中断、可恢复、可审查**的多阶段 pipeline
- **方法论可读可改**：所有 prompt 是 markdown，用户可 fork 修改

---

## 二、核心方法论（项目的 opinion，写死在 prompts/）

### 2.1 报告骨架
1. 整体概要 callout，按发布逻辑分 8-10 块（每块：主题 + 一句定调 + 1-3 行嵌套证据）
2. 整体概要内含「核心判断」子项；正文不再单独写关键判断
3. 文末保留独立「一点观察」整章
4. 数据用「时间→数据」三段对比序列展示
5. 必须超越字幕做联网交叉补充，每条字幕外细节用 `> 📎 **补充信源**：[URL]` 块
6. 叙事顺序按发布的重要性，不按时间序

### 2.2 层级规范
- L1：`## 一、…`（中文数字）
- L2：`### 1.1 …`（阿拉伯数字）
- L3：`**xx**：`（段落标签）
- bullet 子项 4 空格缩进
- 图片永远顶格输出

### 2.3 筛图三原则（最重要的工程沉淀）
1. **信息量**：拒绝纯产品名/转场图/slogan
2. **相关性**：与所在板块内容直接相关，起视觉补充作用
3. **去重**：核心内容重复时严格删减

**优先级**：抽帧 > 官方图。官方图只用于抽帧无法替代的产品形态/技术结构（产品照片、UI 真机截图、合作伙伴墙）。

### 2.4 整体概要视觉
用 `<div class="callout" markdown="1">…</div>` 包裹，渲染后有特殊背景色。

---

## 三、技术选型

| 关注点 | 选择 | 理由 |
|---|---|---|
| 形态 | CLI 工具 + Markdown 库 | 创造性工作流不适合黑盒 SaaS；CLI 支持中断恢复 |
| LLM 后端 | OpenAI 兼容接口 + 用户自配 model | 不绑定单一供应商；支持 Claude/GPT/DeepSeek/智谱/本地 ollama |
| 联网搜索 | 可插拔 provider（默认 Tavily） | 同上原则；提供 webfetch-only 零成本兜底 |
| 视频源 | YouTube + Bilibili（yt-dlp） | 覆盖 95% 发布会场景 |
| 抽帧策略 | 均匀采样 + Vision LLM 二次筛选 | 自动过滤 slogan/转场/演讲者特写 |
| 报告风格 | 单一「哈礼中文风格」 | MVP 不做风格引擎；用户改 prompts/ 即可 |
| 交付物 | report.md + report.html | 飞书友好；HTML 自包含可发邮件 |

---

## 四、Pipeline 架构

### 7 个阶段（含 5.5 caption 核对），3 个人工检查点

> **2026-05-21 v2 修订**：
> - 新增 stage 5.5（图文核对 + 板块覆盖校验），来自 [requirements.md B5.1](../requirements.md) 的硬约束
> - frame 筛选从「单 Vision LLM」改为「frame_scorer 初筛 + Vision LLM 精筛」二级链路（B5.4）
> - research 从 stage 5 中分离（B5.2）

```
┌─────────────┐
│ 0. INPUT    │  CLI: keynote-recap https://youtube.com/...
└──────┬──────┘
       ▼
┌─────────────┐
│ 1. download │  yt-dlp 1080p60 → workdir/video.mp4
│             │  默认保留视频（重跑零成本，B6.2）
└──────┬──────┘
       ▼
┌──────────────┐
│ 2. transcribe│  yt-dlp 官方字幕 → 失败 fallback whisper-cpp 本地
│              │  → workdir/transcript.{srt,txt,chunks.json}
└──────┬───────┘
       ▼
┌────────────────────┐
│ 3. extract         │  ffmpeg 均匀抽 80-120 张 → workdir/frames_raw/
│  3.1 score (PIL)   │  frame_scorer.py 多维评分 → 淘汰演讲者/远景/过场（零成本）
│  3.2 vision filter │  Vision LLM 三筛精筛 → workdir/frames/（30-50 张）
│                    │  + workdir/frames_meta.json（含 timestamp / score / reason）
└──────┬─────────────┘
       ▼
   ⏸  CHECKPOINT 1：用户可审查 frames/ 并删除/补充
       ▼
┌────────────────────────────┐
│ 4. research                │
│  4.1 extract-facts         │  LLM 读字幕 → 抽「需联网验证」清单
│                            │  → workdir/research_targets.json
│  4.2 search & summarize    │  调 search provider → 阅读 → 汇总
│                            │  → workdir/research.md（含 unknowns 节）
└──────┬─────────────────────┘
       ▼
   ⏸  CHECKPOINT 2：用户可审查 research.md 并补充信源
       ▼
┌────────────────────────────┐
│ 5. draft                   │
│  5.1 outline               │  LLM 划章节（按发布优先级）→ workdir/outline.md
│  5.2 write                 │  LLM 综合 transcript + frames + research → workdir/report.draft.md
│  5.3 callout               │  LLM 基于正文写整体概要 callout → 注入到 report.md 顶部
└──────┬─────────────────────┘
       ▼
┌────────────────────────────┐
│ 5.5 verify（新增）         │
│  5.5.1 coverage check      │  机械校验：每个 ## 章节至少有 1 张图（A8 硬约束）
│                            │  失败则回到 stage 5.2 补图
│  5.5.2 caption verify      │  Vision LLM 重读每张图 → 校验 caption 准确性
│                            │  失败则改写 caption 或换图（B1.4）
│  5.5.3 anti-AI lint        │  正则扫「巨大/显著/革命性/让我们/不仅仅是」（B3.4）
│                            │  → workdir/report.md（最终版）
└──────┬─────────────────────┘
       ▼
   ⏸  CHECKPOINT 3：用户可审查 report.md 并精修
       ▼
┌──────────────┐
│ 6. render    │  md_to_html.py + 内联 base64 图片 → workdir/report.html
└──────┬───────┘
       ▼
       完成
```

### 每个 stage 都满足以下契约
- 输入是上一阶段的产出文件
- 产出落到 `workdir/` 磁盘（不在内存里隐式传递）
- 可独立重跑：`keynote-recap run <stage> --workdir /path`
- 可跳过：`keynote-recap run all --skip download,transcribe`（如果已有 mp4 + srt）
- **每个 stage 都打印当前阶段累计 LLM 成本**（B1.5）

---

## 五、命令接口设计

### 主命令
```bash
# 一键运行（无人值守，跑到底）
keynote-recap https://www.youtube.com/watch?v=xxx

# 多阶段 + 检查点（推荐质量优先）
keynote-recap https://www.youtube.com/watch?v=xxx --interactive

# 指定工作目录（重要：每场发布会一个独立目录）
keynote-recap https://... -w ./output/io26-keynote

# 跳过某些 stage（已有产物时）
keynote-recap run all -w ./output/io26-keynote --skip download

# 单跑某个 stage（方便迭代）
keynote-recap run draft -w ./output/io26-keynote
keynote-recap run render -w ./output/io26-keynote
```

### 配置文件
```toml
# ~/.config/keynote-recap/config.toml

[llm]
base_url = "https://api.anthropic.com/v1"  # 任何 OpenAI 兼容 endpoint
api_key  = "${ANTHROPIC_API_KEY}"
model    = "claude-sonnet-4"
vision_model = "claude-sonnet-4"  # 必须支持 vision

[search]
provider = "tavily"  # tavily | perplexity | brave | webfetch_only
api_key  = "${TAVILY_API_KEY}"

[video]
quality = "1080p60"
max_duration_min = 180  # 超过 3 小时报错确认

[extract]
target_frames = 100  # 均匀抽样数
keep_frames = 40     # Vision 筛选后保留数

[output]
language = "zh-CN"
```

### CLI 输出范例
```
$ keynote-recap https://youtube.com/watch?v=wYSncx9zLIU --interactive

[1/6] download   ████████████████ 1.67 GB / 1080p60 / 1:51:15
[2/6] transcribe ████████████████ 12,450 words via official subtitle
[3/6] extract    ████████████████ 96 frames → 38 frames after vision filter
                 28 slogan/transition frames removed
                 9 speaker close-ups removed

  ⏸  CHECKPOINT 1: review ./output/io26-keynote/frames/
  Press Enter to continue, or 'e' to edit...

[4/6] research   ████████████████ 47 facts queried, 23 sources verified

  ⏸  CHECKPOINT 2: review ./output/io26-keynote/research.md
  Press Enter to continue, or 'e' to edit...

[5/6] draft      ████████████████ report.md (781 lines, 14 sections, 46 images)

  ⏸  CHECKPOINT 3: review ./output/io26-keynote/report.md
  Press Enter to continue, or 'e' to edit...

[6/6] render     ████████████████ report.html (8.84 MB)

✅ Done in 24m 15s. Total cost: $4.32 (LLM) + $0.18 (search)
   Open: ./output/io26-keynote/report.html
```

---

## 六、目录结构

```
keynote-recap/
├── README.md                          # 5 分钟上手指南
├── LICENSE                            # MIT
├── CONTRIBUTING.md                    # fork 改 prompts 不用懂 Python
├── pyproject.toml                     # 包定义（用 uv/pip）
├── docs/
│   ├── requirements.md                # 项目初心（38 条用户消息溯源）
│   ├── methodology.md                 # 方法论完整说明
│   ├── customization.md               # 如何 fork 改风格
│   ├── plans/                         # 设计文档（本文件在此）
│   │   ├── 2026-05-21-keynote-recap-design.md
│   │   └── 2026-05-21-implementation-plan.md
│   └── examples/                      # 黄金标准产物
│       ├── io26-keynote-recap.md      # 781 行 / 47 图（B5.3）
│       ├── io26-keynote-recap.html
│       └── io26-research.md           # research stage 产物形态
├── prompts/                           # 所有 LLM 提示词（用户可改）
│   ├── 01-transcribe-fallback.md      # whisper fallback 时的 chunk 边界 prompt
│   ├── 03-extract-vision-filter.md    # 筛图三原则 vision prompt
│   ├── 04-research-extract-facts.md   # 抽「需联网验证」清单
│   ├── 04-research-summarize.md       # 联网结果汇总成 research.md
│   ├── 05-draft-outline.md            # 章节划分（按发布优先级）
│   ├── 05-draft-write.md              # 主稿撰写（含完整方法论模板）
│   ├── 05-draft-callout.md            # 整体概要 callout 撰写
│   ├── 05-5-coverage-check.md         # 每板块至少 1 图校验（A8 硬约束）
│   └── 05-5-caption-verify.md         # 图文核对（B1.4）
├── methodology/                       # 方法论参考资料（可在 prompts 里 reference）
│   ├── report-skeleton.md             # 报告骨架样例
│   ├── filter-three-principles.md     # 筛图三原则详解
│   ├── style-rules.md                 # 反 AI 文风 + 数据叙事偏好
│   └── source-attribution.md          # 三种来源严格区分规则
├── src/
│   └── keynote_recap/
│       ├── __init__.py
│       ├── cli.py                     # Click 命令定义
│       ├── config.py                  # TOML 配置加载
│       ├── pipeline.py                # 7 阶段编排
│       ├── stages/
│       │   ├── __init__.py
│       │   ├── download.py            # yt-dlp 封装（默认 1080p60）
│       │   ├── transcribe.py          # 字幕 + whisper fallback
│       │   ├── extract.py             # ffmpeg + frame_scorer + vision filter
│       │   ├── research.py            # LLM + search provider
│       │   ├── draft.py               # LLM 长链路写作（outline + write + callout）
│       │   ├── verify.py              # 5.5：coverage + caption + anti-AI lint
│       │   └── render.py              # md → html
│       ├── llm.py                     # OpenAI 兼容客户端
│       ├── search.py                  # 可插拔 search providers
│       ├── frame_scorer.py            # PIL 多维评分（从 video-recap 移植）
│       ├── checkpoint.py              # 交互式 checkpoint
│       └── cost_tracker.py            # 累计 token / cost 统计
└── tests/
    ├── fixtures/                      # 短样本视频 + 期望产出
    ├── test_pipeline.py
    ├── test_frame_scorer.py
    └── test_methodology_lint.py       # 方法论合规性 lint
```

---

## 七、核心 prompts 设计（节选）

### prompts/03-extract-vision-filter.md
```markdown
# 筛图三原则（Vision LLM 任务）

你将看到一张发布会演讲的截图。请按以下三个原则判断是否保留：

## 原则 1：信息量
保留：包含可读数据、产品 UI、技术架构图、对比表格、产品照片、合作伙伴 logo 墙
拒绝：纯标题文字（如 "Gemini Omni"）、营销 slogan（如 "Bring any idea to life"）、
       品牌 logo 大字（如 "Antigravity 2.0"）、转场页

## 原则 2：相关性
（在 stage 5 章节划分后再次评估，此 stage 仅看信息量）

## 原则 3：去重
（在 stage 5 主稿完成后做相邻图去重）

## 拒绝信号（额外）
- 演讲者远景特写（看不到屏幕内容）
- 空白屏幕 + 单一 Gemini 闪烁 logo
- 黑屏过场

## 输出格式
仅输出 JSON：{"keep": true/false, "reason": "...", "info_density": 0-10}
```

（其他 prompts 同样 1-2 页 markdown，用户可读可改）

---

## 八、风险与缓解

| 风险 | 缓解 |
|---|---|
| LLM 成本不可控 | config 里写 max_tokens / 每 stage 显示累计成本 / 默认用 sonnet 不用 opus |
| Vision 判图不准 | 三阶段 fallback：vision filter → 检查点 1 人工 review → stage 5 主稿时再次评估相关性 |
| 字幕抽不出来 | yt-dlp 字幕 → whisper-cpp 本地 → 用户提供 .srt 三级 fallback |
| 视频太长（3h+） | 分段处理 + 警告 |
| 法律/ToS 问题 | README 明确说"仅用于个人学习/团队内部复盘"；不提供托管版 |

---

## 九、成功标准

1. **保真度**：用同一份 I/O '26 Keynote 链接跑产品，输出与本次手工产物质量差距 < 15%
2. **易用性**：技术圈用户 5 分钟内首次跑通
3. **可定制**：fork 仓库改 prompts/ 不需要懂 Python
4. **成本透明**：每场发布会成本可预估（视频 1.5h + 100 张图，预算 $5-8）

---

## 十、后续展望（不在 MVP 范围）

- 多语言（英文/日文输出）
- 飞书 / Notion / Confluence 直接发布集成
- 风格 few-shot（用户传入参考文章）
- Web 应用（用户量起来再考虑）
- PDF 输出
