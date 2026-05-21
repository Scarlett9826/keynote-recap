---
stage: 5.5.1
name: coverage-check
description: 检查每章节是否至少 1 张图（A8 硬约束）
model: 任意 LLM（也可用纯 Python 实现，不必走 LLM）
temperature: 0.0
max_tokens: 2000
---

# 实现说明

本检查推荐**纯 Python 实现**（无需 LLM），保证零成本和确定性结果。
仅在需要给出修复建议时调用 LLM。

## Python 实现（推荐）

```python
import re

def check_coverage(report_md: str) -> dict:
    """
    检查 report.md 是否每个 ## 章节都至少有 1 张图。

    豁免章节（无图也通过）：
    - "信源说明"
    - "一点观察" 子章节（## 十X、一点观察 整章必须含图量分布，但单个 ### 子项可豁免）
    - "整体概要"（在 callout 块内，不是独立 ## 章节）
    """
    sections = re.split(r"\n## ", report_md)[1:]  # 跳过文档头
    missing = []
    passed = []

    for sec in sections:
        title_line = sec.split("\n")[0].strip()

        # 豁免清单
        if "信源说明" in title_line:
            continue
        if "整体概要" in title_line:
            continue

        # 检查是否含图
        has_image = bool(re.search(r"!\[.*?\]\(.*?\)", sec))

        if has_image:
            passed.append(title_line)
        else:
            missing.append(title_line)

    return {
        "passed": passed,
        "missing": missing,
        "all_pass": len(missing) == 0
    }
```

## LLM 修复建议 prompt（仅在 missing > 0 时调用）

# System

你是一位发布会简报视觉编辑。stage 5 写出的 report.md 有 N 个章节缺图（违反 A8 硬约束「每板块至少 1 张图」）。

你的任务：基于已筛选的全部 frames + 章节内容，为每个缺图章节推荐最合适的 1-2 张帧。

## 推荐优先级

1. **frames/ 已有但未被使用的帧**（首选——省成本）
2. **frames_official/ 官方图**（次选——抽帧拍不到的产品形态）
3. **建议作者重抽特定时间段的帧**（最后手段）

# User Template

## 缺图章节清单

{{missing_sections_with_content}}

## 全部可用帧（含已用 + 未用）

{{all_frames_with_captions}}

## 已用帧清单（不可重复推荐）

{{used_frames}}

## 输出格式

```json
{
  "recommendations": [
    {
      "section": "<章节标题>",
      "recommended_frames": [
        {
          "filename": "frame_42.jpg",
          "source": "frames|frames_official|new_extract",
          "caption": "<完整 caption>",
          "reason": "<为什么推荐>"
        }
      ]
    }
  ]
}
```

每个章节至少推荐 1 张，最多 3 张候选（让作者最终挑选）。
