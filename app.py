# app.py - Automated Public SOCKS5 Harvester, Validator & Honeygain Supervisor
import os
import sys
import time
import shutil
import socket
import random
import subprocess
import urllib.request
import concurrent.futures
from threading import Thread, Lock
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

PORT = int(os.environ.get("PORT", 10000))
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt"
]

state_lock = Lock()
working_pool = []
tested_counter = 0

node_state = {
    "start_time": time.time(),
    "status": "Initializing proxy harvester...",
    "active_proxy": "none",
    "pool_size": 0,
    "tested_total": 0,
    "honeygain_running": False,
    "device_name": os.getenv("DEVICE_NAME", "Render-AutoHarvest-Node"),
    "last_log": "Booting system...",
    "attempts": 0,
    "successful_runs": 0
}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        with state_lock:
            payload = {
                "service": "Honeygain Auto-Harvesting SOCKS5 Node",
                "mode": "Automated Public Proxy Hunting & Validation",
                "status": node_state["status"],
                "active_proxy": node_state["active_proxy"],
                "verified_pool_size": len(working_pool),
                "tested_total": node_state["tested_total"],
                "honeygain_running": node_state["honeygain_running"],
                "device_name": node_state["device_name"],
                "uptime_seconds": int(time.time() - node_state["start_time"]),
                "last_log": node_state["last_log"]
            }
        self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        pass

def run_health_server():
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    httpd.serve_forever()

def test_socks5_candidate(proxy_str):
    """
    Tests raw SOCKS5 handshake directly towards api.honeygain.com:443.
    Returns (proxy_str, latency) if successful, None otherwise.
    """
    try:
        ip, port = proxy_str.split(":")
        port = int(port)
        start_t = time.time()

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.5)
        s.connect((ip, port))

        # Greeting: SOCKS5, 1 auth method (0x00 = No Auth)
        s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        if resp != b"\x05\x00":
            s.close()
            return None

        # Connect request: connect to api.honeygain.com:443 via proxy
        target = b"api.honeygain.com"
        req = b"\x05\x01\x00\x03" + bytes([len(target)]) + target + (443).to_bytes(2, "big")
        s.sendall(req)
        resp2 = s.recv(10)
        s.close()

        # Reply: version 5, status 0 (Success)
        if len(resp2) >= 4 and resp2[0] == 5 and resp2[1] == 0:
            latency = round(time.time() - start_t, 3)
            return (proxy_str, latency)
    except Exception:
        pass
    return None

def harvest_and_validate_batch(batch_size=150):
    """Fetches candidate proxies from multiple public repositories and validates a batch."""
    global tested_counter
    print("[HARVESTER] Scraping public SOCKS5 proxy feeds...")
    candidates = set()
    for src in PROXY_SOURCES:
        try:
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                for line in data.splitlines():
                    line = line.strip()
                    if line and ":" in line and not line.startswith("#"):
                        candidates.add(line)
        except Exception as e:
            print(f"[HARVESTER] Note: {src.split('/')[-1]} skipped: {e}")

    all_list = list(candidates)
    random.shuffle(all_list)
    print(f"[HARVESTER] Total unique candidates discovered: {len(all_list)}. Testing batch of {min(batch_size, len(all_list))}...")

    batch = all_list[:batch_size]
    with state_lock:
        tested_counter += len(batch)
        node_state["tested_total"] = tested_counter

    verified = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for res in executor.map(test_socks5_candidate, batch):
            if res:
                verified.append(res)

    verified.sort(key=lambda x: x[1])
    print(f"[HARVESTER] Batch complete. Valid operational proxies found: {len(verified)}")
    with state_lock:
        for p, lat in verified:
            if p not in working_pool:
                working_pool.append(p)
        node_state["pool_size"] = len(working_pool)

def background_harvester_daemon():
    """Continuously ensures the working proxy pool stays populated."""
    while True:
        try:
            with state_lock:
                current_pool_len = len(working_pool)
            if current_pool_len < 10:
                print(f"[POOL-MONITOR] Pool low ({current_pool_len} left). Triggering harvest sweep...")
                harvest_and_validate_batch(batch_size=200)
        except Exception as e:
            print(f"[HARVESTER] Error during harvest cycle: {e}")
        time.sleep(30)

def update_proxychains_conf(ip, port):
    """Configures proxychains to route all TCP connections through the chosen proxy."""
    content = f"""strict_chain
proxy_dns
remote_dns_subnet 224
tcp_read_time_out 10000
tcp_connect_time_out 5000

[ProxyList]
socks5 {ip} {port}
"""
    for p in ["/etc/proxychains.conf", "/etc/proxychains4.conf"]:
        try:
            with open(p, "w") as f:
                f.write(content)
        except Exception:
            pass

def find_honeygain_binary():
    """Locates the Honeygain executable."""
    b = shutil.which("honeygain")
    if b:
        return b
    for p in ["/app/honeygain", "/honeygain", "/bin/honeygain", "/usr/local/bin/honeygain"]:
        if os.path.exists(p):
            return p
    return None

def supervise_honeygain():
    """Main worker loop: tests candidate proxies against Honeygain and locks onto working ones."""
    email = os.getenv("HNY_EMAIL", "").strip()
    password = os.getenv("HNY_PASS", "").strip()
    device = os.getenv("DEVICE_NAME", "Render-AutoHarvest-Node").strip()
    custom_proxy = os.getenv("CUSTOM_PROXY", "").strip()

    if not email or not password:
        print("[SUPERVISOR] ERROR: HNY_EMAIL or HNY_PASS environment variables are missing.")
        with state_lock:
            node_state["last_log"] = "Missing HNY_EMAIL / HNY_PASS"
        while True:
            time.sleep(30)

    bin_path = find_honeygain_binary()
    if not bin_path:
        print("[SUPERVISOR] ERROR: Honeygain binary not found in container.")
        with state_lock:
            node_state["last_log"] = "Binary honeygain missing"
        while True:
            time.sleep(30)

    proxychains_bin = "proxychains4" if shutil.which("proxychains4") else "proxychains"

    while True:
        # Check if user set static CUSTOM_PROXY
        if custom_proxy:
            active_target = custom_proxy
            if "://" in custom_proxy:
                from urllib.parse import urlparse
                u = urlparse(custom_proxy)
                target_ip = u.hostname
                target_port = u.port or 1080
            else:
                parts = custom_proxy.split()
                target_ip = parts[1] if len(parts) > 1 else "127.0.0.1"
                target_port = parts[2] if len(parts) > 2 else "1080"
        else:
            # Pop next proxy from verified working pool
            proxy_candidate = None
            while not proxy_candidate:
                with state_lock:
                    if working_pool:
                        proxy_candidate = working_pool.pop(0)
                        node_state["pool_size"] = len(working_pool)
                if not proxy_candidate:
                    print("[SUPERVISOR] Waiting for proxy harvester to find candidates...")
                    with state_lock:
                        node_state["status"] = "Harvesting fresh proxies..."
                    time.sleep(3)

            target_ip, target_port = proxy_candidate.split(":")
            active_target = proxy_candidate

        with state_lock:
            node_state["attempts"] += 1
            node_state["active_proxy"] = active_target
            node_state["status"] = f"Testing candidate node: {active_target} (attempt #{node_state['attempts']})"
            node_state["honeygain_running"] = True

        print(f"\n[SUPERVISOR] === Launching Honeygain on node: {active_target} ===")
        update_proxychains_conf(target_ip, target_port)

        cmd = [
            proxychains_bin, "-q",
            bin_path,
            "-tou-accept",
            "-email", email,
            "-pass", password,
            "-device", device
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            rejected_by_network = False
            start_launch_time = time.time()

            for line in proc.stdout:
                clean = line.strip()
                print(f"[HG-NODE] {clean}")
                with state_lock:
                    node_state["last_log"] = clean

                # Detect network unusable / fraud block
                if "API Error: Network Unusable" in clean or "Network Overused" in clean:
                    print(f"[SUPERVISOR] Node {active_target} rejected by Honeygain perimeter ({clean}).")
                    rejected_by_network = True
                    proc.terminate()
                    break

                # If running for more than 40 seconds without rejection, it is accepted!
                elapsed = time.time() - start_launch_time
                if elapsed > 40 and not rejected_by_network:
                    with state_lock:
                        node_state["status"] = f"ACTIVE & EARNING via {active_target}"
                        node_state["successful_runs"] += 1
                        print(f"[SUCCESS] === Candidate {active_target} ACCEPTED by Honeygain! Running active node. ===")

            proc.wait()
            with state_lock:
                node_state["honeygain_running"] = False

            if rejected_by_network:
                print(f"[SUPERVISOR] Rotating to next candidate in queue...\n")
                time.sleep(1)
            else:
                print(f"[SUPERVISOR] Process exited. Waiting 5s before reconnecting...\n")
                time.sleep(5)

        except Exception as e:
            print(f"[SUPERVISOR] Exception during execution: {e}")
            time.sleep(3)

if __name__ == "__main__":
    print("==================================================")
    print(" Honeygain Automated Public Proxy Hunter & Runner")
    print(" Mode: Multi-Source Harvesting & Active Failover")
    print("==================================================")

    # 1. Start HTTP Health Server for Render
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    print(f"[SYSTEM] Render health check server listening on 0.0.0.0:{PORT}")

    # 2. Initial Proxy Harvesting Sweep
    harvest_and_validate_batch(batch_size=150)

    # 3. Start background harvester thread
    harvester_t = Thread(target=background_harvester_daemon, daemon=True)
    harvester_t.start()

    # 4. Run Honeygain Supervisor with Auto-Rotation
    supervise_honeygain()
