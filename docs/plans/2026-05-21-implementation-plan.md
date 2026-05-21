# keynote-recap 实施计划

**日期**：2026-05-21
**关联文档**：[requirements.md](../requirements.md) | [design.md](./2026-05-21-keynote-recap-design.md)
**目标**：4 个 milestone 把项目从骨架推到「与本次手工产物质量差距 < 15%」

---

## Milestone 0：项目骨架 + 文档落地（**当前进行中**）

**产出**：用户能 `git clone` 后读完所有文档理解项目意图，但还跑不起来。

### 任务清单

- [x] `docs/requirements.md`（已写）
- [x] `docs/plans/2026-05-21-keynote-recap-design.md` 补强 stage 5.5（已改）
- [ ] `docs/methodology.md`：把所有方法论用一篇长文展开
- [ ] `methodology/*.md`（4 篇分主题资料）
- [ ] `prompts/*.md`（9 份 prompt 拆完）
- [ ] `docs/examples/io26-keynote-recap.{md,html}`（复制成品）
- [ ] `docs/examples/io26-research.md`（复制查证报告）
- [ ] `README.md`（5 分钟上手 + 与现有 video-recap 的关系说明）
- [ ] `LICENSE`（MIT）
- [ ] `pyproject.toml`（基础元数据）
- [ ] `.gitignore`

**验收**：用户读完 README + requirements + methodology，能完整复述 7 个 stage、3 个 checkpoint、筛图三原则、A8 硬约束。

---

## Milestone 1：可跑通 happy path（M1）

**产出**：能用一条命令处理一个 30 分钟以内的小型发布会视频，输出 markdown + html。

**目的**：先把整个 pipeline 通起来，质量先放一边。

### 任务清单

#### M1.1 基础设施（src/keynote_recap/）
- [ ] `cli.py`：Click 主命令 + `run <stage>` 子命令
- [ ] `config.py`：TOML 加载 + 环境变量占位符替换
- [ ] `llm.py`：OpenAI 兼容 client（统一 `chat()` 和 `vision()` 接口）
- [ ] `search.py`：抽象 SearchProvider；先实现 `tavily` + `webfetch_only`
- [ ] `frame_scorer.py`：从 `video-recap/frame_scorer.py` 直接移植
- [ ] `cost_tracker.py`：累计 token / 估算 cost
- [ ] `pipeline.py`：7 stage 编排骨架（先空实现）

#### M1.2 Stage 实现（最小可用）
- [ ] `stages/download.py`：yt-dlp 1080p60 + 默认保留视频（B6.2）
- [ ] `stages/transcribe.py`：YouTube 官方字幕 + 失败 raise（whisper fallback 留 M3）
- [ ] `stages/extract.py`：
    - ffmpeg 均匀抽 100 张
    - frame_scorer 初筛（min_score 30，复用现有阈值）
    - Vision LLM 精筛（`prompts/03-extract-vision-filter.md`）
    - 输出 `frames/` + `frames_meta.json`
- [ ] `stages/research.py`：先简化为单步（抽 facts + search + 汇总一起）
- [ ] `stages/draft.py`：单 prompt 直接产 report.md（先不拆 outline/write/callout）
- [ ] `stages/verify.py`：**只做 5.5.1 coverage check**（A8 硬约束必须有）
- [ ] `stages/render.py`：从 `video-recap/md_to_html.py` 移植

#### M1.3 Checkpoint（先无交互）
- [ ] `checkpoint.py`：先实现 non-interactive 模式（直接通过）
- [ ] `--interactive` 留 M3

**验收**：
```bash
keynote-recap https://youtube.com/watch?v=<某 30min 演讲>
# 跑完 ≤ 30 分钟，产生 report.md + report.html
# Coverage check 通过（每个 ## 章节有图）
# 但允许：caption 不够准、概要不够好、研究不够深
```

---

## Milestone 2：质量达标（M2，**最重要**）

**产出**：用 I/O '26 链接 (`wYSncx9zLIU`) 跑出的 report.md，与本次手工产物质量差距 < 15%。

**目的**：把 prompts 调到能复现 781 行 / 47 图 / 47 个 📎 信源的水准。

### 任务清单

#### M2.1 Stage 5 拆三步
- [ ] `stages/draft.py` 拆成：
    - `draft_outline()` → `outline.md`（章节划分按发布优先级）
    - `draft_write()` → `report.draft.md`（正文 + bullet 层级）
    - `draft_callout()` → 注入概要到顶部（基于正文的整理，A5.1）

#### M2.2 Stage 5.5 完整
- [ ] `5.5.1 coverage_check`：每个 ## 章节至少 1 图（A8）
- [ ] `5.5.2 caption_verify`：Vision LLM 重读每张图 + 校验 caption（B1.4）
- [ ] `5.5.3 anti_ai_lint`：正则扫禁用词（B3.4）

#### M2.3 Research 拆两步
- [ ] `research_extract_facts()` → `research_targets.json`
- [ ] `research_summarize()` → `research.md` 含 unknowns 节（B5.2）

#### M2.4 Prompts 调优（迭代）
- 用 I/O '26 链接反复跑，对比 `examples/io26-keynote-recap.md` 找差距
- 每次差距点修对应 prompt
- 直到达成 [requirements.md D 节验收标准](../requirements.md#d-验收标准quality-bar)

**验收**：
```bash
keynote-recap https://www.youtube.com/watch?v=wYSncx9zLIU \
  -w ./output/io26-rerun
diff output/io26-rerun/report.md docs/examples/io26-keynote-recap.md
# 章节结构匹配
# 47 张图中至少 30 张是抽帧
# 47 个 📎 信源中至少有 25 个被命中
# 文末有「未查到」透明声明节
```

---

## Milestone 3：用户体验完善（M3）

**产出**：CLI 体验对得起开源用户。

### 任务清单

- [ ] `--interactive` 模式：3 个 checkpoint 都暂停 + 自动打开 HTML 预览
- [ ] `whisper-cpp` fallback（无字幕视频）
- [ ] B 站 yt-dlp 链路适配 + 字幕拉取
- [ ] `keynote-recap run <stage>` 单 stage 重跑
- [ ] `--skip download,transcribe` 跳过已完成 stage
- [ ] 进度条 + 实时成本显示
- [ ] `tests/test_pipeline.py`：用 fixture 短视频跑全流程

**验收**：技术圈用户 5 分钟内首次跑通；可用 `Ctrl+C` 安全中断后从 checkpoint 恢复。

---

## Milestone 4：发布上 GitHub（M4）

**产出**：可作为开源项目分发。

### 任务清单

- [ ] `CONTRIBUTING.md`：fork prompts 改风格的指南（不用懂 Python）
- [ ] `docs/customization.md`：如何加 search provider / 改章节模板 / 切风格
- [ ] CI（GitHub Actions）：lint + test
- [ ] 发布到 PyPI（`pip install keynote-recap`）
- [ ] README 加 demo 视频 / 截图
- [ ] 加 issue 模板

---

## 进度追踪

```
M0 [████░░░░░░] 40% — requirements.md + design.md done
M1 [░░░░░░░░░░]  0%
M2 [░░░░░░░░░░]  0%
M3 [░░░░░░░░░░]  0%
M4 [░░░░░░░░░░]  0%
```

---

## 决策点（需要用户确认才能继续）

> 以下决策影响后续工程方向，建议在 M1 开始前明确：

1. **包管理工具**：`uv` 还是 `pip` + `pyproject.toml`？
2. **Click vs Typer**：CLI 框架选哪个？
3. **测试框架**：`pytest` 还是 `unittest`？
4. **search provider 默认值**：Tavily（需 API key）还是 webfetch-only（零成本，质量较低）？
5. **是否纳入 video-recap 已有的 `--template` 系统**：保留 4 个模板（recap/talk/interview/tutorial）还是 MVP 只做 keynote-recap 一种？
   - **建议**：MVP 只做 keynote-recap（聚焦 + 与项目名一致），其他模板留 v2

---

## 风险与缓解（来自 design.md 的延伸）

| 风险 | 影响 milestone | 缓解 |
|---|---|---|
| Vision LLM 视觉判断不一致 | M1, M2 | frame_scorer 初筛（确定性）+ Vision 精筛（创造性）二级链路；M2 加 caption_verify 兜底 |
| 长视频（3h+）超出单次 prompt | M2 | research / draft 拆 stage；按章节分批写后拼接 |
| 字幕无法获取 | M3 | whisper fallback + 用户传入 .srt |
| LLM 成本失控 | 全程 | `cost_tracker.py` 实时显示；每 stage 完成报当前累计 |
| caption 错配反复出现 | M2 | Stage 5.5.2 强制 vision 二次核对（基于本次教训 B1.4） |
| A8（每板块 ≥ 1 图）失败 | M1 | Stage 5.5.1 直接 retry stage 5.2 补图 |
