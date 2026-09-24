#!/bin/sh

# Proxychains konfiguráció dinamikus generálása [VERIFIED]
echo "strict_chain" > /etc/proxychains.conf
echo "proxy_dns" >> /etc/proxychains.conf
echo "remote_dns_subnet 224" >> /etc/proxychains.conf
echo "tcp_read_time_out 15000" >> /etc/proxychains.conf
echo "tcp_connect_time_out 8000" >> /etc/proxychains.conf
echo "[ProxyList]" >> /etc/proxychains.conf

# Proxy adatok beillesztése a környezeti változókból
echo "socks5 $RESIDENTIAL_PROXY_IP $RESIDENTIAL_PROXY_PORT $RESIDENTIAL_PROXY_USER $RESIDENTIAL_PROXY_PASS" >> /etc/proxychains.conf

# A Python monitorozó daemon indítása
exec python3 app.py
