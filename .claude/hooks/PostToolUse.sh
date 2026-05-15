#!/usr/bin/env bash
# PostToolUse hook: JSON on stdin. Registered only for Write|Edit in settings.json.
# Optional: run formatter or git add (review side effects before enabling).
# https://code.claude.com/docs/en/hooks#posttooluse
exec cat >/dev/null
