# 黄金标准示例 + 配置预设

本目录有两类内容：
1. **配置预设**（`config.preset-*.yaml`）：常见网关场景的开箱即用配置
2. **黄金标准复盘**（`io26-*.md`）：keynote-recap 的回归对比目标

## 配置预设

按你的 LLM 网关情况选一个，复制到 `~/.config/keynote-recap/config.yaml`：

| 预设 | 适用场景 | 单次成本 |
|---|---|---|
| `config.example.yaml` | 通用示例（含全部字段说明） | 视模型而定 |
| `config.preset-gemini-only.yaml` | 网关只支持 Gemini | ~$0.40 |
| `config.preset-claude-only.yaml` | 网关只支持 Anthropic Claude | ~$2.50 |
| `config.preset-openai-only.yaml` | 网关只支持 OpenAI | ~$1.20 |
| `config.preset-mixed-cheap.yaml` | OpenRouter 等多 vendor 代理 | ~$0.60 |

```bash
# 选一个 preset 复制到默认位置
cp docs/examples/config.preset-gemini-only.yaml ~/.config/keynote-recap/config.yaml

# 跑前体检
keynote-recap doctor
```

## 黄金标准

| 文件 | 说明 |
|---|---|
| `io26-keynote-recap.md` | 黄金标准复盘简报（781 行 / 47 张图 / 14 章节） |
| `io26-research-notes.md` | Stage 4 产出的 research notes 形态参考（含联网查证的全部事实点 + 透明声明节） |

## 不在仓库内的产物

| 产物 | 位置 | 说明 |
|---|---|---|
| `io26-keynote-recap.html` | `~/.local/keynote-recap/examples/`（用户本地）| 9MB self-contained HTML（base64 内嵌图）。仓库不放二进制大文件 |
| `frames/` | 同上 | 57 张 1920×1080 抽帧 |
| `frames_official/` | 同上 | 12 张官方图 |

## 用法

### M2 回归测试

```bash
cd <project root>
keynote-recap recap https://www.youtube.com/watch?v=wYSncx9zLIU \
  --output-dir /tmp/io26-rerun \
  --keep-video

# 跑完后 diff 对比黄金标准
diff -u docs/examples/io26-keynote-recap.md /tmp/io26-rerun/report.md
```

期望：差距 < 15%（按 [docs/requirements.md D2](../requirements.md) 验收标准）。

### Prompt 调优参考

修改任何 `prompts/*.md` 后，应该用以下流程检查回归：

1. 跑一遍 keynote-recap recap
2. 输出与本目录 `io26-keynote-recap.md` 做 diff
3. 关键章节字数 / 图量 / 数据点 / 信源数量不应明显倒退

## 黄金标准的关键特征

| 维度 | 数值 |
|---|---|
| 总行数 | 781 |
| 章节数 | 14（含整体概要 + 13 主题章 + 信源说明） |
| 图量 | 47（抽帧 35 + 官方 12）|
| `> 📎 **补充信源**` 块数 | 23 |
| 「核心判断」分句 | 11（概要 8 + 章节 3） |
| 「一点观察」独立观察数 | 8 |
| 「未查到 / 官方未公布」声明 | 7 条 |
| 信源 URL 总数 | 14 |
| 表格数 | 22 |
