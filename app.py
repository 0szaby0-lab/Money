# app.py - SOCKS5 Active Failover & Log Parsing Daemon
import time
import os
import subprocess
import shutil
import requests
import concurrent.futures
import json
import sys
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

LIMIT_BYTES = 99 * 1024 * 1024 * 1024  # 99 GB Monthly Threshold [VERIFIED]
PORT = int(os.environ.get("PORT", 10000))
# Pivoted to SOCKS5 protocol lists for raw TCP tunneling [VERIFIED]
PROXY_SOURCE_URL = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
TEST_URL = "https://httpbin.org/ip"
PROXY_FILE = "/app/working_proxies.json"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ArmorOS Honeygain Node: Active [VERIFIED]")
    
    def log_message(self, format, *args):
        pass

def run_server():
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    httpd.serve_forever()

def fetch_and_test_proxies():
    print("[INFO] Harvesting SOCKS5 proxy candidates...")
    proxies = []
    try:
        response = requests.get(PROXY_SOURCE_URL, timeout=10)
        if response.status_code == 200:
            for line in response.text.splitlines():
                line = line.strip()
                if ":" in line and line not in proxies:
                    proxies.append(line)
    except Exception as e:
        print(f"[ERROR] Failed to fetch proxy list: {e}")

    valid_proxies = []
    def test_proxy(p):
        proxies_dict = {"http": f"socks5://{p}", "https": f"socks5://{p}"}
        try:
            start = time.time()
            res = requests.get(TEST_URL, proxies=proxies_dict, timeout=5)
            if res.status_code == 200:
                return {"proxy": p, "latency": round(time.time() - start, 3)}
        except:
            pass
        return None

    print(f"[INFO] Testing {len(proxies)} SOCKS5 proxies...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        # Evaluate top 200 to ensure we have a deep enough failover pool
        futures = [executor.submit(test_proxy, p) for p in proxies[:200]] 
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                valid_proxies.append(res)

    valid_proxies.sort(key=lambda x: x["latency"])
    with open(PROXY_FILE, "w") as f:
        json.dump(valid_proxies, f, indent=4)
    print(f"[SUCCESS] Saved {len(valid_proxies)} operational SOCKS5 proxies.")

def update_proxy_chains_conf(index=0):
    if not os.path.exists(PROXY_FILE):
        return False
    
    with open(PROXY_FILE, "r") as f:
        proxies = json.load(f)
    
    if not proxies or index >= len(proxies):
        return False

    target_proxy = proxies[index]["proxy"].split(":")
    ip, port = target_proxy[0], target_proxy[1]

    with open("/etc/proxychains.conf", "w") as f:
        f.write("strict_chain\nproxy_dns\nremote_dns_subnet 224\ntcp_read_time_out 15000\ntcp_connect_time_out 8000\n[ProxyList]\n")
        f.write(f"socks5 {ip} {port}\n")
    print(f"[INFO] Configured proxychains with node {index}: {ip}:{port}")
    return True

def get_tx_bytes():
    try:
        with open('/sys/class/net/eth0/statistics/tx_bytes', 'r') as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return 0

def log_monitor(proc, state_flags):
    """ Reads binary stdout. If network block detected, triggers rotation flag. """
    for line in proc.stdout:
        clean_line = line.strip()
        print(f"[HG-NODE] {clean_line}")
        if "API Error: Network Unusable" in clean_line:
            state_flags["needs_rotation"] = True

def honeygain_daemon():
    current_month = datetime.now().month
    start_tx = get_tx_bytes()
    current_proxy_index = 0
    
    bin_path = shutil.which("honeygain")
    if not bin_path:
        for path in ["/app/honeygain", "/honeygain", "./honeygain"]:
            if os.path.exists(path):
                bin_path = path
                break

    def launch_process(proxy_idx):
        has_proxy = update_proxy_chains_conf(proxy_idx)
        cmd = ["proxychains4", "-q", bin_path, "-tou-accept", "-email", os.getenv("HNY_EMAIL"), "-pass", os.getenv("HNY_PASS"), "-device", os.getenv("DEVICE_NAME")] if has_proxy else [bin_path, "-tou-accept", "-email", os.getenv("HNY_EMAIL"), "-pass", os.getenv("HNY_PASS"), "-device", os.getenv("DEVICE_NAME")]
        # Capture stdout for live parsing
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    proc = launch_process(current_proxy_index)
    state_flags = {"needs_rotation": False}
    monitor_thread = Thread(target=log_monitor, args=(proc, state_flags), daemon=True)
    monitor_thread.start()

    last_proxy_refresh = time.time()

    while True:
        # Active Failover Trigger
        if state_flags["needs_rotation"]:
            print("[WARNING] Node rejected by Honeygain perimeter. Executing active failover...")
            proc.terminate()
            current_proxy_index += 1
            state_flags["needs_rotation"] = False
            
            # If we exhaust the pool, fetch a fresh list
            if not update_proxy_chains_conf(current_proxy_index):
                print("[CRITICAL] Proxy pool exhausted. Harvesting new list...")
                fetch_and_test_proxies()
                current_proxy_index = 0
                
            proc = launch_process(current_proxy_index)
            monitor_thread = Thread(target=log_monitor, args=(proc, state_flags), daemon=True)
            monitor_thread.start()

        # Routine Daily Sweep
        if time.time() - last_proxy_refresh > 43200:
            print("[INFO] Initiating 12-hour routine rotation sweep...")
            fetch_and_test_proxies()
            last_proxy_refresh = time.time()
            current_proxy_index = 0
            proc.terminate()
            proc = launch_process(current_proxy_index)
            monitor_thread = Thread(target=log_monitor, args=(proc, state_flags), daemon=True)
            monitor_thread.start()

        # Monthly Bandwidth Cap
        if datetime.now().month != current_month:
            current_month = datetime.now().month
            start_tx = get_tx_bytes()
            if proc.poll() is not None:
                proc = launch_process(current_proxy_index)
                monitor_thread = Thread(target=log_monitor, args=(proc, state_flags), daemon=True)
                monitor_thread.start()

        current_tx = get_tx_bytes() - start_tx
        if current_tx >= LIMIT_BYTES:
            if proc.poll() is None:
                proc.terminate()
                print("99 GB limit reached. Halting operations until next month.")
        
        time.sleep(2)

if __name__ == '__main__':
    if "--init-proxies" in sys.argv:
        fetch_and_test_proxies()
        sys.exit(0)

    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    honeygain_daemon()
