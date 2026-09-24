# Multi-App Passive Income Node for Render.com Free Tier
# Runs EarnFM + Traffmonetizer + Repocket simultaneously
# All three accept datacenter IPs natively - no proxy needed

# Stage 1: Extract EarnFM binary
FROM earnfm/earnfm-client:latest AS earnfm-source

# Stage 2: Extract Traffmonetizer binary
FROM traffmonetizer/cli_v2 AS tm-source

# Stage 3: Extract Repocket binary
FROM repocket/repocket AS rp-source

# Stage 4: Final lightweight container
FROM alpine:latest

RUN apk add --no-cache python3 libstdc++ libgcc ca-certificates libc6-compat

WORKDIR /app

# Copy all three client binaries
COPY --from=earnfm-source /app/ /app/earnfm/
COPY --from=tm-source / /app/tm-stage/
COPY --from=rp-source / /app/rp-stage/

# Make everything executable
RUN find /app -type f -executable -o -name "*.so*" | head -50 && \
    chmod -R +x /app/earnfm/ 2>/dev/null || true && \
    chmod -R +x /app/tm-stage/ 2>/dev/null || true && \
    chmod -R +x /app/rp-stage/ 2>/dev/null || true

COPY app.py /app/app.py

EXPOSE 10000

ENTRYPOINT ["python3", "-u", "/app/app.py"]
