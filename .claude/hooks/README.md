# Hooks (project)

Verified against [Claude Code hooks](https://code.claude.com/docs/en/hooks) (command hooks receive JSON on stdin; use exit 0 and empty stdout unless you intend JSON output).

- `SessionStart`: matcher `*` fires on startup, resume, clear, compact. Keep scripts fast. This is **not** the same as the user running `/compact` in chat (that triggers compaction; `PreCompact` runs before it).
- `PostToolUse`: matcher `Write|Edit` here so the stub does not run on every tool.
- `PreCompact`: matchers `manual` and `auto`; exit 2 or JSON `decision: block` would block compaction. Stubs exit 0 only.

Hook commands use `"$CLAUDE_PROJECT_DIR"/.claude/hooks/...` per official docs.
