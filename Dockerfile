# Dockerfile
FROM honeygain/honeygain:latest

USER root

# Install Python 3 and system utilities [VERIFIED]
RUN command -v apk >/dev/null && apk add --no-cache python3 py3-requests proxychains-ng || \
    (apt-get update && apt-get install -y python3 python3-requests proxychains4)

WORKDIR /app

COPY entrypoint.sh /app/entrypoint.sh
COPY app.py /app/app.py

RUN chmod +x /app/entrypoint.sh

EXPOSE 10000

ENTRYPOINT ["/app/entrypoint.sh"]
