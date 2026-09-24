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
    "https://raw.githubusercontent.com/roosterkid/openproxies/main/socks5_proxies.txt"
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

def check_socks5_handshake(proxy_str):
    """Tests raw SOCKS5 handshake (b'\x05\x01\x00' -> b'\x05\x00') in under 2.5 seconds."""
    try:
        ip, port = proxy_str.split(":")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.5)
        s.connect((ip, int(port)))
        s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        s.close()
        if resp == b"\x05\x00":
            return proxy_str
    except Exception:
        pass
    return None

def fetch_and_filter_residential_proxies():
    """Scrapes SOCKS5 lists, batch-filters out datacenter IPs via ip-api, and verifies live handshakes."""
    print("[HARVESTER] Scraping public SOCKS5 proxy feeds...")
    candidates = set()
    for src in PROXY_SOURCES:
        try:
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                lines = resp.read().decode("utf-8", errors="ignore").splitlines()
                for line in lines:
                    line = line.strip()
                    if ":" in line and not line.startswith("#"):
                        candidates.add(line)
        except Exception as e:
            print(f"[HARVESTER] Warning reading {src.split('/')[-1]}: {e}")

    raw_list = list(candidates)
    random.shuffle(raw_list)
    print(f"[HARVESTER] Total scraped candidates: {len(raw_list)}. Selecting batch of 100 for residential filtering...")

    batch = raw_list[:100]
    query_payload = [{"query": p.split(":")[0], "fields": "query,hosting"} for p in batch]

    residential_ips = set()
    try:
        data = json.dumps(query_payload).encode()
        req = urllib.request.Request("http://ip-api.com/batch", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read().decode())
            for item in results:
                if not item.get("hosting"):  # hosting == False means Residential ISP!
                    residential_ips.add(item.get("query"))
    except Exception as e:
        print(f"[HARVESTER] Residential filter error: {e}")

    residential_candidates = [p for p in batch if p.split(":")[0] in residential_ips]
    print(f"[HARVESTER] Residential ISP candidates found: {len(residential_candidates)}. Testing live handshakes...")

    verified = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        for res in executor.map(check_socks5_handshake, residential_candidates):
            if res:
                verified.append(res)

    print(f"[HARVESTER] Live verified residential proxies: {len(verified)}")
    with state_lock:
        for p in verified:
            if p not in working_residential_pool:
                working_residential_pool.append(p)
        node_state["pool_size"] = len(working_residential_pool)

def background_harvester():
    """Replenishes the pool whenever it drops below 5 proxies."""
    while True:
        try:
            with state_lock:
                current_len = len(working_residential_pool)
            if current_len < 5:
                fetch_and_filter_residential_proxies()
        except Exception as e:
            print(f"[HARVESTER] Error in harvest loop: {e}")
        time.sleep(30)

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
                        node_state["status"] = "Waiting for verified residential proxy..."
                    time.sleep(3)

        ip, port = target_proxy.split(":")
        print(f"\n[SUPERVISOR] >>> Connecting Honeygain via Residential Proxy: {target_proxy} <<<")
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
                    print(f"[SUPERVISOR] Proxy {target_proxy} rejected by Honeygain perimeter. Rotating...")
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
                print("[SUPERVISOR] Process ended. Reconnecting in 5s...")
                time.sleep(5)

        except Exception as e:
            print(f"[SUPERVISOR] Error running node: {e}")
            time.sleep(3)

if __name__ == "__main__":
    print("=========================================================")
    print(" Honeygain 24/7 Residential Auto-Harvest Node for Render")
    print("=========================================================")
    
    # 1. Start HTTP health check server for Render (responds 200 OK on $PORT)
    server_t = Thread(target=run_health_server, daemon=True)
    server_t.start()

    # 2. Pre-fill residential pool
    if not CUSTOM_PROXY:
        fetch_and_filter_residential_proxies()
        harvester_t = Thread(target=background_harvester, daemon=True)
        harvester_t.start()

    # 3. Supervise Honeygain with auto-failover
    supervise_honeygain()
