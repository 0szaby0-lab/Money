# Dockerfile - Honeygain with Cloudflare 1.1.1.1 WARP Tunnel
FROM honeygain/honeygain:latest

USER root

# Install dependencies (Python 3, proxychains4, curl, ca-certificates, tar, procps)
RUN if command -v apt-get >/dev/null 2>&1; then \
        apt-get update && apt-get install -y --no-install-recommends \
            ca-certificates curl python3 proxychains4 tar iproute2 procps && \
        rm -rf /var/lib/apt/lists/*; \
    elif command -v apk >/dev/null 2>&1; then \
        apk add --no-cache ca-certificates curl python3 proxychains-ng tar procps; \
    fi

# Download wgcf (Cloudflare WARP registration utility)
RUN curl -fsSL https://github.com/ViRb3/wgcf/releases/download/v2.3.0/wgcf_2.3.0_linux_amd64 -o /usr/local/bin/wgcf && \
    chmod +x /usr/local/bin/wgcf

# Download wireproxy (Userspace WireGuard client providing SOCKS5/HTTP proxy without TUN/NET_ADMIN)
RUN curl -fsSL https://github.com/windtf/wireproxy/releases/download/v1.1.3/wireproxy_linux_amd64.tar.gz | tar -xz -C /usr/local/bin/ wireproxy && \
    chmod +x /usr/local/bin/wireproxy

WORKDIR /app

COPY entrypoint.sh /app/entrypoint.sh
COPY app.py /app/app.py

RUN chmod +x /app/entrypoint.sh

# Render binds to $PORT (default 10000)
EXPOSE 10000

ENTRYPOINT ["/app/entrypoint.sh"]
