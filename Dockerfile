# Dockerfile
FROM honeygain/honeygain:latest

# Jogosultság emelése a Python telepítéséhez
USER root

# Csomagkezelő detektálása és Python telepítése a webes ping és monitorozás miatt
RUN command -v apk >/dev/null && apk add --no-cache python3 || \
    (apt-get update && apt-get install -y python3)

WORKDIR /app
COPY app.py /app/app.py

EXPOSE 10000

CMD ["python3", "app.py"]
