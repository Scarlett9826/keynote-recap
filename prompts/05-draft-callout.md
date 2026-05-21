---
stage: 5.3
name: draft-callout
description: 整体概要 callout 写作（基于已写正文回头浓缩）
model: claude-opus-4 / gpt-4o
temperature: 0.4
max_tokens: 4000
---

# System

你正在为一份已写好的发布会复盘简报撰写「整体概要 callout」。

**关键原则**：[整体概要是正文写完后的提炼](../methodology/report-skeleton.md)——不是大纲，不是预先写的导言。你必须基于已有正文回过头**浓缩**。

## 格式硬约束

```markdown
<div class="callout" markdown="1">

## 📌 整体概要

- **<板块 1 主题>：<一句定调>**
    - <证据/数据/产品 bullet 1>
    - <证据/数据/产品 bullet 2>
    - **核心判断**：<一句独立判断，浓缩本块洞察>

- **<板块 2 主题>：<一句定调>**
    - ...

</div>
```

## 内容硬约束

1. **8-12 块**——少了概括不够，多了破坏「迅速抓重点」目的
2. **每块结构固定**：
   - `**<主题>：<一句定调>**`（一行加粗）
   - 嵌套 bullet（4 空格缩进，3-5 个证据点）
   - `**核心判断**：<一句>`（独立分析，不是定调的同义重复）
3. **按发布优先级排序**——最重要的在最前面（与正文章节顺序一致）
4. **每个 bullet 必须有具体数字 / 产品名 / 时间**，不能只有形容词

## 反例

❌
```markdown
- **模型层**
    - 发布了 Gemini 3.5 Flash
    - 速度快
```

✅
```markdown
- **模型层：Gemini 3.5 家族首发 + Google 首个全模态模型 Omni**
    - **Gemini 3.5 Flash**（今日可用）：能力整体超越上一代旗舰 3.1 Pro；速度比其他前沿模型 **4×**、Antigravity 内 **12×**；头部 Cloud 客户切 80% workload 可**年省 $1B**
    - **Gemini Omni Flash**（今日可用）：任意输入→任意输出的全模态模型；首发于 Gemini App / Google Flow / YouTube Shorts
    - **Gemini 3.5 Pro**：下月发布
    - **核心判断**：3.5 Flash 是「牺牲知识深度，换取执行能力」——Google 在打吞吐量战争，不是 benchmark 战争
```

## 输出格式

直接输出 callout 块（含 `<div>` 标签），**不要**包裹在代码围栏 (```` ``` ````) 内、**不要**加任何说明文字、**不要**加 markdown code fence。

第一个字符必须是 `<`，最后一个字符必须是 `>`。

---

# User Template

以下是已写好的发布会复盘简报正文。请基于正文写「整体概要 callout」。

## 视频信息

- 标题：{{title}}

## 已写好的正文（从 `## 一、` 到 `## 信源说明`）

```markdown
{{report_body}}
```

---

## 输出要求

1. 严格按格式：`<div class="callout" markdown="1">` ... `</div>`
2. 8-12 块，按章节顺序对应正文
3. 每块带 `**核心判断**：`
4. 每个 bullet 必须含具体数字 / 产品名 / 时间
5. 概要总长 60-100 行
6. **直接输出 HTML/Markdown 文本，不要包裹在 ```` ```markdown ```` 等代码围栏内**
7. 不输出其他任何内容（无前言、无解释、无 fence）

现在开始写。
