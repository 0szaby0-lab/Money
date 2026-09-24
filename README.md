# Honeygain Automated Public Proxy Hunter & Runner (Render.com)

Ez a rendszer önállóan, automatikusan keres és tesztel **több ezer publikus SOCKS5 proxyt**, ellenőrzi az elérhetőségüket és közvetlen kapcsolatukat a Honeygain szervereivel, majd elindítja a Honeygaint.

Amint egy IP-t a Honeygain elutasít (`API Error: Network Unusable`), a felügyelő démon azonnal (1-2 másodpercen belül) továbbugrik a következő ellenőrzött, működő jelöltre, amíg meg nem találja azt, ami aktív és elfogadott!

---

## ⚡ Főbb funkciók

1. **Automatikus forrásgyűjtés (Multi-Source Harvesting):**
   Több megbízható és folyamatosan frissülő publikus GitHub repo-ból gyűjti a SOCKS5 proxykat (monosans, TheSpeedX, hookzof, MuRongPIG).
2. **Ultragyors natív socket tesztelő:**
   Párhuzamos szálakon (50 szál) teszteli a proxyk SOCKS5 kézfogását és közvetlen csatlakozását az `api.honeygain.com:443`-hoz. A nem válaszoló vagy lassú proxykat azonnal kiszűri.
3. **Aktív hibatűrés és forgatás (Active Failover):**
   A Honeygain naplóját valós időben figyeli. Ha `API Error: Network Unusable` üzenetet kap, 1 másodperc alatt leállítja a folyamatot, átírja a proxychains konfigurációt, és a következő működő proxyval újrapróbálja.
4. **Automatikus utánpótlás (Background Daemon):**
   Amikor az ellenőrzött proxyk száma 10 alá esik, a háttérben automatikusan újabb 200 fős kört tesztel le, így soha nem fogy el a működő proxyk sora.
5. **Render 24/7 Health Check:**
   A `$PORT` (10000) porton JSON formátumú élő telemetriát szolgáltat (aktuális proxy, medence mérete, státusz).

---

## 🛠️ Beállítás a Render.com-on

A Render Dashboard **Environment** fülén mindössze a Honeygain adataid kellenek:

| Változó | Leírás | Kötelező? |
|---|---|:---:|
| `HNY_EMAIL` | A Honeygain fiókod email címe | **Igen** |
| `HNY_PASS` | A Honeygain fiókod jelszava | **Igen** |
| `DEVICE_NAME` | Eszköz neve a dashboardon | Nem (alapértelmezett: `Render-AutoHarvest-Node`) |
| `CUSTOM_PROXY` | Ha van saját privát proxyd, felülbírálja az automatát | Opcionális |

---

## 📊 Élő állapot ellenőrzése

Nyisd meg a Render URL-t (pl. `https://money-wubo.onrender.com/`):
```json
{
  "service": "Honeygain Auto-Harvesting SOCKS5 Node",
  "mode": "Automated Public Proxy Hunting & Validation",
  "status": "ACTIVE & EARNING via 5.75.133.113:10814",
  "active_proxy": "5.75.133.113:10814",
  "verified_pool_size": 24,
  "tested_total": 450,
  "honeygain_running": true,
  "device_name": "ArmorOS-Render-Node-01",
  "uptime_seconds": 3600,
  "last_log": "Honeygain service is starting"
}
```
