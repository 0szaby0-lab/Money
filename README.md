# Honeygain + Cloudflare 1.1.1.1 WARP (Render.com Node)

Ez a projekt lehetővé teszi a **Honeygain** futtatását a [Render.com](https://render.com) ingyenes (Free Web Service) felhős környezetében úgy, hogy a teljes hálózati forgalom és a DNS-lekérdezések a **Cloudflare 1.1.1.1 WARP (UDP WireGuard)** alagúton keresztül mennek át.

Ez megoldja a Render közvetlen adatközponti IP-címének letiltását (*"API Error: Network Unusable"*).

---

## 🚀 Hogyan működik? (Architektúra)

1. **Cloudflare WARP (Traffic and DNS - UDP)**:
   A container a Cloudflare hivatalos WireGuard hálózatára csatlakozik (UDP 2408-as porton a `162.159.192.1` / `engage.cloudflareclient.com` végpontra).
2. **Userspace WireGuard (`wireproxy`)**:
   Mivel a Render nem engedélyezi a `--cap-add=NET_ADMIN` jogosultságot és a `/dev/net/tun` virtuális eszközt, a WireGuard kapcsolat tisztán felhasználói rétegben (userspace Go netstack) épül fel, root/kernel jogosultságok nélkül.
3. **SOCKS5 + Proxychains4**:
   A `wireproxy` egy helyi SOCKS5 interfészt biztosít (`127.0.0.1:1080`), amelyen keresztül a `proxychains4` segítségével a Honeygain kliens összes TCP kapcsolata és DNS feloldása közvetlenül a Cloudflare 1.1.1.1 hálózatán fut.
4. **Render HTTP Health Check Server**:
   A Render ingyenes Web Service-ként vár egy élő HTTP szervert a `$PORT` porton (10000). A beépített Python szerver 200 OK státuszt és élő állapotjelentést küld a Rendernek.

---

## 🛠️ Telepítés Render.com-ra

### 1. Lépés: Repository Fork / Csatlakoztatás
1. Nyisd meg a [Render Dashboardot](https://dashboard.render.com).
2. Kattints a **New +** -> **Web Service** gombra.
3. Válaszd ki a GitHub fiókodhoz csatolt `Money` repót.

### 2. Lépés: Beállítások (Render Web Service)
- **Name:** `honeygain-warp-node` (vagy tetszőleges)
- **Region:** Frankfurt (vagy Ohio / Oregon)
- **Runtime:** `Docker`
- **Instance Type:** `Free`

### 3. Lépés: Környezeti változók (Environment Variables)

A Render felületén a **Environment** fül alatt állítsd be az alábbi változókat:

| Változó | Leírás | Kötelező? | Példa érték |
|---|---|:---:|---|
| `HNY_EMAIL` | A Honeygain fiókod email címe | **Igen** | `pelda@gmail.com` |
| `HNY_PASS` | A Honeygain fiókod jelszava | **Igen** | `Jelszavad123` |
| `DEVICE_NAME` | Az eszköz neve a Honeygain dashboardon | Nem | `Render-Warp-Node` |
| `WARP_PRIVATE_KEY` | Saját Cloudflare WARP WireGuard privát kulcs | Opcionális* | `aB3...=` |
| `WARP_ADDRESS` | Saját Cloudflare WARP belső IP | Opcionális* | `172.16.0.2/32` |
| `WARP_CONF_BASE64` | Teljes WireGuard profil Base64 kódolva | Opcionális* | `W0ludGVyZmFjZV0...` |

> 💡 **Megjegyzés:** Ha nem adsz meg saját WARP kulcsot, a container automatikusan megpróbál regisztrálni egy új Cloudflare WARP profilt a `wgcf` segítségével. Ha a Cloudflare API az adatközponti IP miatt korlátozná az automatikus regisztrációt, futtasd a mellékelt `python register_warp.py` scriptet a gépeden, és másold be a kapott kulcsokat a Render Environment fülre!

---

## 💻 Saját WARP profil generálása (1 kattintással)

Ha szeretnél saját WARP kulcsot használni:
```bash
python register_warp.py
```
A script automatikusan regisztrál egy profilt és kiírja a Renderbe másolandó kulcsokat.

---

## 📊 Állapot lekérdezése

A Render által generált URL-t (`https://<app-name>.onrender.com/`) böngészőben megnyitva egy JSON állapotképet kapsz:
```json
{
  "service": "Honeygain Cloudflare WARP Node",
  "mode": "Traffic and DNS (UDP) - 1.1.1.1 WARP",
  "warp_connected": true,
  "warp_ip": "104.28.x.x",
  "warp_type": "on",
  "honeygain_running": true,
  "device_name": "Render-Cloudflare-Warp-01",
  "uptime_seconds": 3600
}
```
