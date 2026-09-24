# Multi-App Passive Income Node for Render.com Free Tier
# Runs EarnFM + Traffmonetizer + Repocket + Honeygain simultaneously
# EarnFM/TM/Repocket: native datacenter support (guaranteed)
# Honeygain: auto-harvested clean residential proxies (best effort)

# Stage 1: Extract EarnFM binary
FROM earnfm/earnfm-client:latest AS earnfm-source

# Stage 2: Extract Traffmonetizer binary
FROM traffmonetizer/cli_v2 AS tm-source

# Stage 3: Extract Repocket binary
FROM repocket/repocket AS rp-source

# Stage 4: Extract Honeygain binary
FROM honeygain/honeygain:latest AS hg-source

# Stage 5: Final lightweight container
FROM alpine:latest

RUN apk add --no-cache python3 libstdc++ libgcc ca-certificates libc6-compat proxychains-ng

WORKDIR /app

# Copy all client binaries from their source images
COPY --from=earnfm-source /app/ /app/earnfm/
COPY --from=tm-source / /app/tm-stage/
COPY --from=rp-source / /app/rp-stage/
COPY --from=hg-source /app/ /app/hg/

# Make everything executable
RUN chmod -R +x /app/earnfm/ 2>/dev/null || true && \
    chmod -R +x /app/tm-stage/ 2>/dev/null || true && \
    chmod -R +x /app/rp-stage/ 2>/dev/null || true && \
    chmod -R +x /app/hg/ 2>/dev/null || true

COPY app.py /app/app.py

EXPOSE 10000

ENTRYPOINT ["python3", "-u", "/app/app.py"]
