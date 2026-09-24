#!/bin/sh
set -e

# Forward all arguments and execute python orchestrator with unbuffered output
exec python3 -u /app/app.py "$@"
