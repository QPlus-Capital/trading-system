# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_claude_runtime_files.py` | RED: `.claude/skills` and `.claude/agents` absent | GREEN: exact file sets and required frontmatter/body contracts parse |
| AC-02 | `tests/test_quality_hooks.py` decision matrix | RED: `scripts.quality.hooks` cannot import | GREEN: all eight decisions block unsafe and allow safe inputs |
| AC-03 | `test_secret_decision_blocks_synthetic_secret_without_leaking_it` and clean counterpart | RED: secret decision absent | GREEN: fake secret blocks, clean diff passes, neither input is returned |
| AC-04 | settings/module tests plus `just check` | RED: settings and hook module absent | GREEN: documented hook schema imports and all repository gates pass |
| INV-01 | classifier-injection runtime test and source review | RED: hook runtime absent | GREEN: runtime calls imported `classify_paths` with the loaded model |
| INV-02 | readiness/review delegation tests | RED: boundary hook absent | GREEN: `pr_ready.main` and `validate_task_dir` determine their respective decisions |
| INV-03 | unit tests monkeypatch all subprocess/readiness boundaries | RED: no guarded execution path | GREEN: no live module is imported or executed by hook tests |
| INV-04 | denial rendering and synthetic-secret tests | RED: no output contract | GREEN: output contains only fixed reason text and documented JSON keys |
