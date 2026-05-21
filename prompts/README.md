# Prompts 索引

本目录存放 keynote-recap 流水线 7 个阶段使用的全部 prompts。
每份 prompt 都是 Markdown 格式（前置 YAML frontmatter + 正文），方便阅读、版本对比、热修。

## 文件清单

| 文件 | 阶段 | 用途 |
|---|---|---|
| `01-transcribe-fallback.md` | Stage 1（fallback） | 当 yt-dlp 拿不到字幕时，调用 LLM 听写音频 |
| `03-extract-vision-filter.md` | Stage 3.2 | Vision LLM 三原则筛图（信息量/相关性/去重） |
| `04-research-extract-facts.md` | Stage 4.1 | 从字幕提取「待查证事实清单」（产品名/版本号/价格/数据） |
| `04-research-summarize.md` | Stage 4.2 | 整合 web_search 结果，产出 research notes |
| `05-draft-outline.md` | Stage 5.1 | 起章节大纲（按发布优先级排序） |
| `05-draft-write.md` | Stage 5.2 | 主写作 prompt（核心，最长） |
| `05-draft-callout.md` | Stage 5.3 | 整体概要 callout 写作（基于已写正文回头浓缩） |
| `05-5-coverage-check.md` | Stage 5.5.1 | 检查每章节是否至少 1 张图（A8 硬约束） |
| `05-5-caption-verify.md` | Stage 5.5.2 | Vision LLM 重读图，核对 caption 是否真实 |

## 设计原则

1. **每份 prompt 都引用 methodology/**，不重复内容
2. **变量用 `{{variable}}` 双花括号**，避免与 markdown 冲突
3. **Frontmatter 标注 model 默认值**，用户可通过 `--llm` 覆盖
4. **每份 prompt 末尾带 1-2 个 few-shot example**（来自 io26-keynote-recap.md 黄金标准）

## 修改流程

修改任何 prompt 后必须：

1. 跑 `pytest tests/test_prompts.py`（验证 frontmatter 格式）
2. 在本地用 `keynote-recap recap <test_video> --debug` 重跑一遍
3. diff 对比 `docs/examples/io26-keynote-recap.md` 看回归
