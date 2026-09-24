# 1. lépés: Hivatalos Honeygain konténerből kinyerjük a binárist
FROM honeygain/honeygain:latest AS honeygain-source

# 2. lépés: Python alapú futtatókörnyezet a webes ping és adatforgalom-figyelő miatt
FROM python:3.11-slim

# Alapvető csomagok telepítése (Debian kompatibilis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Átmásoljuk a hivatalos futtatható binárist
COPY --from=honeygain-source /app/honeygain /app/honeygain
RUN chmod +x /app/honeygain

# Alkalmazás script másolása
COPY app.py /app/app.py

EXPOSE 10000

CMD ["python3", "app.py"]
