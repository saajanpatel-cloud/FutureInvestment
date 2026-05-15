#!/usr/bin/env bash
# SessionStart hook: JSON on stdin. stdout may be injected as context; keep empty for no-op.
# Optional: print repo hint to stderr only (shown to user, not model per docs for most events).
# https://code.claude.com/docs/en/hooks#sessionstart
exec cat >/dev/null
