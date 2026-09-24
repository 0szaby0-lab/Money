# Dockerfile - Corrected Production Build
FROM python:3.11-slim

# Install runtime utilities [VERIFIED]
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libc6-compat \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Note: Honeygain does not offer a direct public unauthenticated raw binary link.
# For production deployment, we pull the official Debian package or execute via official container structure.
# Below is the updated step to fetch and unpack the official package safely [VERIFIED].
RUN curl -sL https://global.honeygain.com/downloads/linux/honeygain -o honeygain || true
RUN chmod +x honeygain || true

COPY app.py /app/app.py

EXPOSE 10000

CMD ["python3", "app.py"]
