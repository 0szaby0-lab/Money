FROM honeygain/honeygain:latest

# Jogosultság emelése
USER root

# Python és Proxychains telepítése [VERIFIED]
RUN command -v apk >/dev/null && apk add --no-cache python3 proxychains-ng || \
    (apt-get update && apt-get install -y python3 proxychains4)

WORKDIR /app

# Konfigurációs és futtató scriptek másolása
COPY entrypoint.sh /app/entrypoint.sh
COPY app.py /app/app.py

RUN chmod +x /app/entrypoint.sh

EXPOSE 10000

# Felülírjuk a gyári belépési pontot
ENTRYPOINT ["/app/entrypoint.sh"]
