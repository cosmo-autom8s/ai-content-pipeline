# Codex Hardening Plan

Created: 2026-04-06
Status: In Progress
Branch: `codex/content-pipeline-hardening`

## Objective

Turn the content pipeline into a system that is:

- operationally correct
- easier to validate and debug
- less dependent on undocumented Claude-specific behavior
- reproducible from a fresh setup

## Plan of Action

### 1. Stabilize the environment and setup flow

- Add `.env.example`
- Add a `validate_env.py` command that checks:
  - required env vars
  - Notion API access
  - OpenRouter auth
  - Obsidian vault path
- Document the remaining MCP requirement explicitly so TokScript access is not a hidden assumption

### 2. Harden the orchestrator

- Normalize the run order:
  - CSV ingest
  - Spotify conversion
  - transcript extraction
  - classification
  - summary
- Improve `--dry-run`
- Improve `--status`
- Add clearer stage-by-stage success/failure reporting

### 3. Make transcript extraction more robust

- Reduce reliance on prompt-shaped output parsing
- Keep structured backup artifacts for every extraction batch
- Normalize transcript metadata updates consistently
- Improve partial-failure reporting

### 4. Harden classification

- Add clearer startup validation and error messages
- Improve OpenRouter failure handling and retry behavior
- Add optional fallback model support
- Preserve raw failed outputs for inspection
- Extend tests around retry and failure behavior

### 5. Make ideation a real workflow

- Keep prompt-print mode
- Keep human approval in the loop
- Enforce a real machine-usable save path
- Validate incoming idea JSON before writing to Notion
- Add deduplication safeguards for repeated source saves

### 6. Make captions a real workflow

- Use the live Notion schema consistently
- Support partial saves
- Support clean status transitions
- Add tests around field mapping and payload validation

### 7. Align docs and skills with reality

- Update README for the true setup flow
- Audit `/ca-*` skill files for drift
- Remove or label legacy behavior clearly

### 8. Improve coverage where it matters

- Add tests for:
  - orchestrator routing
  - Spotify conversion integration
  - ideation save validation
  - captions save validation
  - Notion field mapping
  - classification fallback/retry behavior

## Immediate Next Steps

1. Add `.env.example`
2. Add `validate_env.py`
3. Update README setup docs
4. Re-run validation locally
