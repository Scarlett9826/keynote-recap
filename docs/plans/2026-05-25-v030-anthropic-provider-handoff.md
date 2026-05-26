# v0.3.0 交接文档 — anthropic provider 支持

> **给接手 agent 的话**：今晚目标是发布 v0.3.0，新增 anthropic-native provider 支持。
> 用户已经走过完整诊断、所有判断都已落地，你的任务是**执行**而不是重新设计。
> 读完这份文档，按 Checklist 顺序做。不要扩大范围、不要调整方法论、不要重新讨论。
> 如果遇到本文档没覆盖的边界情况，先 question 用户，不要假设。
>
> 当前位置：`/Users/mi/Desktop/截图提取/keynote-recap/`，分支 `main`，最新 commit `84da8d3`（v0.2.5.1 hotfix），工作树干净。
> Python venv：`.venv/bin/python`，全套测试 `.venv/bin/python -m pytest tests/ -q`，目前 124 passing。
> Lint：`.venv/bin/ruff check src/ tests/ --select=E,F,W --ignore=E501,E402`。

---

## 1. 必须先理解的"为什么"

### 用户的一句话定调

> "我觉得产出质量稳定最重要"

**所有设计决策围绕这条**。不要为了"配置灵活性"放任 agent 偷工减料、不要为了"快速发布"砍掉防御层。

### 用户当前痛点链（你现在要解决的）

1. **your-gateway gateway 上 Claude 模型走 Anthropic 协议，不是 OpenAI 协议**
   - `https://your-gateway.example.com/v1/chat/completions` → 不挂 Claude
   - `https://your-gateway.example.com/anthropic/v1/messages` → 挂 `your-vendor/claude-sonnet-4-6` / `your-vendor/claude-opus-4-7` / `your-vendor/claude-haiku-4-5`
2. **keynote-recap 当前 LLMClient 只会讲 OpenAI 协议**（`src/keynote_recap/llm_client.py`，171 行，用 `openai` SDK）
3. **`config.LLMConfig` 已有 `provider: Literal["openai-compatible", "anthropic-native"]` 字段**（schema 早已设计好）—— 但 LLMClient 实现里**完全没用 provider 分支**。
4. 用户实战跑 acme-launch-2026（已缓存 video + 80 帧 + zh.srt，stage 1-2 已完成）时，stage 3 vision call 全部 `BadRequestError: Param Incorrect: Not supported model` —— 因为模型 ID + endpoint 错配。
5. fallback 启发式选帧路径还有 pydantic schema bug：`SelectedFrame.source` literal 不接受 `frame_extract` 之外的值，但 fallback 填了别的值。**这是 v0.3.0 范围外的问题，先记着，今晚不修。**

### 已经决定的事（不要重新讨论）

- ✅ **v0.3.0 = 仅 anthropic provider 支持**。其他治本动作（模型白名单收紧 / draft linter / 字幕缺失硬 abort）等真产出出来后**根据真产出质量**决定，不基于推测设计。
- ✅ 用 `anthropic` 官方 Python SDK，不手搓 HTTP。理由：vision payload 转换、retry、stream（未来）都是 SDK 已实现的。
- ✅ 不破坏 v0.2.5.1 的 banner / verify / recap-and-verify / methodology / 所有现有防御层。
- ✅ 不破坏 OpenAI provider 路径（向后兼容）。

---

## 2. 全局背景速读

| 项 | 值 |
|---|---|
| 当前版本 | v0.2.5.1（commit `84da8d3`） |
| 目标版本 | v0.3.0 |
| 测试基线 | 124 passed |
| ruff 基线 | clean |
| 用户机器路径 | `/Users/mi/Desktop/截图提取/keynote-recap` |
| 远程 | `git@github.com:Scarlett9826/keynote-recap.git` |
| 已发布 tags | v0.2.0 ~ v0.2.5.1（含 v0.2.4.1） |

### v0.2.5 三层防御（不要碰）

1. **AGENTS.md**（项目根，153 行硬核明令式 agent 指南）
2. **HTML 顶部 sticky 橙 banner**（`stages/render.py::_build_top_banner`）
3. **`keynote-recap verify <file>`**（`src/keynote_recap/verify.py`，pure-function 模块，二元 OK/FAIL）
4. **`keynote-recap recap-and-verify <url>`**（`cli.py` 组合命令）

这些是产品的护城河。**任何改动**都要保证这四件还能正常工作。

### v0.2.5.1 hotfix 修了什么（不要回退）

`preflight_env.check_api_key` 的 severity 从 `blocker` 降为 `warning`。原因：v0.2.5 静悄悄升 blocker 触发 hard abort，破坏了"用户用 corporate gateway/agent-host proxy"场景。

**重要**：v0.3.0 的 anthropic provider 配置场景里，`api_key_env` 仍然要被检查（warning 级别）。不要在 `check_api_key` 里加 provider 分支搞特殊处理——保持简单。

---

## 3. 用户已确认的 your-gateway gateway 实测数据

> 这些是真实 curl 验证过的、在用户机器上 work 的事实。不要质疑、直接用。

### 协议路径

```
Endpoint:  https://your-gateway.example.com/anthropic/v1/messages
Method:    POST
Auth:      Authorization: Bearer <key>   (也接受 x-api-key: <key>，用 Authorization 即可)
Header:    anthropic-version: 2023-06-01
           Content-Type: application/json
```

### 已验证可用模型

```
your-vendor/claude-sonnet-4-6     (Anthropic, 200K ctx, vision ✓)
your-vendor/claude-opus-4-7       (Anthropic, 200K ctx, vision ✓)
your-vendor/claude-haiku-4-5      (Anthropic, 200K ctx, vision ✓)
```

注意 `your-vendor/` 前缀。用户一开始 config.yaml 配的是 `pa/claude-sonnet-4-6`（缺前缀）+ 走 `/v1` 路径，两处都错。新版要让用户能干净地改 config 直接 work。

### 实测 vision payload（这是 ground truth）

请求（用户已 curl 验证返回成功）：

```json
POST https://your-gateway.example.com/anthropic/v1/messages
Authorization: Bearer <key>
anthropic-version: 2023-06-01

{
  "model": "your-vendor/claude-sonnet-4-6",
  "max_tokens": 200,
  "messages": [{
    "role": "user",
    "content": [
      {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "<b64>"}},
      {"type": "text", "text": "用 30 字以内描述这张图核心内容"}
    ]
  }]
}
```

响应（实测）：

```json
{
  "model": "pa/claude-sonnet-4-6",
  "id": "msg_bdrk_...",
  "type": "message",
  "role": "assistant",
  "content": [{"type": "text", "text": "**ACME Phone Pro 发布会**：展示其屏幕清晰度媲美2K..."}],
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 585,
    "output_tokens": 57,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0
  }
}
```

注意三件事：
1. response 里 model 字段会回成 `pa/claude-sonnet-4-6`（去掉 `your-vendor/` 前缀），这是 gateway 行为，不影响功能。
2. usage 里有 `cache_creation_input_tokens` / `cache_read_input_tokens`——anthropic prompt caching feature。今晚不用管，但 cost_tracker 别因为这俩字段崩。
3. content 是个 list、第一个 element type=text，文本在 `.text`——和 OpenAI `choices[0].message.content` 不一样。

---

## 4. 代码改动 Checklist（按顺序做、每步打勾）

### 4.1 添加 anthropic 依赖

文件：`pyproject.toml`

在 `dependencies` 列表加：
```
"anthropic>=0.40.0",
```

`anthropic>=0.40.0` 选这个版本因为它已经稳定支持 messages API + vision + 完整 type hint。装好后跑：

```bash
.venv/bin/pip install -e .
.venv/bin/python -c "import anthropic; print(anthropic.__version__)"
```

### 4.2 LLMClient 重构 —— 按 provider 分发

文件：`src/keynote_recap/llm_client.py`

**当前结构**（171 行）：
- `class LLMClient` 在 `__init__` 直接 `self.client = OpenAI(...)`
- `chat()` / `chat_with_images()` 都直接 `self.client.chat.completions.create(...)`

**目标结构**：
- `class LLMClient` 是 **公开 API 不变**（`chat` / `chat_with_images` / `parse_json` 签名 + 返回值 100% 不变 —— 因为 stages/extract.py / stages/draft.py 等多处在调用，不要级联改动）
- 内部按 `cfg.provider` 在 `__init__` 决定底层 client + chat 方法
- 不要用 if 散在每个方法里——用 `_OpenAIBackend` / `_AnthropicBackend` 两个类各实现 `chat(...)` / `chat_with_images(...)`，然后 `LLMClient` 转发。

#### 推荐结构（不要发明别的）

```python
class _Backend:
    """Internal protocol — chat / chat_with_images return (text, in_tok, out_tok)."""
    def chat(self, *, model, system, user, messages, temperature, max_tokens, json_mode) -> tuple[str, int, int]: ...
    def chat_with_images(self, *, model, system, user_text, image_paths, temperature, max_tokens, json_mode) -> tuple[str, int, int]: ...


class _OpenAIBackend(_Backend):
    """Existing v0.2.x behavior, copied verbatim from current LLMClient."""
    def __init__(self, cfg: LLMConfig) -> None:
        from openai import OpenAI
        api_key = os.getenv(cfg.api_key_env)
        if not api_key:
            raise RuntimeError(...)
        self.client = OpenAI(api_key=api_key, base_url=cfg.base_url, timeout=cfg.timeout_s)
    # ... chat / chat_with_images 是从原文件复制粘贴 ...


class _AnthropicBackend(_Backend):
    """v0.3.0: native Anthropic /messages API."""
    def __init__(self, cfg: LLMConfig) -> None:
        from anthropic import Anthropic
        api_key = os.getenv(cfg.api_key_env)
        if not api_key:
            raise RuntimeError(...)
        # Anthropic SDK 默认 base_url 是 api.anthropic.com，要 override
        self.client = Anthropic(
            api_key=api_key,
            base_url=cfg.base_url,
            timeout=cfg.timeout_s,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def chat(self, *, model, system="", user="", messages=None, temperature=0.5, max_tokens=8000, json_mode=False) -> tuple[str, int, int]:
        # Anthropic /messages 不接受 'system' role in messages list — 用单独 system 参数
        if messages is None:
            msgs = [{"role": "user", "content": user}]
        else:
            # 拆出 system role，剩下转成 anthropic messages
            system_parts = [m["content"] for m in messages if m.get("role") == "system"]
            if system_parts:
                system = "\n\n".join(system_parts) if not system else system
            msgs = [m for m in messages if m.get("role") != "system"]

        # JSON mode workaround：anthropic 没 response_format。
        # 在 system prompt 末尾追加强制指令，让模型只输出 JSON。
        if json_mode:
            json_directive = (
                "\n\n你必须只输出有效 JSON 对象，不要有任何前后文字、不要 markdown 代码块包裹。"
            )
            system = (system or "") + json_directive

        kwargs = {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        resp = self.client.messages.create(**kwargs)
        # response.content 是 list of blocks; 取所有 text block 拼起来
        text = "".join(b.text for b in resp.content if b.type == "text")
        usage = resp.usage
        return (
            text,
            getattr(usage, "input_tokens", 0),
            getattr(usage, "output_tokens", 0),
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def chat_with_images(self, *, model, system="", user_text="", image_paths, temperature=0.2, max_tokens=4000, json_mode=False) -> tuple[str, int, int]:
        # Anthropic vision content blocks
        content = []
        for p in image_paths:
            data = base64.b64encode(p.read_bytes()).decode("ascii")
            mime = "image/jpeg"  # TODO: detect by extension; .jpg/.jpeg → jpeg, .png → png
            if p.suffix.lower() == ".png":
                mime = "image/png"
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": data},
            })
        content.append({"type": "text", "text": user_text})

        if json_mode:
            json_directive = "\n\n你必须只输出有效 JSON 对象，不要有任何前后文字、不要 markdown 代码块包裹。"
            system = (system or "") + json_directive

        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        resp = self.client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if b.type == "text")
        usage = resp.usage
        return (
            text,
            getattr(usage, "input_tokens", 0),
            getattr(usage, "output_tokens", 0),
        )


class LLMClient:
    """Public API — unchanged from v0.2.x."""
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        if cfg.provider == "anthropic-native":
            self._backend: _Backend = _AnthropicBackend(cfg)
        else:  # "openai-compatible" 或缺省
            self._backend = _OpenAIBackend(cfg)

    def chat(self, **kw) -> tuple[str, int, int]:
        return self._backend.chat(**kw)

    def chat_with_images(self, **kw) -> tuple[str, int, int]:
        return self._backend.chat_with_images(**kw)

    @staticmethod
    def parse_json(text: str) -> Any:
        # 不变，从原文件复制
        ...
```

注意：

- 不要把 `run_parallel` 函数挪进 backend 类——它是模块级函数、和 backend 无关。保持原位。
- `tenacity` retry 装饰器在 backend method 上加；和 v0.2.x 一致。
- `LLMConfig.provider` 字段不需要改 —— schema 已经定义好了。

### 4.3 处理 anthropic 没有的 json_mode

OpenAI 的 `response_format={"type":"json_object"}` 会强制模型输出 JSON。Anthropic 没这个。

**对策**：在 system prompt 末尾追加强制指令（见上面代码 `json_directive`）。
**注意**：现有 `LLMClient.parse_json(text)` 已经能 strip markdown fence —— 即使 anthropic 偶尔输出 ```json ... ``` 也会被 strip。所以**不需要改 parse_json**。

### 4.4 verify_chat 输出 token 字段差异

OpenAI usage：`prompt_tokens` / `completion_tokens`
Anthropic usage：`input_tokens` / `output_tokens`

cost_tracker 记录的是 (text, input_tokens, output_tokens)。我已经在 `_AnthropicBackend` 里把 anthropic 的 `input_tokens`/`output_tokens` 直接 return —— 接口对齐。

但 `cost_tracker.py` 内部如果还硬编码"prompt_tokens" / "completion_tokens"字段名，要查一下。你做之前先：

```bash
grep -rn 'prompt_tokens\|completion_tokens' /Users/mi/Desktop/截图提取/keynote-recap/src/
```

如果 cost_tracker 里有，要改成接口里 (in_tok, out_tok) 元组的位置参数。

### 4.5 单元测试

文件：`tests/test_smoke.py`

加一组 `test_v030_anthropic_*` 测试。**不要烧 token**——全部 mock anthropic SDK。

要覆盖的场景：

```python
def test_v030_anthropic_backend_routes_via_messages_api(monkeypatch):
    """provider=anthropic-native → uses anthropic SDK, not openai SDK."""
    # mock anthropic.Anthropic.messages.create
    # 调 LLMClient(cfg with provider=anthropic-native).chat(...)
    # assert anthropic SDK 被调到，openai SDK 没被调到

def test_v030_anthropic_chat_basic_text(monkeypatch):
    """Plain text chat returns (text, in_tok, out_tok)."""
    # mock 返回 anthropic.types.Message 风格 response
    # assert text 拼接、token 字段正确

def test_v030_anthropic_chat_with_images_payload(monkeypatch):
    """Vision call uses anthropic block format (image + text)."""
    # mock; 验证发出的 messages[0].content 里有 type=image / type=text 两个 block
    # 验证 image source.type=base64, source.media_type=image/jpeg

def test_v030_anthropic_json_mode_appends_system_directive(monkeypatch):
    """json_mode=True → system prompt 末尾追加 JSON 强制指令。"""
    # mock; 检查发出去的 system 参数包含 "只输出有效 JSON" 字样

def test_v030_anthropic_extracts_system_from_messages_list(monkeypatch):
    """If messages list contains role=system, it's lifted out into the
    Anthropic-native top-level system parameter."""

def test_v030_openai_provider_still_works_unchanged(monkeypatch):
    """Regression: provider=openai-compatible (default) goes through
    _OpenAIBackend with byte-identical behavior to v0.2.5.1."""

def test_v030_provider_default_is_openai_compatible():
    """LLMConfig() default — backward compat."""
    from keynote_recap.config import LLMConfig
    assert LLMConfig().provider == "openai-compatible"

def test_v030_png_frames_use_image_png_media_type(monkeypatch):
    """If image path ends with .png, media_type is image/png; else image/jpeg."""
```

预计 6-8 个新测试。目标：**全套测试 132+ passed**。

### 4.6 doctor 命令支持 provider 显示

文件：`src/keynote_recap/cli.py`

`doctor` 命令现在 print 的 model resolution 部分要带上 provider 信息。简单加一行：

```python
console.print(f"  provider: {cfg.llm.provider}")
console.print(f"  base_url: {cfg.llm.base_url}")
```

放在 "Resolved per-stage models:" 这一段附近。

如果你看 cli.py 找不到那段，搜 `Resolved per-stage models`。

### 4.7 文档

#### `README.md`

加一节"Provider 配置"，给 anthropic 配置示例：

```yaml
# ~/.config/keynote-recap/config.yaml
llm:
  provider: anthropic-native    # ← v0.3.0 新增
  base_url: https://your-gateway.example.com/anthropic/v1
  api_key_env: OPENAI_API_KEY
  models:
    extract: your-vendor/claude-sonnet-4-6
    research: your-vendor/claude-sonnet-4-6
    draft: your-vendor/claude-opus-4-7        # 用 opus 写 draft 更稳
    verify: your-vendor/claude-sonnet-4-6
    transcribe: your-vendor/claude-sonnet-4-6
```

**不要**在 README 里贴用户那个 your-gateway 内部 URL —— 用 `your-gateway.example.com` 占位。用户自己的 URL 在他自己的 config.yaml 里。

#### `AGENTS.md`

不需要大改。但在 §3 "How to actually run it" 的 preflight 一段，把"`OPENAI_API_KEY` 必须设置"那条注释加一句：

> v0.3.0 起，`api_key_env` 字段决定读哪个 env var；如果用户走 anthropic-native provider 配置自己的 gateway，env var 名字可能不是 OPENAI_API_KEY。读 ~/.config/keynote-recap/config.yaml 的 `llm.api_key_env` 字段确认。

#### `CHANGELOG.md`

顶部加 0.3.0 entry。模板：

```markdown
## [0.3.0] — Anthropic-native provider support (2026-05-26)

### Added

- **Native Anthropic Messages API support.** `LLMConfig.provider` is now
  honored at the client level; setting `provider: anthropic-native`
  routes all stages through the `anthropic` SDK and the `/messages`
  endpoint instead of OpenAI's `/chat/completions`. This unblocks users
  whose corporate LLM gateway exposes Claude via the native Anthropic
  protocol (e.g. Bedrock-style `<provider>/pa/claude-sonnet-4-6`
  model IDs reachable only via `/anthropic/v1/messages`). Vision
  payloads are converted to Anthropic's content-block format
  (`{type:"image", source:{type:"base64", media_type, data}}`).

- **Anthropic JSON-mode workaround.** Anthropic Messages has no
  `response_format` parameter. When the caller passes `json_mode=True`,
  the backend appends a strict-JSON directive to the system prompt; the
  existing `LLMClient.parse_json` already strips markdown fences, so
  end-to-end behavior matches OpenAI json_mode for the project's needs.

### Changed

- `LLMClient` is now a thin facade dispatching to `_OpenAIBackend` or
  `_AnthropicBackend` based on `cfg.llm.provider`. Public API
  (`chat` / `chat_with_images` / `parse_json` signatures and return
  shapes) is byte-identical to v0.2.5.1; no callers in `stages/*` need
  changes.

- `keynote-recap doctor` now prints the active provider and base_url so
  config errors surface immediately.

### Tests

- 8 new `test_v030_anthropic_*` tests covering: provider routing,
  text chat, vision payload format, json_mode directive injection,
  system role lifting, OpenAI-provider regression, default provider,
  PNG vs JPEG media_type detection. All mocked — no token spend.

- Total: 132+ passing (was 124 in v0.2.5.1).

### Acknowledged limitations

- Stage 3 fallback path (when ALL vision batches fail and the
  heuristic scorer promotes top-N rejected frames) has a pre-existing
  pydantic schema bug: `SelectedFrame.source` literal does not accept
  the value the fallback fills in. v0.3.0 does NOT fix this; tracked
  for v0.3.1. With v0.3.0's anthropic provider working correctly, the
  fallback path becomes much rarer and the bug is less urgent.

- Anthropic prompt-caching tokens (`cache_creation_input_tokens` /
  `cache_read_input_tokens` in usage) are not yet surfaced to
  cost_tracker. Tracked for v0.3.1.
```

### 4.8 版本号

- `pyproject.toml`: `version = "0.3.0"`
- `src/keynote_recap/__init__.py`: `__version__ = "0.3.0"`

---

## 5. 跑通真产出（验证 v0.3.0 是否真 work）

代码改完、测试过、ruff 干净后，跑一次端到端真产出验证。

### 用户已缓存的 baseline

```
/Users/mi/Desktop/截图提取/output/acme-launch-2026/
├── video.mp4              191 MB
├── subtitle.zh.srt        123 KB
├── frames_raw/            80 帧 jpeg
├── metadata.json          25 KB
└── state.json             92 KB (last_completed_stage = 2.0)
```

视频是 https://www.bilibili.com/video/BVxxxxxxxxxx/（ACME Phone Max 发布会）。stage 1-2 已完成。stage 3 起从未跑成功过。

### config 设置

让用户**临时**改 `~/.config/keynote-recap/config.yaml`（用户已说倾向不写 key 进 config，所以只改 base_url + provider + model id）：

```yaml
llm:
  provider: anthropic-native              # ← 改这个
  base_url: https://your-gateway.example.com/anthropic/v1   # ← 改这个（加 /anthropic）
  api_key_env: OPENAI_API_KEY             # 保持
  timeout_s: 600
  max_retries: 3
  models:
    extract: your-vendor/claude-sonnet-4-6    # ← 加 your-vendor/ 前缀
    research: your-vendor/claude-sonnet-4-6
    draft: your-vendor/claude-sonnet-4-6      # 用户说全 sonnet 跑
    verify: your-vendor/claude-sonnet-4-6
    transcribe: your-vendor/claude-sonnet-4-6
```

### 跑命令

**关键**：用户的 key 不能写进 ~/.zshrc（用户明确选了"不落盘"路径）。每次跑用临时 env：

```bash
cd /Users/mi/Desktop/截图提取/keynote-recap
OPENAI_API_KEY="<让用户告诉你或从此前对话 transcript 里取>" \
  .venv/bin/keynote-recap recap "https://www.bilibili.com/video/BVxxxxxxxxxx/" \
  --output-dir /Users/mi/Desktop/截图提取/output/acme-launch-2026 \
  --start-stage 3 \
  --end-stage 6 \
  --no-checkpoint
```

预期：
- stage 3 (extract): 5-10 分钟，约 80 帧分 8 batch 走 anthropic vision，每 batch 2-3 个 LLM call
- stage 4 (research): 1-2 分钟
- stage 5 (draft): 5-10 分钟
- stage 5.5 (verify): 3-5 分钟
- stage 6 (render): 几秒

成功标志：
- exit 0
- `output/acme-launch-2026/report.md` 存在、有 frontmatter（version + content-sha256）
- `output/acme-launch-2026/report.html` 存在、4-8 MB
- 跑 `keynote-recap verify output/acme-launch-2026/report.html` 应输出 `OK: ...`
- 用户能 open report.html 看到顶部橙 banner、内容是关于 ACME 17 Max

如果 stage 3 失败，**先看错误信息**：
- 如果是协议问题（headers / endpoint path），重看 §3 的 ground truth curl
- 如果是 SDK 版本问题，`pip show anthropic`
- 如果是 token 限制，单 batch 80 帧太多，考虑减 BATCH_SIZE（但这是 stages/extract.py 的事，今晚不在范围）

---

## 6. 发布 Checklist

```bash
cd /Users/mi/Desktop/截图提取/keynote-recap

# 1. 确认 working tree 干净
git status -s

# 2. 全套测试
.venv/bin/python -m pytest tests/ -q --tb=short
# 期望：132+ passed

# 3. ruff
.venv/bin/ruff check src/ tests/ --select=E,F,W --ignore=E501,E402

# 4. 跑 §5 真产出验证
# 必须用户在场、用户提供 key
# 必须 verify 输出 OK
# 必须用户 open html 确认 banner 在、内容关于 ACME

# 5. commit
git add -A
git commit -m "feat(p11): v0.3.0 anthropic-native provider support

LLMClient is now a thin facade dispatching to _OpenAIBackend or
_AnthropicBackend based on cfg.llm.provider. Anthropic backend uses
the native /messages API and converts vision payloads to content-block
format. JSON-mode is emulated via system-prompt directive.

Public LLMClient API unchanged; no caller in stages/* needs updates.

Tested end-to-end on a Bilibili keynote with sonnet-4-6 via your-gateway
gateway; stage 3-6 complete successfully and verify exits OK.

- pyproject.toml: anthropic>=0.40.0 dependency
- src/keynote_recap/llm_client.py: provider dispatch
- src/keynote_recap/cli.py: doctor prints provider+base_url
- tests/test_smoke.py: 8 new test_v030_anthropic_* (mocked)
- README.md / AGENTS.md / CHANGELOG.md: anthropic provider docs

132 tests pass; ruff clean.
"

# 6. tag + push（只在用户明确确认后做）
git tag v0.3.0
git push origin main
git push origin v0.3.0
```

---

## 7. 不要做的事（重要）

❌ **不要**改 methodology.py 的任何常量。所有方法论合约 v0.3.0 不动。
❌ **不要**改 stages/*.py 的任何文件。LLMClient 接口不变 = stages 不需要改。如果你发现某个 stage 调用要改 —— 先停，question 用户。
❌ **不要**改 verify.py / render.py 的 banner 逻辑。v0.2.5 防御层完整保留。
❌ **不要**碰 frame_scorer 的 fallback 路径（pydantic source bug）。这是 v0.3.1 的事。
❌ **不要**把用户的 your-gateway 内部 URL 或任何 key 提交进任何文件（README、CHANGELOG、tests）。用 `your-gateway.example.com` 之类占位。
❌ **不要**自己手搓 Anthropic HTTP 调用——必须用 `anthropic` SDK。
❌ **不要**升级现有依赖版本（openai SDK 等）。只新增 anthropic。
❌ **不要**做"顺便重构"。任何 v0.3.0 范围外的改动等下一个版本。
❌ **不要**改 default `LLMConfig.provider` 值。保持 `openai-compatible` 是默认 = 完美向后兼容。

---

## 8. 关键决策树（你卡住时往这看）

| 情况 | 做什么 |
|---|---|
| anthropic SDK 版本要选 | `>=0.40.0`。0.40 之前 messages API 还在演进，0.40 后稳定。 |
| OpenAI provider 测试还过吗 | 必须过。改完跑全套测试，old `test_*` 一个不许挂。 |
| anthropic SDK 需要 base_url 自定义吗 | 是。`Anthropic(api_key=..., base_url=cfg.base_url)`，覆盖默认 api.anthropic.com。 |
| anthropic SDK 用 timeout 怎么传 | `Anthropic(timeout=cfg.timeout_s)`，httpx 风格。 |
| messages 里有 system role 怎么办 | Anthropic 不接受 messages 列表里的 system role。要把 system 内容拎出来作为 top-level `system` 参数传。我已经在 §4.2 代码示例里写了。 |
| 实测 anthropic 返回 model 字段会丢 your-vendor/ 前缀 | 不影响功能，gateway 行为，忽略。 |
| 用户问能不能也加 google gemini provider | 不是 v0.3.0 范围。回答"v0.3.1 backlog"。 |
| 用户问能不能打成 skill 让 agent 直接跑 | 用户已明确 "产出质量稳定最重要"，skill-only 路径会牺牲质量稳定性。skill 作为"调 CLI 的薄入口"是 v0.3.1+ 候选，今晚不做。 |
| 用户的 key 又被贴出来 | 不要把 key 写入任何文件。临时 env var 用法见 §5。建议用户轮换 key（已在前面对话说过）。 |
| stage 3 跑出来还是失败 | 先看具体 error。如果是 anthropic SDK 报错，贴报错原文给用户、不要自己猜。如果是 stages/extract.py 的 pydantic schema —— 那是已知的 fallback 路径 bug，**不应该被触发**（因为现在 anthropic vision 应该 work）。 |
| 跑出来质量很差（结构散、引用少） | 记下、不修。这正是用户想用 anthropic 后看真产出再决定 v0.3.1 范围的目的。 |

---

## 9. 用户偏好速查（不要违反）

- 公开仓库铁律：**禁** your-company/your-gateway/bytedance 等公司词及 PII 出现在任何提交文件里。用 `your-gateway.example.com` 占位。
- commit 风格：`feat(p<N>): <数字>` 或 `fix(p<N>): <说明>`。这次是 p11。
- 远程写之前用 question tool 确认（git push / tag 等）。
- 文风零容忍：**禁**「巨大/显著/革命性/让我们/不仅仅是/总而言之/惊人/飞跃」等。CHANGELOG / README 写作里也要遵守。
- 不允许 emoji（除 📎/✅）。
- 用户喜欢"项目方法论 = 代码合约"。CHANGELOG 写"acknowledged limitations"段落是好习惯。
- 用户的 commit 描述喜欢具体测试数 / 文件清单。我在 §6 commit message 模板里已经按这个风格写了。

---

## 10. 验证文档完整性（自检 Checklist）

读完这份文档，你应该能立刻回答：

- [ ] v0.3.0 范围是什么？只有 anthropic provider 支持，其他治本动作都不在范围。
- [ ] 不要碰哪些文件？methodology.py / stages/*.py / verify.py / render.py 的 banner / frame_scorer fallback。
- [ ] anthropic vision payload 长什么样？`{type:"image", source:{type:"base64", media_type, data}}`，文本块在最后。
- [ ] anthropic 没有 json_mode 怎么办？system prompt 末尾追加 JSON 强制指令。
- [ ] LLMClient 公开 API 改了吗？没改，签名一致，stages 里不用改。
- [ ] 测试目标多少？132+ passed（v0.2.5.1 是 124，加 8 个新测试）。
- [ ] 用户的 key 怎么处理？临时 env var，不写文件，建议用户轮换。
- [ ] 跑通真产出的视频是哪个？BVxxxxxxxxxx（ACME Phone Max 发布会），output_dir = `acme-launch-2026`，stage 1-2 已缓存。

如果有一项答不上来，回去再读对应章节。

---

**祝顺利。**
