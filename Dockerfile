# Dockerfile - Entrypoint Override Revision
FROM honeygain/honeygain:latest

# Elevate privileges to inject our dependencies
USER root

# Dynamically detect the underlying OS package manager and install Python [VERIFIED]
RUN command -v apk >/dev/null && apk add --no-cache python3 || \
    (apt-get update && apt-get install -y python3)

WORKDIR /app
COPY app.py /app/app.py

EXPOSE 10000

# CRITICAL FIX: Nullify the manufacturer's hardcoded entrypoint.
# This ensures Docker boots our Python daemon instead of launching the binary directly.
ENTRYPOINT ["python3", "app.py"]
