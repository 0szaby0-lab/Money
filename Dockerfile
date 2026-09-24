# Dockerfile - Web-Enabled Container Configuration
FROM alpine:latest

RUN apk add --no-cache curl python3 libc6-compat

RUN addgroup -S honeygroup && adduser -S honeyuser -G honeygroup

WORKDIR /app
RUN curl -sL https://dorianpritchard.com/honeygain/honeygain-linux -o honeygain && \
    chmod +x honeygain

COPY app.py /app/app.py

USER honeyuser

EXPOSE 10000

CMD ["python3", "app.py"]
