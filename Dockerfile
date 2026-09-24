# Dockerfile - EarnFM 24/7 Passive Income Node for Render.com Free Web Service
FROM earnfm/earnfm-client:latest

USER root

# Install Python 3 for the Render HTTP health check web server
RUN apk update && apk add --no-cache python3

WORKDIR /app

COPY app.py /app/app.py

# Render binds to $PORT (default 10000)
EXPOSE 10000

ENTRYPOINT ["python3", "-u", "/app/app.py"]
