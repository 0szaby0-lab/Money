# 1. lépés: Hivatalos Honeygain konténer
FROM honeygain/honeygain:latest AS honeygain-source

# 2. lépés: Python futtatókörnyezet a webes szerverhez és monitoringhoz
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    procps \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# A teljes /app mappát átmásoljuk (a .so könyvtárakkal és függőségekkel együtt)
COPY --from=honeygain-source /app /app
RUN chmod +x /app/honeygain

# Beállítjuk a dinamikus linker útvonalát, hogy megtalálja a libhg.so-t
ENV LD_LIBRARY_PATH="/app:$LD_LIBRARY_PATH"

# Alkalmazás script bemásolása
COPY app.py /app/app.py

EXPOSE 10000

CMD ["python3", "app.py"]
