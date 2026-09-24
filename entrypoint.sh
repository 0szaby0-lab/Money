#!/bin/sh
# entrypoint.sh

# Run initial proxy harvesting and testing before booting the main daemon
python3 /app/app.py --init-proxies

exec python3 /app/app.py
