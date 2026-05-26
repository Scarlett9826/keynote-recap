# v0.3.1 — Image Quality Hard Gates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把"筛图三原则"从 prompt-only 软约束升级为代码合约，让 stage 3 实际产出 ≥ 35 张 / live ≥ 50% / 每章节 ≥ 1 张 / caption 准确率 ≥ 70%——让"质量稳定"从"运气"变成"代码兜底"。

**Architecture:**
- 三类硬 gate（HARD_FLOOR / SOFT_TARGET / RETRY_DRIVER）按"信号清晰度"分层挂在 stage 3 出口和 stage 5.5 verify
- retry 编排修 v0.2.5 残留 bug（C1-C4），retry 时把"上次失败原因"拼进 prompt
- caption 字段从单一 `caption` 拆成 `alt_short` / `description_long`，治本 D2 alt 过长 + D1 报告非简报体
- 所有阈值从代码里挪到 `methodology.py` 单一来源

**Tech Stack:** Python 3.10+, pydantic v2, pytest, ruff, anthropic SDK ≥ 0.40, openai SDK

---

## 范围与防漏清单

本计划必须修复以下全部 19 个问题（编号与会话取证一致）：

- **A 组（图量图质硬底线）**：A1 实际 27 < 30 不 abort、A2 prompt vs 代码不一致、A3 live 37% retry 不收敛、A4 info_density < 0.7 被选、A5 6 章节 0 图、A6 主线子节 < 1 张
- **B 组（caption 错配防线）**：B1 三张 caption 完全错、B2 caption verify wrong 不进 retry、B3 5.5.4 子节级误报
- **C 组（retry 编排 bug）**：C1 retry 后 image_mix 仍 fail、C2 quality_passed 与 gate 状态不一致、C3 retry 不带失败原因、C4 retry 后不 re-collect
- **D 组（报告格式漂移）**：D1 词典释义体首句、D2 alt 过长、D3 表格少散文多
- **E 组（常量分散）**：E1 30 vs 35 不一致、E2 LIVE_RATIO 散落、E3 缺 PER_SECTION/PER_MAINLINE

每个 task 文末都会标注它修复的问题编号，最后一个 task 是"防漏 audit checklist"。

---

## 阈值最终定义（写入 `methodology.py`）

```python
EXTRACT_FINAL_COUNT_MIN: int = 35     # E1 (was 30) — 与 prompts/03 一致
EXTRACT_FINAL_COUNT_MAX: int = 50
EXTRACT_LIVE_RATIO_MIN: float = 0.50  # E2 — abort 兜底（prompt 仍写 0.70 软目标）
EXTRACT_INFO_DENSITY_MIN: float = 0.70  # 已存在；新增代码 hard filter
EXTRACT_PER_SECTION_MIN: int = 1      # E3 — A8 硬约束
EXTRACT_PER_MAINLINE_MIN: int = 4     # E3 — 方法论"主线 4-6 张"
EXTRACT_CAPTION_VERIFY_WRONG_MAX: int = 1  # B2 — sample 10 wrong ≥ 2 触发 retry
```

**为何 live 0.50 而不是 0.70**：0.70 是 prompt 软目标，0.50 是 abort 兜底——两层结构。如果 abort 阈值也设 0.70，retry 失败时全 fail，banner 永远红色。0.50 = "至少现场图占多数"，是底线信号。

---

## Task 1: 阈值常量集中迁移（E1/E2/E3）

**Files:**
- Modify: `src/keynote_recap/methodology.py:62-68`
- Test: `tests/test_smoke.py` 新增 `test_v031_methodology_constants`

**Step 1: 写失败测试**

在 `tests/test_smoke.py` 末尾添加：

```python
def test_v031_methodology_constants():
    """v0.3.1: image quality hard floor constants exist with correct values."""
    from keynote_recap import methodology as M
    assert M.EXTRACT_FINAL_COUNT_MIN == 35  # E1: was 30
    assert M.EXTRACT_LIVE_RATIO_MIN == 0.50  # E2: new
    assert M.EXTRACT_PER_SECTION_MIN == 1  # E3: A8 硬约束
    assert M.EXTRACT_PER_MAINLINE_MIN == 4  # E3: 主线 4-6 张
    assert M.EXTRACT_CAPTION_VERIFY_WRONG_MAX == 1  # B2
    assert M.EXTRACT_INFO_DENSITY_MIN == 0.70
```

**Step 2: 跑测试确认失败**

```
.venv/bin/python -m pytest tests/test_smoke.py::test_v031_methodology_constants -v
```

预期：`AttributeError: module 'keynote_recap.methodology' has no attribute 'EXTRACT_LIVE_RATIO_MIN'`

**Step 3: 改 methodology.py**

`src/keynote_recap/methodology.py:62-68` 替换为：

```python
# Stage 3 internal target band. v0.3.1: MIN raised 30→35 to align with
# prompts/03-extract-vision-filter.md. Below 35 the report is too sparse
# for a 60-90min keynote (verified empirically against IO/Xiaomi keynotes).
EXTRACT_FINAL_COUNT_MIN: int = 35
EXTRACT_FINAL_COUNT_MAX: int = 50

# Three-principle thresholds. info_density / relevance below 0.7 produces
# pretty-but-empty frames or off-topic frames.
EXTRACT_INFO_DENSITY_MIN: float = 0.70
EXTRACT_RELEVANCE_MIN: float = 0.70

# v0.3.1: live-ratio abort floor. Prompt still asks for 0.70 (soft target),
# this is the abort floor. < 0.50 means the report is mostly marketing
# renders, not a real keynote recap.
EXTRACT_LIVE_RATIO_MIN: float = 0.50

# v0.3.1: A8 硬约束 — 每板块至少 1 张。methodology/filter-three-principles.md
# 写过"绝不接受这个章节没合适的图"，但 v0.3.0 之前没有代码兜底。
EXTRACT_PER_SECTION_MIN: int = 1

# v0.3.1: 主线章节图量下限。方法论文档"主线 4-6 张"。主线判定 = 章节出现
# 在前 1/3 且 transcript 提及次数最高 2 个 section name。
EXTRACT_PER_MAINLINE_MIN: int = 4

# v0.3.1: caption verify sample 10 张里 wrong 超过此数 → 触发 stage 3 retry。
# 1 张容错（vision LLM 偶发幻觉），≥ 2 张说明系统性看错图。
EXTRACT_CAPTION_VERIFY_WRONG_MAX: int = 1
```

**Step 4: 跑测试确认通过**

```
.venv/bin/python -m pytest tests/test_smoke.py::test_v031_methodology_constants -v
.venv/bin/python -m pytest tests/ -q
```

预期：新测试 PASS；既有 132 tests 全 PASS（这一步不应破坏任何现有测试）。

**Step 5: commit**

```
git add src/keynote_recap/methodology.py tests/test_smoke.py
git commit -m "feat(p12): v0.3.1 — methodology constants for image quality hard gates

E1/E2/E3 from v0.3.0 audit:
- EXTRACT_FINAL_COUNT_MIN 30→35 (align with prompts/03)
- new EXTRACT_LIVE_RATIO_MIN=0.50 (abort floor; prompt 0.70 stays as soft target)
- new EXTRACT_PER_SECTION_MIN=1 (A8 hard constraint)
- new EXTRACT_PER_MAINLINE_MIN=4 (mainline 4-6 frames)
- new EXTRACT_CAPTION_VERIFY_WRONG_MAX=1 (sample 10 wrong >= 2 triggers retry)
"
```

**修复**：E1, E2, E3。

---

## Task 2: stage 3 出口 hard gate — count + density + live（A1/A3/A4）

**Files:**
- Modify: `src/keynote_recap/stages/extract.py:155-203`
- Test: `tests/test_smoke.py`

**Step 1: 写失败测试**

```python
def test_v031_extract_drops_low_density():
    """v0.3.1 A4: stage 3 must drop frames with info_density < 0.70."""
    from keynote_recap.stages.extract import _enforce_density_floor
    from keynote_recap.state import SelectedFrame
    frames = [
        SelectedFrame(filename="a.jpg", timestamp="00:00:01", category="data",
                      is_live=True, caption="x", recommended_section="一",
                      info_density=0.85, relevance_to_section=0.9, source="frame_extract"),
        SelectedFrame(filename="b.jpg", timestamp="00:00:02", category="data",
                      is_live=True, caption="y", recommended_section="一",
                      info_density=0.55, relevance_to_section=0.9, source="frame_extract"),
    ]
    kept, dropped = _enforce_density_floor(frames, threshold=0.70)
    assert len(kept) == 1 and kept[0].filename == "a.jpg"
    assert len(dropped) == 1 and dropped[0].filename == "b.jpg"


def test_v031_extract_aborts_below_count_floor():
    """v0.3.1 A1: stage 3 must raise ExtractFloorError when selected < MIN
    after density filter and rescue, signaling that retry must be triggered."""
    from keynote_recap.stages.extract import ExtractFloorError, _check_extract_floors
    from keynote_recap.state import SelectedFrame
    too_few = [
        SelectedFrame(filename=f"f{i}.jpg", timestamp="00:00:01", category="data",
                      is_live=True, caption="x", recommended_section="一",
                      info_density=0.85, relevance_to_section=0.9, source="frame_extract")
        for i in range(20)
    ]
    try:
        _check_extract_floors(too_few, count_min=35, live_ratio_min=0.50)
    except ExtractFloorError as e:
        assert "20 < 35" in str(e)
    else:
        raise AssertionError("expected ExtractFloorError")


def test_v031_extract_aborts_below_live_ratio():
    """v0.3.1 A3: live ratio < 0.50 raises ExtractFloorError."""
    from keynote_recap.stages.extract import ExtractFloorError, _check_extract_floors
    from keynote_recap.state import SelectedFrame
    frames = []
    # 35 张但只 10 张 live → 28% < 50%
    for i in range(35):
        frames.append(SelectedFrame(
            filename=f"f{i}.jpg", timestamp="00:00:01", category="data",
            is_live=(i < 10), caption="（插播官方渲染）x" if i >= 10 else "x",
            recommended_section="一", info_density=0.85,
            relevance_to_section=0.9, source="frame_extract",
        ))
    try:
        _check_extract_floors(frames, count_min=35, live_ratio_min=0.50)
    except ExtractFloorError as e:
        assert "live" in str(e).lower()
    else:
        raise AssertionError("expected ExtractFloorError on low live ratio")
```

**Step 2: 跑测试确认失败**

```
.venv/bin/python -m pytest tests/test_smoke.py -k v031_extract -v
```

预期：3 个测试都 ImportError（函数未定义）。

**Step 3: 改 extract.py**

在 `src/keynote_recap/stages/extract.py` 顶部 import 后加：

```python
class ExtractFloorError(RuntimeError):
    """Stage 3 produced fewer/worse frames than methodology hard floors require.

    Raising this is how stage 3 signals 'retry me with a strengthened prompt'.
    The pipeline catches it in retry orchestration (v0.2.5 already had the
    skeleton; v0.3.1 wires this exception type into it).
    """
```

在文件末尾追加两个纯函数：

```python
def _enforce_density_floor(
    frames: list,  # list[SelectedFrame]
    threshold: float = M.EXTRACT_INFO_DENSITY_MIN,
) -> tuple[list, list]:
    """Drop frames whose info_density < threshold. Returns (kept, dropped)."""
    kept = [f for f in frames if (f.info_density or 0.0) >= threshold]
    dropped = [f for f in frames if (f.info_density or 0.0) < threshold]
    return kept, dropped


def _check_extract_floors(
    selected: list,  # list[SelectedFrame]
    count_min: int = M.EXTRACT_FINAL_COUNT_MIN,
    live_ratio_min: float = M.EXTRACT_LIVE_RATIO_MIN,
) -> None:
    """Raise ExtractFloorError if hard floors fail.

    Floors checked here (cheap / deterministic):
    - total count >= count_min
    - live ratio >= live_ratio_min

    Per-section / per-mainline checks live in verify (need report.md).
    """
    n = len(selected)
    if n < count_min:
        raise ExtractFloorError(
            f"selected_frames count {n} < {count_min} (EXTRACT_FINAL_COUNT_MIN)"
        )
    n_live = sum(1 for f in selected if f.is_live)
    ratio = n_live / n if n else 0.0
    if ratio < live_ratio_min:
        raise ExtractFloorError(
            f"live ratio {ratio:.0%} < {live_ratio_min:.0%} "
            f"({n_live}/{n} live frames; too many marketing renders)"
        )
```

然后修改 `extract.py:155-203` 区域（最终 cap + dedupe 之后），把现有 `if len(selected) < M.EXTRACT_FINAL_COUNT_MIN: ... promote top N` 这段**整段替换为**：

```python
    # v0.3.1 A4: drop low-density frames before count/ratio checks
    selected, dropped_lowd = _enforce_density_floor(selected)
    if dropped_lowd:
        console.print(
            f"[yellow]  density filter: dropped {len(dropped_lowd)} frames "
            f"(info_density < {M.EXTRACT_INFO_DENSITY_MIN})[/]"
        )

    # Cap to MAX
    if len(selected) > M.EXTRACT_FINAL_COUNT_MAX:
        selected.sort(key=lambda f: (f.info_density or 0.0, f.relevance_to_section or 0.0), reverse=True)
        selected = selected[: M.EXTRACT_FINAL_COUNT_MAX]

    # v0.3.1 A1/A3: hard floors. Raises ExtractFloorError → caught by pipeline
    # retry orchestration. Do NOT promote_top_n to silently fill the gap;
    # that hides the methodology drift.
    _check_extract_floors(selected)
```

**Step 4: 跑测试**

```
.venv/bin/python -m pytest tests/test_smoke.py -k v031_extract -v
.venv/bin/python -m pytest tests/ -q
```

预期：3 个新测试 PASS；既有测试若有依赖"selected < 30 仍能 promote"的需要修。

**Step 5: 修受影响的既有测试**

如果 `pytest tests/ -q` 有 fail，逐个看，可能场景：
- 某个 fixture 用 20 张 frames 测 stage 3 → 改成 35 张或 mock `_check_extract_floors`
- 不要改测试断言来"配合"新行为；要么补 fixture 数量，要么改成测 ExtractFloorError 路径

**Step 6: commit**

```
git add src/keynote_recap/stages/extract.py tests/test_smoke.py
git commit -m "feat(p12): v0.3.1 stage 3 hard floors (A1/A3/A4)

- _enforce_density_floor: drop frames with info_density < 0.70 (A4)
- _check_extract_floors: raise ExtractFloorError if count<35 or live<50% (A1/A3)
- ExtractFloorError exception type for pipeline retry orchestration
- Remove silent 'promote top N' behavior that hid methodology drift
"
```

**修复**：A1, A3, A4。

---

## Task 3: stage 3 → verify 加 per-section / per-mainline gate（A5/A6）

**Files:**
- Modify: `src/keynote_recap/stages/verify.py` (add `check_per_section_floor`)
- Modify: `src/keynote_recap/state.py` 加字段 `per_section_floor_passed: bool = True`
- Modify: `src/keynote_recap/pipeline.py:198-215` `_collect_extract_failures` 加 per-section
- Test: `tests/test_smoke.py`

**Step 1: 写失败测试**

```python
def test_v031_per_section_floor_pass():
    """v0.3.1 A5: 每个 ## 章节 ≥ 1 张图 → pass."""
    from keynote_recap.stages.verify import check_per_section_floor
    md = """## 一、A
![](frames/a.jpg)
## 二、B
![](frames/b.jpg)
"""
    r = check_per_section_floor(md, per_section_min=1, mainline_titles=set(), per_mainline_min=4)
    assert r["all_pass"] is True
    assert r["sections_below_floor"] == []


def test_v031_per_section_floor_fails_empty():
    """v0.3.1 A5: 章节 0 张图 → fail."""
    from keynote_recap.stages.verify import check_per_section_floor
    md = """## 一、A
![](frames/a.jpg)
## 二、B
some text but no image
## 三、C
![](frames/c.jpg)
"""
    r = check_per_section_floor(md, per_section_min=1, mainline_titles=set(), per_mainline_min=4)
    assert r["all_pass"] is False
    assert any("二" in s for s in r["sections_below_floor"])


def test_v031_per_mainline_floor_fails():
    """v0.3.1 A6: 主线章节 < 4 张 → fail."""
    from keynote_recap.stages.verify import check_per_section_floor
    md = """## 一、主线
![](frames/a.jpg)
![](frames/b.jpg)
## 二、其他
![](frames/c.jpg)
"""
    r = check_per_section_floor(md, per_section_min=1, mainline_titles={"一、主线"}, per_mainline_min=4)
    assert r["all_pass"] is False
    assert any("主线" in s for s in r["mainline_below_floor"])
```

**Step 2: 跑测试确认失败**

```
.venv/bin/python -m pytest tests/test_smoke.py -k v031_per -v
```

**Step 3: 实现 `check_per_section_floor`**

在 `src/keynote_recap/stages/verify.py` 5.5.1 附近（既有 `check_coverage` 之后）新增：

```python
import re

def check_per_section_floor(
    report_md: str,
    per_section_min: int = 1,
    mainline_titles: set[str] | None = None,
    per_mainline_min: int = 4,
) -> dict:
    """v0.3.1 A5/A6 — per-section image floor + per-mainline image floor.

    A5: every ## section needs >= per_section_min images (default 1, A8 硬约束).
    A6: mainline sections (caller passes the set) need >= per_mainline_min.

    Returns dict with:
      sections_below_floor: list[str]  # 不含主线，纯次要章节缺图
      mainline_below_floor: list[str]  # 主线章节图量 < 4
      all_pass: bool
    """
    mainline_titles = mainline_titles or set()
    sections_below: list[str] = []
    mainline_below: list[str] = []

    # split by ^## (level-2)
    chunks = re.split(r"(?m)^## ", report_md)
    for chunk in chunks[1:]:
        first_line = chunk.splitlines()[0].strip() if chunk.strip() else ""
        if not first_line:
            continue
        # count images in this section (until next ## or EOF)
        body = chunk[len(first_line):]
        n_images = len(re.findall(r"^!\[", body, flags=re.M))
        title_norm = first_line.lstrip("一二三四五六七八九十").lstrip("、 ").strip()

        is_mainline = any(
            (m.lstrip("一二三四五六七八九十").lstrip("、 ").strip() == title_norm)
            or (m == first_line)
            for m in mainline_titles
        )
        if is_mainline:
            if n_images < per_mainline_min:
                mainline_below.append(f"{first_line} (n={n_images}/{per_mainline_min})")
        else:
            if n_images < per_section_min:
                sections_below.append(f"{first_line} (n={n_images}/{per_section_min})")

    return {
        "sections_below_floor": sections_below,
        "mainline_below_floor": mainline_below,
        "all_pass": not sections_below and not mainline_below,
    }
```

**Step 4: 加 state 字段**

在 `src/keynote_recap/state.py:130` 附近加：

```python
    per_section_floor_passed: bool = True  # v0.3.1 (A5/A6): per-section/per-mainline image floor
```

**Step 5: wire 进 verify run**

在 `verify.py` 主 `run` 函数 5.5.1 之后插入：

```python
    # v0.3.1 — 5.5.1b per-section / per-mainline floor (HARD GATE → stage 3 retry)
    mainline_titles = _detect_mainline_titles(state)  # see helper below
    psec = check_per_section_floor(
        report_md,
        per_section_min=M.EXTRACT_PER_SECTION_MIN,
        mainline_titles=mainline_titles,
        per_mainline_min=M.EXTRACT_PER_MAINLINE_MIN,
    )
    state.per_section_floor_passed = psec["all_pass"]
    if psec["all_pass"]:
        console.print("  [5.5.1b] per-section floor: ✓ all sections meet floor")
    else:
        console.print(
            f"  [5.5.1b] per-section floor: [red]✗ "
            f"{len(psec['sections_below_floor'])} below 1 / "
            f"{len(psec['mainline_below_floor'])} mainline below {M.EXTRACT_PER_MAINLINE_MIN}[/]"
        )
        for s in psec["sections_below_floor"][:5]:
            console.print(f"          - {s}")
        for s in psec["mainline_below_floor"][:5]:
            console.print(f"          - mainline: {s}")
```

并在文件靠下加 helper：

```python
def _detect_mainline_titles(state) -> set[str]:
    """主线 = transcript 提及次数 top-2 的 ## 章节。"""
    if not state.video.transcript or not state.report_md_path:
        return set()
    try:
        report_md = Path(state.report_md_path).read_text()
    except OSError:
        return set()
    titles = re.findall(r"(?m)^## (.+)$", report_md)
    transcript = state.video.transcript
    scores = []
    for t in titles:
        # crude: count first 4-char keyword occurrences
        kw = re.sub(r"^[一二三四五六七八九十]+、", "", t).split("：")[0].split(" ")[0][:6]
        if len(kw) >= 2:
            scores.append((t, transcript.count(kw)))
    scores.sort(key=lambda x: x[1], reverse=True)
    return {t for t, _ in scores[:2]}
```

**Step 6: wire 进 retry**

`pipeline.py:198-215` `_collect_extract_failures` 改为：

```python
def _collect_extract_failures(state: State) -> list[str]:
    issues: list[str] = []
    if not state.image_mix_passed:
        issues.append(
            "5.5.6 image mix: total frames < 35 or live ratio < 50% "
            "(too many marketing renders / inserts vs. live keynote frames)"
        )
    if not state.topic_coverage_passed:
        issues.append(
            "5.5.7 topic coverage: a high-frequency topic in the transcript "
            "has zero associated frames (vision LLM was too aggressive)"
        )
    if not state.per_section_floor_passed:  # v0.3.1 A5/A6
        issues.append(
            "5.5.1b per-section floor: a chapter has 0 images, OR a mainline "
            "chapter has < 4 images (frame_scorer 选帧分布不均，需重跑 stage 3)"
        )
    return issues
```

**Step 7: 跑测试**

```
.venv/bin/python -m pytest tests/test_smoke.py -k v031_per -v
.venv/bin/python -m pytest tests/ -q
```

**Step 8: commit**

```
git add src/keynote_recap/stages/verify.py src/keynote_recap/state.py src/keynote_recap/pipeline.py tests/test_smoke.py
git commit -m "feat(p12): v0.3.1 per-section + per-mainline image floor (A5/A6)

- check_per_section_floor: A8 硬约束代码兑现 (every ## section >= 1 image)
- mainline detection: top-2 most-mentioned chapters need >= 4 images
- wire into _collect_extract_failures → triggers stage 3 retry
- new state.per_section_floor_passed flag
"
```

**修复**：A5, A6。

---

## Task 4: caption verify wrong → 触发 retry（B1/B2）

**Files:**
- Modify: `src/keynote_recap/state.py` 加 `caption_verify_wrong_count: int = 0`
- Modify: `src/keynote_recap/stages/verify.py` 主 `run`：caption verify 后落 state
- Modify: `src/keynote_recap/pipeline.py` `_collect_extract_failures` 加 caption check
- Test: `tests/test_smoke.py`

**Step 1: 写失败测试**

```python
def test_v031_caption_wrong_triggers_extract_retry():
    """v0.3.1 B2: caption verify wrong >= 2 → 进 extract_failures."""
    from keynote_recap.pipeline import _collect_extract_failures
    from keynote_recap.state import State, VideoMeta
    s = State(video=VideoMeta(url="x", title="t", duration_seconds=60))
    s.image_mix_passed = True
    s.topic_coverage_passed = True
    s.per_section_floor_passed = True
    s.caption_verify_wrong_count = 2  # >= EXTRACT_CAPTION_VERIFY_WRONG_MAX (1)
    fails = _collect_extract_failures(s)
    assert any("caption" in f.lower() for f in fails)


def test_v031_caption_wrong_below_threshold_no_retry():
    from keynote_recap.pipeline import _collect_extract_failures
    from keynote_recap.state import State, VideoMeta
    s = State(video=VideoMeta(url="x", title="t", duration_seconds=60))
    s.image_mix_passed = True
    s.topic_coverage_passed = True
    s.per_section_floor_passed = True
    s.caption_verify_wrong_count = 1  # at threshold; tolerated
    fails = _collect_extract_failures(s)
    assert not any("caption" in f.lower() for f in fails)
```

**Step 2: 跑测试确认失败**

```
.venv/bin/python -m pytest tests/test_smoke.py -k v031_caption -v
```

**Step 3: 加 state 字段**

`src/keynote_recap/state.py` 加：

```python
    caption_verify_wrong_count: int = 0  # v0.3.1 B2: 5.5.2 caption verify wrong count
```

**Step 4: 改 verify 主 run 落 state**

verify.py 主 `run` 函数里 caption verify 那段（约 769-775 行）改为：

```python
    cap = verify_captions(state, cfg, client)
    n_verifications = len(cap.get("verifications", []))
    n_wrong = sum(1 for v in cap.get("verifications", []) if v.get("match_status") == "wrong")
    state.caption_verify_wrong_count = n_wrong  # v0.3.1 B2
    console.print(f"  [5.5.2] caption verify (sample {n_verifications}): "
                  f"{'✓' if n_wrong == 0 else f'[red]✗ {n_wrong} wrong[/]'}")
```

**Step 5: 改 `_collect_extract_failures`**

加上：

```python
    if state.caption_verify_wrong_count > M.EXTRACT_CAPTION_VERIFY_WRONG_MAX:
        issues.append(
            f"5.5.2 caption verify: {state.caption_verify_wrong_count} wrong "
            f"captions (> tolerance {M.EXTRACT_CAPTION_VERIFY_WRONG_MAX}); "
            f"vision LLM 看错图，stage 3 retry 时强化 caption 忠实性 prompt"
        )
```

记得 `import keynote_recap.methodology as M` 已在 pipeline.py 顶部。

**Step 6: 跑测试 + commit**

```
.venv/bin/python -m pytest tests/test_smoke.py -k v031 -v
.venv/bin/python -m pytest tests/ -q
git add -A && git commit -m "feat(p12): v0.3.1 caption verify wrong triggers extract retry (B1/B2)

- state.caption_verify_wrong_count: tracks 5.5.2 wrong captions
- _collect_extract_failures: > 1 wrong → retry stage 3
- methodology constant EXTRACT_CAPTION_VERIFY_WRONG_MAX = 1
"
```

**修复**：B1, B2。

---

## Task 5: 5.5.4 image-section fit 改子节级粒度（B3）

**Files:**
- Modify: `src/keynote_recap/stages/verify.py:308-371` `check_image_section_fit`
- Test: `tests/test_smoke.py`

**Step 1: 写失败测试**

```python
def test_v031_section_fit_subsection_grain():
    """v0.3.1 B3: image-section fit 应到 ### 子节级而非 ## 章节级。
    
    场景：## 八、ACME 空调 / ### 8.3 制造底气 — 家电智能工厂
    frame caption: 'ACME 家电智能工厂介绍片段...'
    应该 PASS（caption 与 8.3 子节匹配），而不是 fail（caption 与 §8 标题不匹配）。
    """
    from keynote_recap.stages.verify import check_image_section_fit
    md = """## 八、ACME 空调强劲风系列：风量对标柜机的挂机

### 8.1 1.5 匹挂机 — 风量 1000 m³/h

![空调实物](frames/ac.jpg)

### 8.3 制造底气 — 家电智能工厂，磁悬浮装配线 + AI 100% 全检

2024 年 10 月，ACME 家电智能工厂正式投产。

![（插播官方渲染）ACME 家电智能工厂介绍片段：磁悬浮主板装配线](frames/factory.jpg)
"""
    r = check_image_section_fit(md)
    # factory.jpg 在 8.3 智能工厂子节里，caption 谈智能工厂 → 应 PASS
    mismatches = [m for m in r.get("mismatches", []) if "factory" in m.get("filename", "")]
    assert len(mismatches) == 0, f"factory.jpg should match 8.3 subsection: {mismatches}"
```

**Step 2: 跑测试确认失败**

```
.venv/bin/python -m pytest tests/test_smoke.py -k v031_section_fit -v
```

**Step 3: 改 `check_image_section_fit`**

读现有实现（verify.py:308-371），把 "对每张图找最近的 ## 标题" 改为 "找最近的 ### 子节标题，子节没有时再 fallback 到 ##"。

伪码：

```python
# 原来：找最近的 ## 标题做 keyword overlap
# 改为：
#   1. 优先找最近的 ### 子节标题
#   2. 用 子节标题 的 token 做 keyword overlap
#   3. 子节标题 token 命中 ≥ 1 → PASS（不再 fallback 到 ##）
#   4. 子节标题 0 命中、## 章节标题 0 命中 → 才算 mismatch
```

具体实现需要看现有代码细节再写——这一步**不在 plan 里硬编代码**（待 sub-agent 读完 verify.py:308-371 再决定）。

**Step 4: 跑测试 + commit**

```
.venv/bin/python -m pytest tests/ -q
git add -A && git commit -m "fix(p12): v0.3.1 image-section fit 改子节级粒度 (B3)

5.5.4 检查从 ## 章节级降到 ### 子节级，消除 §8 ACME 空调 / §8.3 智能工厂
此类合理跨子主题的误报。
"
```

**修复**：B3。

---

## Task 6: retry 编排修 bug（C1/C2/C3/C4）

**Files:**
- Modify: `src/keynote_recap/pipeline.py:280-373`
- Modify: `src/keynote_recap/stages/extract.py` `run` 接受 `retry_context: list[str] | None = None` 参数
- Test: `tests/test_smoke.py`

**Step 1: 写失败测试**

```python
def test_v031_retry_passes_failure_reasons_to_stage3():
    """v0.3.1 C3: retry 时把 last_extract_failures 拼进 prompt context。"""
    from keynote_recap.stages.extract import _build_retry_directive
    fails = [
        "5.5.6 image mix: live ratio 37% < 50%",
        "5.5.1b per-section floor: 6 sections below 1 image",
    ]
    directive = _build_retry_directive(fails)
    assert "上次筛图失败" in directive or "previous attempt failed" in directive.lower()
    assert "37%" in directive
    assert "6 sections" in directive or "6 个章节" in directive


def test_v031_quality_passed_consistent_with_gates():
    """v0.3.1 C2: quality_passed must reflect the actual gate state.
    
    Setup: simulate retry done (extract_retry_count=1) but image_mix still False.
    Expectation: _collect_quality_failures 仍能正确 collect。
    """
    from keynote_recap.pipeline import _collect_quality_failures
    from keynote_recap.state import State, VideoMeta
    s = State(video=VideoMeta(url="x", title="t", duration_seconds=60))
    s.extract_retry_count = 1
    s.image_mix_passed = False
    s.coverage_check_passed = False
    s.per_section_floor_passed = False
    fails = _collect_quality_failures(s)
    # 5 个 gate 全 fail，应该收集到 ≥ 3 issues
    assert len(fails) >= 3
```

**Step 2: 跑测试确认失败**

```
.venv/bin/python -m pytest tests/test_smoke.py -k v031_retry -v
```

**Step 3: 加 retry directive helper**

`src/keynote_recap/stages/extract.py` 末尾加：

```python
def _build_retry_directive(failures: list[str]) -> str:
    """v0.3.1 C3 — turn last failures into a Chinese prompt prefix.

    Example output:
      [retry context]
      上次筛图失败原因：
      1. live ratio 37% < 50% (太多营销渲染)
      2. 6 个章节缺图

      本次筛图必须修复以上问题：
      - 优先选 is_live=true 的图（现场画面）
      - 确保每个发布主题至少有 1 张相关帧
    """
    if not failures:
        return ""
    lines = ["", "## 上次筛图失败原因（必须本次修复）", ""]
    for i, f in enumerate(failures, 1):
        lines.append(f"{i}. {f}")
    lines += [
        "",
        "## 本次必须做的改进",
        "- 优先选 is_live=true 的图（现场实拍 / PPT 投影 / 真机 demo），",
        "  减少 is_live=false 插播渲染的占比",
        "- 每个发布主题（产品/协议/技术）至少 1 张相关帧",
        "- caption 必须只描述图中实际可见内容，不要从字幕推测",
        "",
    ]
    return "\n".join(lines)
```

**Step 4: 让 stage 3 run 接受 retry context**

`extract.py` 的 `run` 函数签名加默认参数（pipeline 调用时不传时不影响 v0.2 行为）：

```python
def run(state: State, config: Config, retry_context: list[str] | None = None) -> State:
    ...
    # 在拼 user prompt 时插入 retry directive
    retry_prefix = _build_retry_directive(retry_context or [])
    if retry_prefix:
        user_prompt = retry_prefix + "\n\n" + user_prompt
```

具体插入点 sub-agent 看 extract.py 实际拼 prompt 的位置（约 90-100 行附近）。

**Step 5: pipeline retry 编排传 retry_context**

`pipeline.py:307-333`，把 stage 3 retry 那段改：

```python
            extract_fails = _collect_extract_failures(state)
            if extract_fails and state.extract_retry_count == 0:
                console.print(
                    f"\n[bold yellow]⚠ Frame-selection gate failed:[/] "
                    f"{len(extract_fails)} hard issues — re-running stage 3 (vision filter).\n"
                )
                for issue in extract_fails:
                    console.print(f"   • {issue}")
                state.extract_retry_count = 1
                state.last_completed_stage = 2.0
                state.save()
                try:
                    # v0.3.1 C3 — 把失败原因塞进 stage 3 prompt
                    state = STAGES["extract"][1](state, config, retry_context=extract_fails)
                    if not state.research_notes_path:
                        state = STAGES["research"][1](state, config)
                    state = STAGES["draft"][1](state, config)
                    state = STAGES["verify"][1](state, config)
                except ExtractFloorError as e:
                    console.print(f"[bold red]Stage 3 retry — floor still failing:[/] {e}")
                    state.runtime_warnings.append(f"stage 3 retry failed floor: {e}")
                    state.save()
                    if debug:
                        raise
                    return state
                except Exception as e:
                    console.print(f"[bold red]Stage 3 retry failed:[/] {e}")
                    state.save()
                    if debug:
                        raise
                    return state
```

**Step 6: 修 final assessment（C2/C4）**

`pipeline.py:357-372` 区域，把 final assessment 改为重 collect：

```python
            # v0.3.1 C2/C4 — re-collect after all retries to ensure
            # quality_passed reflects actual gate state.
            still_failing = _collect_quality_failures(state)  # collects extract+draft fresh
            if still_failing:
                state.quality_passed = False
                state.final_quality_warnings = still_failing
                console.print(
                    f"\n[bold yellow]⚠ Quality gate still failing[/]: "
                    f"{len(still_failing)} issues remain — banner will be added to report.\n"
                )
                for issue in still_failing:
                    console.print(f"   • {issue}")
            else:
                state.quality_passed = True
                state.final_quality_warnings = []
                console.print("[green]✓ Quality gate passed[/]\n")
            state.save()
```

需要从 `extract` import `ExtractFloorError`：

```python
from keynote_recap.stages.extract import ExtractFloorError
```

**Step 7: 跑测试 + commit**

```
.venv/bin/python -m pytest tests/ -q
git add -A && git commit -m "fix(p12): v0.3.1 retry orchestration bugs (C1/C2/C3/C4)

- C3: retry passes last failures as prompt context (_build_retry_directive)
- C2/C4: final assessment re-collects gate state, no stale quality_passed
- catch ExtractFloorError separately for clearer abort reason
- stage 3 retry now actually addresses what failed last time
"
```

**修复**：C1, C2, C3, C4。

---

## Task 7: caption 拆 alt_short / description_long（D1/D2）

**Files:**
- Modify: `src/keynote_recap/state.py` `SelectedFrame` 加 `alt_short: str = ""`
- Modify: `prompts/03-extract-vision-filter.md` 输出 schema 加 `alt_short` 字段
- Modify: `src/keynote_recap/stages/extract.py` parse 接受新字段
- Modify: `prompts/05-draft-write-strict.md` 用 `alt_short` 而非完整 caption
- Test: `tests/test_smoke.py`

**Step 1: 写失败测试**

```python
def test_v031_selected_frame_has_alt_short():
    from keynote_recap.state import SelectedFrame
    f = SelectedFrame(
        filename="x.jpg", timestamp="00:00:01", category="data",
        is_live=True, caption="完整长 caption 描述包括是什么讲什么上下文",
        alt_short="YU7 GT 销售数据",
        recommended_section="一", info_density=0.85,
        relevance_to_section=0.9, source="frame_extract",
    )
    assert f.alt_short == "YU7 GT 销售数据"
    # alt_short 必须 ≤ 25 字
    assert len(f.alt_short) <= 25
```

**Step 2: 加 state 字段**

`SelectedFrame` 加：

```python
    alt_short: str = ""  # v0.3.1 D2: ≤ 25 字短 alt，用于 ![alt](frames/x.jpg)
```

**Step 3: 改 prompt schema**

`prompts/03-extract-vision-filter.md` 的 JSON schema 区块加：

```
"alt_short": "<≤ 25 字短 alt 文字（用于 markdown alt-text 位）。例：「YU7 GT 销售数据」「V8s EVO 电机参数」>",
"caption": "<完整 caption（必须中文，禁止英文）：是什么 + 讲什么 + 上下文。如果 is_live=false，caption 必须以「（插播官方渲染）」开头>",
```

并在 prompt 主体加段落：

```
## alt_short vs caption 区别（v0.3.1 新增）

- `alt_short`：≤ 25 字。markdown 渲染时塞进 `![<alt_short>](frame.jpg)` 的 alt 位。**短词组**，例：「YU7 GT 纽北圈速」、「V8s EVO 电机参数」、「8000 mAh 电池数据」
- `caption`：30-150 字。完整三要素（是什么/讲什么/上下文），用于 stage 5.5 caption verify 与下游正文叙述

stage 5 写报告时只用 alt_short，不直接把长 caption 塞 alt 位。
```

**Step 4: 改 strict draft prompt**

`prompts/05-draft-write-strict.md` 关于图片插入的部分改成：

```
## 图片插入规范（v0.3.1）

每张图必须用 `alt_short` 字段做 alt 文字，不要把完整 caption 塞 alt 位：

✅ 正确：
![YU7 GT 销售数据](frames/frame_00259.jpg)

紧接着用一段或一个 bullet 把图的核心信息消化成正文（不是抄 caption）。

❌ 错误（v0.3.0 漂移）：
![ACME GT品牌代言人舒淇宣传片：画面显示「舒淇 ACME 汽车品牌代言人」字幕，舒淇坐在红色沙发上阅读，室内场景，正式确认其ACME 汽车品牌代言人身份。](frames/frame_00902.jpg)
```

**Step 5: stage 5 prompt 加"简报体"硬约束（D1/D3）**

`prompts/05-draft-write-strict.md` 加段落：

```
## 简报体硬约束（v0.3.1，D1/D3 修复）

每个 ### 子节首句必须采用以下三种模式之一，**不得**用词典释义体（"X 是 Y 的缩写"）：

1. `**定位**：<一句话点死核心>` 例：「**定位**：38.99 万起，对标卡宴 Turbo GT」
2. 「<产品/技术名> + <核心数字>」 例：「YU7 GT 搭载 V8s EVO 超级电机，1000 匹综合马力。」
3. 「<时间/事件> + <数据>」 例：「2025 年 1 月，YU7 累计交付 23.2 万辆，夺全车型销量冠军。」

并列信息**优先用表格**：
- 多版本/多型号对比 → 表格（≥ 2 列）
- 时间线/上线节奏 → 表格（时间 | 范围）
- 参数对比（前代 vs 当代 / 自家 vs 竞品）→ 表格

整篇报告 table_count ≥ 8（5.5.5 既有硬约束）；本次额外约束 ：
- 主线章节每个子节 ≥ 1 个表格 OR ≥ 1 个 bullet 列表
```

**Step 6: 测试 + commit**

```
.venv/bin/python -m pytest tests/ -q
git add -A && git commit -m "feat(p12): v0.3.1 alt_short field + 简报体 prompt (D1/D2/D3)

- SelectedFrame.alt_short: ≤25 char alt-text
- prompt 03: schema 加 alt_short, 解释 alt_short vs caption 区别
- prompt 05-strict: 图片插入用 alt_short 不用 caption；首句三种模式禁止
  词典释义体；并列信息硬约束用表格
"
```

**修复**：D1, D2, D3。

---

## Task 8: 端到端真产出验证（防漏）

**Files:** （只读，不改）
- Run: `keynote-recap recap-and-verify` on cached BVxxxxxxxxxx

**Step 1: 用已 cache 的视频跑全流程**

acme-launch-2026 已经 cache 了 video / subtitle / frames_raw 80 张。重新跑 stage 3-6：

```bash
cd /Users/mi/Desktop/截图提取
rm -rf output/acme-launch-2026
cp -r output/acme-launch-2026 output/acme-launch-2026
# 改 state.json 让它从 stage 3 开始
.venv/bin/python -c "
import json, pathlib
p = pathlib.Path('output/acme-launch-2026/state.json')
s = json.loads(p.read_text())
s['last_completed_stage'] = 2.0
s['stages_completed'] = [1.0, 2.0]
s['extract_retry_count'] = 0
s['draft_retry_count'] = 0
s['selected_frames'] = []
p.write_text(json.dumps(s, ensure_ascii=False, indent=2))
"
OPENAI_API_KEY=$KEY .venv/bin/keynote-recap recap-and-verify \
  https://www.bilibili.com/video/BVxxxxxxxxxx/ \
  --output-dir ./output/acme-launch-2026 \
  --start-stage 3 --no-checkpoint
```

**Step 2: 验证防漏 checklist**

A 组（图量图质硬底线）：
- [ ] A1: `selected_frames count >= 35` (`jq '.selected_frames | length' state.json`)
- [ ] A2: `prompts/03` 写 35 与 `EXTRACT_FINAL_COUNT_MIN=35` 一致（grep）
- [ ] A3: `live_ratio >= 0.50` (`jq '[.selected_frames[] | select(.is_live==true)] | length` 计算)
- [ ] A4: `min(info_density) >= 0.70` (`jq '[.selected_frames[].info_density] | min' state.json`)
- [ ] A5: `lint_report.md` 5.5.1 coverage all pass
- [ ] A6: 主线章节图量 >= 4（手数 §1 YU7 GT 子节图量）

B 组（caption 错配防线）：
- [ ] B1: `lint_report.md` 5.5.2 wrong = 0
- [ ] B2: 即使有 wrong，state.caption_verify_wrong_count 落地，retry 触发（看 stdout）
- [ ] B3: 5.5.4 fit 没有把 "工厂图在 §8.3" 误报

C 组（retry 编排）：
- [ ] C1: 如果 retry 跑过，retry 后 image_mix_passed=True
- [ ] C2: `quality_passed` 与 5 个 gate 严格一致（写 1 行 jq 同时检查）
- [ ] C3: stdout 应能看到 "上次筛图失败原因" 字样（如果 retry 触发）
- [ ] C4: `final_quality_warnings` 与 `_collect_quality_failures()` 同步

D 组（报告格式）：
- [ ] D1: `report.md` 中 ### 子节首句不含「是英文 X 的缩写」「直译」「字面义」
- [ ] D2: `![...]()` alt 长度全部 ≤ 25 字（grep + 字数统计）
- [ ] D3: `report.md` table_count >= 8

E 组（常量）：
- [ ] E1/E2/E3: `git grep -nE "FINAL_COUNT_MIN|LIVE_RATIO_MIN|PER_SECTION_MIN" src/` 只在 methodology.py 出现一次定义、其他地方都 import

**Step 3: 把 checklist 结果落到 plan 同目录**

```bash
echo "checklist 验证结果：见 docs/plans/2026-05-26-v031-verification-results.md"
```

实测哪些 ✓ / ✗，写一行原因。

**Step 4: 如果有 ✗，回到对应 task 修补**

不允许 "✗ 但 we ship anyway"。每个 ✗ 必须找到 task N 修补再跑一次。

**Step 5: bump 版本 + CHANGELOG + commit + tag**

```bash
# pyproject.toml + __init__.py: 0.3.0 → 0.3.1
# CHANGELOG.md: v0.3.1 entry，列 A/B/C/D/E 五组各修了什么
git add -A && git commit -m "release(p12): v0.3.1 — image quality hard gates"
git tag v0.3.1
# push 等用户确认（按"远程写操作前 question 确认"约定）
```

---

## 不在本计划范围（v0.3.2+ 候选）

- `SelectedFrame.source` literal 加 `frame_extract_rescue`（v0.3.0 已知 fallback bug，本次不动）
- Anthropic prompt-caching tokens surface
- 模型白名单收紧（M7 internalized defense 加严）
- frame_scorer 改 ML embedding（当前 PIL edge density）

---

## 完成标准（DoD）

- 132 + 新增 ~15 测试全 PASS
- ruff `--select=E,F,W` 无 warning
- `keynote-recap recap-and-verify <BVxxxxxxxxxx>` 在 cache 数据上 quality_passed=True
- A/B/C/D/E 五组 19 个问题 audit checklist 全 ✓
- v0.3.1 tag pushed
