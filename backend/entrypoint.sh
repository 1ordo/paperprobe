#!/bin/sh
set -e

# Auto-generate AUTH_SECRET if not set
if [ -z "$AUTH_SECRET" ]; then
    export AUTH_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
    echo "[entrypoint] Generated random AUTH_SECRET (set AUTH_SECRET in .env to persist across restarts)"
fi

exec "$@"
