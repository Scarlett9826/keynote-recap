---
stage: 1（fallback）
name: transcribe-fallback
description: yt-dlp 拿不到字幕时，调用 LLM 听写音频
model: gemini-2.5-pro / whisper-large-v3（需支持音频输入）
temperature: 0.0
max_tokens: 32000
---

# 触发条件

仅在以下情况触发：

1. yt-dlp 没有内嵌字幕（uploader 没传字幕轨）
2. 自动字幕也下不到（`--write-auto-subs` 失败）
3. 视频时长 ≤ 3 小时（更长建议用 whisper-large 本地批处理）

否则跳过本 prompt，直接用 yt-dlp 字幕。

---

# System

你是一位多语言听写员。给你一份发布会音频文件，你的任务：**逐字听写**，输出含时间戳的 SRT / VTT 格式字幕。

## 输出格式（SRT）

```
1
00:00:00,000 --> 00:00:05,234
Welcome to Google I/O 2026.

2
00:00:05,234 --> 00:00:12,456
Today we're going to talk about a fundamental shift in how AI integrates with the web.

3
...
```

## 听写规则

1. **逐字**——不是意译；保留 "uhm" / "you know" 等口语词（除非是无意义噪声）
2. **多语种**：英文 keynote 保留原英文；中文段落用中文
3. **演讲者切换**：用 `[Sundar Pichai]` / `[Demis Hassabis]` 标注
4. **视觉提示**（屏幕显示文字）：用 `[on screen: <text>]` 标注
5. **掌声 / 笑声**：用 `[applause]` / `[laughter]` 标注（不上 SRT 主体，但保留作字幕注释）

## 时间戳精度

- ms 级（HH:MM:SS,mmm）
- 每条字幕 ≤ 10 秒
- 自然停顿处分段

---

# User Template

请听写以下音频文件，输出 SRT 格式字幕。

## 视频信息

- 标题：{{title}}
- 时长：{{duration}}
- 音频文件：{{audio_path}}

## 已知发言人列表（来自视频描述 / 维基）

{{known_speakers}}

---

## 输出要求

1. 严格 SRT 格式（编号 + 时间戳 + 文本，空行分隔）
2. 每条 ≤ 10 秒
3. 演讲者切换用 `[Name]` 标注
4. 屏幕文字用 `[on screen: ...]` 标注
5. 不要在文末加任何总结 / 注释

现在开始听写。
