import os
import sys
import time
import json
import socket
import random
import shutil
import urllib.request
import subprocess
import concurrent.futures
from threading import Thread, Lock
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 10000))

# EarnFM
EARNFM_TOKEN = os.environ.get("EARNFM_TOKEN", "").strip()

# Traffmonetizer
TM_TOKEN = os.environ.get("TM_TOKEN", "").strip()

# Repocket
RP_EMAIL = os.environ.get("RP_EMAIL", "").strip()
RP_API_KEY = os.environ.get("RP_API_KEY", "").strip()

# Honeygain
HNY_EMAIL = os.environ.get("HNY_EMAIL", "").strip()
HNY_PASS = os.environ.get("HNY_PASS", "").strip()
HNY_DEVICE = os.environ.get("DEVICE_NAME", "Render-Node").strip()

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=3000&country=all"
]

HG_DOMAIN = b"api.honeygain.com"
HG_CONNECT_REQ = b"\x05\x01\x00\x03" + bytes([len(HG_DOMAIN)]) + HG_DOMAIN + b"\x01\xbb"

state_lock = Lock()
app_states = {}
hg_pool = []


# ═══════════════════════════════════════════
# HTTP Health Check Server (Render requirement)
# ═══════════════════════════════════════════

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        with state_lock:
            body = json.dumps({
                "service": "Multi-App Passive Income Node",
                "apps": dict(app_states),
                "hg_pool_size": len(hg_pool)
            }).encode()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass

def run_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    print(f"[HTTP] Render health check server running on port {PORT}")
    server.serve_forever()


# ═══════════════════════════════════════════
# Binary Discovery
# ═══════════════════════════════════════════

def find_binary(search_dirs, names):
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            for name in names:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    os.chmod(path, 0o755)
                    return path
        for root, dirs, files in os.walk(d):
            for f in files:
                fpath = os.path.join(root, f)
                if os.path.isfile(fpath) and not f.endswith(('.py', '.sh', '.conf', '.txt', '.md', '.json', '.yml', '.yaml', '.so')):
                    try:
                        st = os.stat(fpath)
                        if st.st_size > 50000:
                            os.chmod(fpath, 0o755)
                            return fpath
                    except:
                        pass
    return None

def debug_list_dir(label, path):
    if not os.path.isdir(path):
        print(f"[DEBUG] {label}: {path} does not exist")
        return
    for root, dirs, files in os.walk(path):
        for f in files:
            fpath = os.path.join(root, f)
            try:
                sz = os.path.getsize(fpath)
                if sz > 10000:
                    print(f"[DEBUG] {label}: {fpath} ({sz} bytes)")
            except:
                pass


# ═══════════════════════════════════════════
# EarnFM (datacenter OK - guaranteed)
# ═══════════════════════════════════════════

def run_earnfm():
    if not EARNFM_TOKEN:
        print("[EARNFM] Skipped: EARNFM_TOKEN not set")
        with state_lock:
            app_states["earnfm"] = "Skipped (no token)"
        return

    debug_list_dir("EARNFM", "/app/earnfm")
    binary = find_binary(["/app/earnfm"], ["earnfm_example", "main", "earnfm"])
    if not binary:
        print("[EARNFM] ERROR: Binary not found")
        with state_lock:
            app_states["earnfm"] = "Error: binary not found"
        return

    print(f"[EARNFM] Using binary: {binary}")
    env = os.environ.copy()
    env["EARNFM_TOKEN"] = EARNFM_TOKEN

    while True:
        with state_lock:
            app_states["earnfm"] = "Running"
        try:
            proc = subprocess.Popen([binary], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                print(f"[EARNFM] {line.strip()}")
            proc.wait()
            print(f"[EARNFM] Exited ({proc.returncode}). Restarting in 10s...")
        except Exception as e:
            print(f"[EARNFM] Error: {e}")
        with state_lock:
            app_states["earnfm"] = "Restarting..."
        time.sleep(10)


# ═══════════════════════════════════════════
# Traffmonetizer (datacenter OK - guaranteed)
# ═══════════════════════════════════════════

def run_traffmonetizer():
    if not TM_TOKEN:
        print("[TRAFFMON] Skipped: TM_TOKEN not set")
        with state_lock:
            app_states["traffmonetizer"] = "Skipped (no token)"
        return

    debug_list_dir("TRAFFMON", "/app/tm-stage")
    binary = find_binary(["/app/tm-stage", "/app/tm-stage/usr", "/app/tm-stage/bin", "/app/tm-stage/opt"], ["Cli", "cli", "traffmonetizer", "tm"])
    if not binary:
        print("[TRAFFMON] ERROR: Binary not found")
        with state_lock:
            app_states["traffmonetizer"] = "Error: binary not found"
        return

    print(f"[TRAFFMON] Using binary: {binary}")
    while True:
        with state_lock:
            app_states["traffmonetizer"] = "Running"
        try:
            proc = subprocess.Popen([binary, "start", "accept", "--token", TM_TOKEN], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                print(f"[TRAFFMON] {line.strip()}")
            proc.wait()
            print(f"[TRAFFMON] Exited ({proc.returncode}). Restarting in 10s...")
        except Exception as e:
            print(f"[TRAFFMON] Error: {e}")
        with state_lock:
            app_states["traffmonetizer"] = "Restarting..."
        time.sleep(10)


# ═══════════════════════════════════════════
# Repocket (datacenter OK - guaranteed)
# ═══════════════════════════════════════════

def run_repocket():
    if not RP_EMAIL or not RP_API_KEY:
        print("[REPOCKET] Skipped: RP_EMAIL or RP_API_KEY not set")
        with state_lock:
            app_states["repocket"] = "Skipped (no credentials)"
        return

    debug_list_dir("REPOCKET", "/app/rp-stage")
    binary = find_binary(["/app/rp-stage", "/app/rp-stage/usr", "/app/rp-stage/bin", "/app/rp-stage/opt"], ["repocket", "rp"])
    if not binary:
        print("[REPOCKET] ERROR: Binary not found")
        with state_lock:
            app_states["repocket"] = "Error: binary not found"
        return

    print(f"[REPOCKET] Using binary: {binary}")
    env = os.environ.copy()
    env["RP_EMAIL"] = RP_EMAIL
    env["RP_API_KEY"] = RP_API_KEY

    while True:
        with state_lock:
            app_states["repocket"] = "Running"
        try:
            proc = subprocess.Popen([binary], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                print(f"[REPOCKET] {line.strip()}")
            proc.wait()
            print(f"[REPOCKET] Exited ({proc.returncode}). Restarting in 10s...")
        except Exception as e:
            print(f"[REPOCKET] Error: {e}")
        with state_lock:
            app_states["repocket"] = "Restarting..."
        time.sleep(10)


# ═══════════════════════════════════════════
# Honeygain (residential proxy required)
# ═══════════════════════════════════════════

def verify_socks5_to_hg_api(proxy_str):
    """Verifies SOCKS5 handshake + tunnel to api.honeygain.com:443."""
    try:
        ip, port = proxy_str.split(":")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.5)
        s.connect((ip, int(port)))
        s.sendall(b"\x05\x01\x00")
        r1 = s.recv(2)
        if r1 != b"\x05\x00":
            s.close()
            return None
        s.sendall(HG_CONNECT_REQ)
        r2 = s.recv(10)
        s.close()
        if len(r2) >= 2 and r2[1] == 0:
            return proxy_str
    except:
        pass
    return None

def harvest_clean_residential_proxies():
    """
    Strict 3-layer filter:
    1. Scrape thousands of SOCKS5 proxies from public feeds
    2. Verify live tunnel to api.honeygain.com:443
    3. Batch check with ip-api: MUST be hosting=false AND proxy=false
    """
    print("[HG-HARVEST] Scraping public SOCKS5 feeds...")
    candidates = set()
    for src in PROXY_SOURCES:
        try:
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                for line in resp.read().decode("utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if ":" in line and not line.startswith("#"):
                        candidates.add(line)
        except:
            pass

    all_cands = list(candidates)
    random.shuffle(all_cands)
    batch = all_cands[:800]
    print(f"[HG-HARVEST] Scraped {len(all_cands)} total. Testing API tunnel on {len(batch)} candidates...")

    api_reachable = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
        for res in ex.map(verify_socks5_to_hg_api, batch):
            if res:
                api_reachable.append(res)

    print(f"[HG-HARVEST] API-reachable proxies: {len(api_reachable)}")
    if not api_reachable:
        return

    # Check residential + not flagged as proxy
    query_batch = api_reachable[:100]
    payload = [{"query": p.split(":")[0], "fields": "query,hosting,proxy,isp,country"} for p in query_batch]

    clean_map = {}
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request("http://ip-api.com/batch", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            results = json.loads(resp.read().decode())
            for item in results:
                if not item.get("hosting") and not item.get("proxy"):
                    clean_map[item.get("query")] = item
    except Exception as e:
        print(f"[HG-HARVEST] IP-API error: {e}")

    clean_proxies = [p for p in query_batch if p.split(":")[0] in clean_map]
    print(f"[HG-HARVEST] CLEAN residential (hosting=false, proxy=false): {len(clean_proxies)}")

    with state_lock:
        for p in clean_proxies:
            if p not in hg_pool:
                hg_pool.append(p)
                ip = p.split(":")[0]
                info = clean_map.get(ip, {})
                print(f"[HG-HARVEST] Added: {p} -> {info.get('isp')} ({info.get('country')})")

def hg_background_harvester():
    while True:
        try:
            with state_lock:
                pool_len = len(hg_pool)
            if pool_len < 3:
                harvest_clean_residential_proxies()
        except Exception as e:
            print(f"[HG-HARVEST] Loop error: {e}")
        time.sleep(25)

def update_proxychains(ip, port):
    content = f"""strict_chain
tcp_read_time_out 15000
tcp_connect_time_out 8000

[ProxyList]
socks5 {ip} {port}
"""
    for path in ["/etc/proxychains.conf", "/etc/proxychains4.conf"]:
        try:
            with open(path, "w") as f:
                f.write(content)
        except:
            pass

def run_honeygain():
    if not HNY_EMAIL or not HNY_PASS:
        print("[HONEYGAIN] Skipped: HNY_EMAIL or HNY_PASS not set")
        with state_lock:
            app_states["honeygain"] = "Skipped (no credentials)"
        return

    binary = find_binary(["/app/hg"], ["honeygain"])
    if not binary:
        print("[HONEYGAIN] ERROR: Binary not found in /app/hg/")
        with state_lock:
            app_states["honeygain"] = "Error: binary not found"
        return

    proxychains_bin = "proxychains4" if shutil.which("proxychains4") else "proxychains"
    print(f"[HONEYGAIN] Using binary: {binary}, wrapper: {proxychains_bin}")

    # Start harvester thread
    Thread(target=hg_background_harvester, daemon=True).start()

    # Initial harvest
    harvest_clean_residential_proxies()

    while True:
        target = None
        while not target:
            with state_lock:
                if hg_pool:
                    target = hg_pool.pop(0)
            if not target:
                with state_lock:
                    app_states["honeygain"] = "Harvesting clean residential proxies..."
                time.sleep(3)

        ip, port = target.split(":")
        print(f"\n[HONEYGAIN] >>> Connecting via clean residential: {target} <<<")
        update_proxychains(ip, port)

        with state_lock:
            app_states["honeygain"] = f"Running on {target}"

        cmd = [proxychains_bin, "-q", binary, "-tou-accept", "-email", HNY_EMAIL, "-pass", HNY_PASS, "-device", HNY_DEVICE]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            rejected = False
            start_time = time.time()

            for line in proc.stdout:
                clean = line.strip()
                print(f"[HG-NODE] {clean}")

                if "API Error: Network Unusable" in clean or "Network Overused" in clean:
                    print(f"[HONEYGAIN] Proxy {target} rejected. Rotating...")
                    rejected = True
                    proc.terminate()
                    break

                if time.time() - start_time > 40 and not rejected:
                    with state_lock:
                        app_states["honeygain"] = f"ACTIVE & EARNING via {target}"
                    print(f"[HONEYGAIN] >>> ACCEPTED! Earning on {target} <<<")

            proc.wait()
            if rejected:
                time.sleep(1)
            else:
                time.sleep(3)

        except Exception as e:
            print(f"[HONEYGAIN] Error: {e}")
            time.sleep(3)


# ═══════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════

if __name__ == "__main__":
    print("=========================================================")
    print(" Multi-App Passive Income Node for Render.com Free Tier")
    print(" EarnFM + Traffmonetizer + Repocket + Honeygain")
    print("=========================================================")

    # 1. HTTP health check for Render
    Thread(target=run_health_server, daemon=True).start()

    # 2. Launch all configured apps in parallel
    active = []

    if EARNFM_TOKEN:
        Thread(target=run_earnfm, daemon=True).start()
        active.append("EarnFM")

    if TM_TOKEN:
        Thread(target=run_traffmonetizer, daemon=True).start()
        active.append("Traffmonetizer")

    if RP_EMAIL and RP_API_KEY:
        Thread(target=run_repocket, daemon=True).start()
        active.append("Repocket")

    if HNY_EMAIL and HNY_PASS:
        Thread(target=run_honeygain, daemon=True).start()
        active.append("Honeygain")

    if active:
        print(f"[SYSTEM] Active apps: {', '.join(active)}")
    else:
        print("[SYSTEM] WARNING: No app tokens configured! Set in Render Environment:")
        print("[SYSTEM]   EARNFM_TOKEN       -> https://app.earn.fm/")
        print("[SYSTEM]   TM_TOKEN           -> https://app.traffmonetizer.com/")
        print("[SYSTEM]   RP_EMAIL + RP_API_KEY -> https://app.repocket.com/")
        print("[SYSTEM]   HNY_EMAIL + HNY_PASS -> https://honeygain.com/")

    # Keep main thread alive
    while True:
        time.sleep(60)
