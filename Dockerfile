# Dockerfile - Honeygain 24/7 Automated Residential Node for Render
FROM honeygain/honeygain:latest

USER root

# Install Python 3, requests, and proxychains for dynamic residential routing
RUN command -v apk >/dev/null && apk add --no-cache python3 py3-requests proxychains-ng || \
    (apt-get update && apt-get install -y --no-install-recommends python3 python3-requests proxychains4 && rm -rf /var/lib/apt/lists/*)

WORKDIR /app

COPY app.py /app/app.py

EXPOSE 10000

ENTRYPOINT ["python3", "-u", "/app/app.py"]
