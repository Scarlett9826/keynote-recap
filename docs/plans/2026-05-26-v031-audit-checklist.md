# v0.3.1 Audit Checklist — 19 Findings from v0.3.0 真产出

This document tracks how each of the 19 findings in
``2026-05-26-v031-image-quality-hard-gates.md`` is verified.

## Scope

- **Code-level guards** are enforced by tests in ``tests/test_smoke.py``
  named ``test_v031_audit_*`` (20 tests, including a sentinel). These
  run on every CI invocation.
- **End-to-end production verification** requires a real video URL,
  configured LLM gateway, and ~5–10 minutes wall-clock. Documented
  below as opt-in; not part of automated CI.

## Code-level audit (20 tests in suite)

| # | Finding | Test | Status |
|---|---------|------|--------|
| A1 | count floor 35 (was 30 advisory) | ``test_v031_audit_A1_count_floor_is_35`` | ✓ |
| A2 | prompt and code agree on 35 | ``test_v031_audit_A2_prompt_and_code_count_consistent`` | ✓ |
| A3 | live ratio hard floor 0.50 | ``test_v031_audit_A3_live_ratio_hard_floor_50pct`` | ✓ |
| A4 | info_density floor 0.70 enforced | ``test_v031_audit_A4_info_density_floor_enforced`` | ✓ |
| A5 | per-section floor check exists | ``test_v031_audit_A5_per_section_floor_check_exists`` | ✓ |
| A6 | per-mainline ≥ 4, per-section ≥ 1 | ``test_v031_audit_A6_per_mainline_floor_constant`` | ✓ |
| B1 | caption_verify_wrong_count persists | ``test_v031_audit_B1_caption_wrong_persists_in_state`` | ✓ |
| B2 | caption-wrong > 1 triggers retry | ``test_v031_audit_B2_caption_wrong_triggers_extract_retry`` | ✓ |
| B3 | 5.5.4 considers ### subsection | ``test_v031_audit_B3_section_fit_uses_subsection`` | ✓ |
| C1 | retry block re-runs verify | ``test_v031_audit_C1_retry_actually_reruns_verify`` | ✓ |
| C2 | quality_passed default False | ``test_v031_audit_C2_quality_passed_default_false`` | ✓ |
| C3 | extract.run accepts retry_context | ``test_v031_audit_C3_extract_run_accepts_retry_context`` | ✓ |
| C4 | pipeline re-collects after retry | ``test_v031_audit_C4_pipeline_recollects_after_retry`` | ✓ |
| D1 | strict prompt briefing-style rule | ``test_v031_audit_D1_strict_prompt_briefing_rule`` | ✓ |
| D2 | alt_short field + prompt schema | ``test_v031_audit_D2_alt_short_field_and_schema`` | ✓ |
| D3 | strict prompt table constraint | ``test_v031_audit_D3_strict_prompt_table_constraint`` | ✓ |
| E1 | 35 lives in methodology.py | ``test_v031_audit_E1_count_constant_consistent`` | ✓ |
| E2 | live-ratio const centralized | ``test_v031_audit_E2_live_ratio_constant_centralized`` | ✓ |
| E3 | per-section consts present | ``test_v031_audit_E3_per_section_constants_present`` | ✓ |
| ☑ | sentinel: ≥ 19 audit tests defined | ``test_v031_audit_full_19_findings_have_guards`` | ✓ |

Run the audit any time:

```bash
.venv/bin/python -m pytest tests/test_smoke.py -k v031_audit -v
```

## End-to-end production verification (opt-in)

Code-level guards prove the gates exist. Whether they actually fire
correctly against a real video can only be observed at runtime. Use
this when validating a release candidate before tagging.

### Prerequisites

- ``~/.config/keynote-recap/config.yaml`` configured with a working LLM
  gateway (``provider: anthropic-native`` or ``openai-compatible``).
- ``KEYNOTE_RECAP_MODEL`` set to a verified multimodal model.
- A keynote video URL (YouTube / Bilibili / mp4).

### Recommended baseline

The your-company 2026-05-20 product launch is the regression video for
v0.3.1 because v0.3.0 produced the 22-image / 5-failed-gate / silent-
quality-pass report that motivated this release. Cached frames and
state at ``output/acme-launch-2026/`` from the v0.3.0 run can be
diffed against a fresh v0.3.1 run.

### Run

```bash
keynote-recap recap-and-verify <url> --output-dir ./output/v031-audit-<slug>
```

### Post-run audit

```bash
# 1. final image count >= 35
jq '.selected_frames | length' output/v031-audit-<slug>/state.json

# 2. live ratio >= 50%
jq '[.selected_frames[] | select(.is_live == true)] | length as $live |
    .selected_frames | length as $total | $live / $total' \
    output/v031-audit-<slug>/state.json

# 3. info_density floor honored (no frame below 0.70)
jq '[.selected_frames[] | select(.info_density < 0.70)] | length' \
    output/v031-audit-<slug>/state.json
# expect: 0 (rescue floor itself is 0.70)

# 4. per-section coverage: every chapter has >= 1 image
# (manual: scan report.md headings vs ![]() refs)

# 5. mainline chapters have >= 4 images each
# (manual: identify top-2 transcript topics, count images in those chapters)

# 6. caption verify: 5.5.2 wrong count <= 1
grep -c "wrong" output/v031-audit-<slug>/lint_report.md

# 7. 5.5.4 image-section fit: review mismatches list
grep -A 20 "5.5.4" output/v031-audit-<slug>/lint_report.md

# 8. quality_passed honest: matches actual gate states
jq '{quality_passed, image_mix_passed, coverage_check_passed,
     bucket_placement_passed, structure_check_passed, lint_hard_failed,
     per_section_floor_passed, caption_verify_wrong_count,
     final_quality_warnings}' output/v031-audit-<slug>/state.json
# expect: quality_passed=true ONLY when all individual gates pass
#         AND final_quality_warnings is empty

# 9. retry transparency: if extract_retry_count=1, [RETRY GUIDANCE]
# should appear in stage 3 logs
grep -i "retry guidance" output/v031-audit-<slug>/*.log 2>/dev/null

# 10. alt_short populated: count frames with non-empty alt_short
jq '[.selected_frames[] | select(.alt_short != "")] | length' \
    output/v031-audit-<slug>/state.json

# 11. report has banner stamp + signed sha (verify command independently)
keynote-recap verify ./output/v031-audit-<slug>/report.html
# expect: OK: ...

# 12. report.md sections: count ## headings
grep -c "^## " output/v031-audit-<slug>/report.md

# 13. table density: count tables in report.md (strict requires >= 5)
grep -cE "^\|.*\|$" output/v031-audit-<slug>/report.md

# 14. briefing-style first sentence: spot-check first sentence of each
# ## chapter; should NOT match 词典释义体 / 仪式开场 / 议程预告 patterns
```

### Sign-off

A v0.3.1 release-candidate is signed off when:

- All 20 ``v031_audit_*`` code-level tests pass (CI-enforced).
- A real-world end-to-end run on the your-company 2026-05-20 baseline (or
  any other keynote ≥ 60 minutes) produces:
  - ``selected_frames`` ≥ 35.
  - live ratio ≥ 0.50.
  - all per-section / per-mainline floors honored.
  - caption-verify wrong count ≤ 1.
  - ``quality_passed=true`` AND ``final_quality_warnings=[]`` AND every
    individual gate flag is True (or, if any failed, ``quality_passed=
    false`` with the specific gate listed in warnings).
  - ``keynote-recap verify`` returns ``OK``.

A run where ``quality_passed`` disagrees with individual gate flags
is the C2 root-cause bug; it must not occur in v0.3.1.
