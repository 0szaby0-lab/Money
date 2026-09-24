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
EMAIL = os.environ.get("HNY_EMAIL", "").strip()
PASS = os.environ.get("HNY_PASS", "").strip()
DEVICE = os.environ.get("DEVICE_NAME", "Render-Honeygain-Node").strip()
CUSTOM_PROXY = os.environ.get("CUSTOM_PROXY", "").strip()

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=3000&country=all"
]

state_lock = Lock()
working_residential_pool = []
node_state = {
    "status": "Initializing...",
    "attempts": 0,
    "active_proxy": "None",
    "last_log": "Starting",
    "pool_size": 0
}

HG_DOMAIN = b"api.honeygain.com"
HG_CONNECT_REQ = b"\x05\x01\x00\x03" + bytes([len(HG_DOMAIN)]) + HG_DOMAIN + b"\x01\xbb"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        with state_lock:
            body = json.dumps({
                "service": "Honeygain Residential Node",
                "status": node_state["status"],
                "active_proxy": node_state["active_proxy"],
                "verified_pool_size": node_state["pool_size"],
                "last_log": node_state["last_log"]
            }).encode()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass

def run_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    print(f"[HTTP] Render health check server running on port {PORT}")
    server.serve_forever()

def verify_proxy_to_honeygain_api(proxy_str):
    """
    Two-step verification:
    1. SOCKS5 handshake.
    2. TCP tunnel directly to api.honeygain.com:443.
    """
    try:
        ip, port = proxy_str.split(":")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.5)
        s.connect((ip, int(port)))
        # Handshake
        s.sendall(b"\x05\x01\x00")
        resp1 = s.recv(2)
        if resp1 != b"\x05\x00":
            s.close()
            return None
        # Connect to api.honeygain.com:443
        s.sendall(HG_CONNECT_REQ)
        resp2 = s.recv(10)
        s.close()
        if len(resp2) >= 2 and resp2[1] == 0:
            return proxy_str
    except Exception:
        pass
    return None

def fetch_and_filter_residential_proxies():
    print("[HARVESTER] Scraping public SOCKS5 proxy feeds...")
    candidates = set()
    for src in PROXY_SOURCES:
        try:
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                lines = resp.read().decode("utf-8", errors="ignore").splitlines()
                for line in lines:
                    line = line.strip()
                    if ":" in line and not line.startswith("#"):
                        candidates.add(line)
        except Exception:
            pass

    all_cands = list(candidates)
    random.shuffle(all_cands)
    test_batch = all_cands[:500]
    print(f"[HARVESTER] Testing full Honeygain API tunnel on {len(test_batch)} candidates...")

    api_capable_proxies = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
        for res in executor.map(verify_proxy_to_honeygain_api, test_batch):
            if res:
                api_capable_proxies.append(res)

    print(f"[HARVESTER] Proxies with working tunnel to api.honeygain.com: {len(api_capable_proxies)}")
    if not api_capable_proxies:
        return

    # Check residential status on API-capable proxies
    batch_to_query = api_capable_proxies[:100]
    payload = [{"query": p.split(":")[0], "fields": "query,hosting,isp,country"} for p in batch_to_query]

    residential_map = {}
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request("http://ip-api.com/batch", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            results = json.loads(resp.read().decode())
            for item in results:
                if not item.get("hosting"):
                    residential_map[item.get("query")] = item
    except Exception as e:
        print(f"[HARVESTER] IP-API batch lookup error: {e}")

    verified_residential = [p for p in batch_to_query if p.split(":")[0] in residential_map]
    print(f"[HARVESTER] Verified API-REACHABLE Residential proxies: {len(verified_residential)}")

    with state_lock:
        for p in verified_residential:
            if p not in working_residential_pool:
                working_residential_pool.append(p)
                ip = p.split(":")[0]
                info = residential_map.get(ip, {})
                print(f"[HARVESTER] Verified ready: {p} -> {info.get('isp')} ({info.get('country')})")
        node_state["pool_size"] = len(working_residential_pool)

def background_harvester():
    while True:
        try:
            with state_lock:
                current_len = len(working_residential_pool)
            if current_len < 5:
                fetch_and_filter_residential_proxies()
        except Exception as e:
            print(f"[HARVESTER] Error in harvest loop: {e}")
        time.sleep(20)

def update_proxychains(ip, port):
    conf_content = f"""strict_chain
tcp_read_time_out 15000
tcp_connect_time_out 8000

[ProxyList]
socks5 {ip} {port}
"""
    for path in ["/etc/proxychains.conf", "/etc/proxychains4.conf", "/etc/proxychains/proxychains.conf"]:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(conf_content)
        except Exception:
            pass

def find_honeygain_binary():
    candidates = [
        shutil.which("honeygain"),
        "/app/honeygain",
        "/honeygain",
        "./honeygain",
        "/bin/honeygain",
        "/usr/local/bin/honeygain"
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return "honeygain"

def supervise_honeygain():
    if not EMAIL or not PASS:
        print("[SUPERVISOR] ERROR: HNY_EMAIL or HNY_PASS environment variables are missing!")
        with state_lock:
            node_state["status"] = "Missing HNY_EMAIL or HNY_PASS"
        while True:
            time.sleep(30)

    bin_path = find_honeygain_binary()
    proxychains_bin = "proxychains4" if shutil.which("proxychains4") else "proxychains"
    print(f"[SUPERVISOR] Using Honeygain binary: {bin_path} with wrapper {proxychains_bin}")

    while True:
        target_proxy = None
        if CUSTOM_PROXY:
            target_proxy = CUSTOM_PROXY
        else:
            while not target_proxy:
                with state_lock:
                    if working_residential_pool:
                        target_proxy = working_residential_pool.pop(0)
                        node_state["pool_size"] = len(working_residential_pool)
                if not target_proxy:
                    with state_lock:
                        node_state["status"] = "Harvesting API-verified residential proxies..."
                    time.sleep(2)

        ip, port = target_proxy.split(":")
        print(f"\n[SUPERVISOR] >>> Launching Honeygain via API-Verified Residential Node: {target_proxy} <<<")
        update_proxychains(ip, port)

        with state_lock:
            node_state["attempts"] += 1
            node_state["active_proxy"] = target_proxy
            node_state["status"] = f"Running on {target_proxy}"

        cmd = [
            proxychains_bin, "-q",
            bin_path,
            "-tou-accept",
            "-email", EMAIL,
            "-pass", PASS,
            "-device", DEVICE
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            rejected = False
            start_time = time.time()

            for line in proc.stdout:
                clean = line.strip()
                print(f"[HG-NODE] {clean}")
                with state_lock:
                    node_state["last_log"] = clean

                if "API Error: Network Unusable" in clean or "Network Overused" in clean:
                    print(f"[SUPERVISOR] Node {target_proxy} rejected by Honeygain perimeter. Rotating...")
                    rejected = True
                    proc.terminate()
                    break

                if time.time() - start_time > 35 and not rejected:
                    with state_lock:
                        node_state["status"] = f"ACTIVE & EARNING via {target_proxy}"
                        print(f"[SUCCESS] >>> Node {target_proxy} ACCEPTED by Honeygain! Actively earning. <<<")

            proc.wait()
            if rejected:
                time.sleep(1)
            else:
                print(f"[SUPERVISOR] Node {target_proxy} exited (code {proc.returncode}). Reconnecting in 3s...")
                time.sleep(3)

        except Exception as e:
            print(f"[SUPERVISOR] Error running node: {e}")
            time.sleep(3)

if __name__ == "__main__":
    print("=========================================================")
    print(" Honeygain 24/7 Residential Auto-Harvest Node for Render")
    print("=========================================================")
    
    server_t = Thread(target=run_health_server, daemon=True)
    server_t.start()

    if not CUSTOM_PROXY:
        fetch_and_filter_residential_proxies()
        harvester_t = Thread(target=background_harvester, daemon=True)
        harvester_t.start()

    supervise_honeygain()
