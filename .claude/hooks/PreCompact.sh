#!/usr/bin/env bash
# PreCompact hook: JSON on stdin. Do NOT exit 2 or emit decision:block unless you intend to block compaction.
# This is the hook lifecycle before compaction, not the same as typing /compact (though trigger may be manual).
# https://code.claude.com/docs/en/hooks#precompact
exec cat >/dev/null
