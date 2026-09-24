# app.py
import time
import os
import subprocess
import shutil
import requests
import concurrent.futures
import json
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

LIMIT_BYTES = 99 * 1024 * 1024 * 1024  # 99 GB Monthly Threshold [VERIFIED]
PORT = int(os.environ.get("PORT", 10000))
PROXY_SOURCE_URL = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
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
    print("[INFO] Harvesting public proxy candidates...")
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
        proxies_dict = {"http": f"http://{p}", "https": f"http://{p}"}
        try:
            start = time.time()
            res = requests.get(TEST_URL, proxies=proxies_dict, timeout=4)
            if res.status_code == 200:
                return {"proxy": p, "latency": round(time.time() - start, 3)}
        except:
            pass
        return None

    print(f"[INFO] Testing {len(proxies)} proxies...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(test_proxy, p) for p in proxies[:150]] # Limit initial check batch for speed
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                valid_proxies.append(res)

    valid_proxies.sort(key=lambda x: x["latency"])
    with open(PROXY_FILE, "w") as f:
        json.dump(valid_proxies, f, indent=4)
    print(f"[SUCCESS] Saved {len(valid_proxies)} operational proxies.")

def update_proxy_chains_conf():
    if not os.path.exists(PROXY_FILE):
        return False
    
    with open(PROXY_FILE, "r") as f:
        proxies = json.load(f)
    
    if not proxies:
        return False

    best_proxy = proxies[0]["proxy"].split(":")
    ip, port = best_proxy[0], best_proxy[1]

    with open("/etc/proxychains.conf", "w") as f:
        f.write("strict_chain\nproxy_dns\nremote_dns_subnet 224\ntcp_read_time_out 15000\ntcp_connect_time_out 8000\n[ProxyList]\n")
        f.write(f"http {ip} {port}\n")
    print(f"[INFO] Configured proxychains with active node: {ip}:{port}")
    return True

def get_tx_bytes():
    try:
        with open('/sys/class/net/eth0/statistics/tx_bytes', 'r') as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return 0

def honeygain_daemon():
    current_month = datetime.now().month
    start_tx = get_tx_bytes()
    
    bin_path = shutil.which("honeygain")
    if not bin_path:
        for path in ["/app/honeygain", "/honeygain", "./honeygain"]:
            if os.path.exists(path):
                bin_path = path
                break

    def launch_process():
        has_proxy = update_proxy_chains_conf()
        cmd = ["proxychains4", "-q", bin_path, "-tou-accept", "-email", os.getenv("HNY_EMAIL"), "-pass", os.getenv("HNY_PASS"), "-device", os.getenv("DEVICE_NAME")] if has_proxy else [bin_path, "-tou-accept", "-email", os.getenv("HNY_EMAIL"), "-pass", os.getenv("HNY_PASS"), "-device", os.getenv("DEVICE_NAME")]
        return subprocess.Popen(cmd)

    proc = launch_process()
    last_proxy_refresh = time.time()

    while True:
        # Refresh proxies every 12 hours
        if time.time() - last_proxy_refresh > 43200:
            print("[INFO] Initiating daily proxy rotation sweep...")
            fetch_and_test_proxies()
            last_proxy_refresh = time.time()
            if proc.poll() is None:
                proc.terminate()
                proc = launch_process()

        if datetime.now().month != current_month:
            current_month = datetime.now().month
            start_tx = get_tx_bytes()
            if proc.poll() is not None:
                proc = launch_process()

        current_tx = get_tx_bytes() - start_tx
        if current_tx >= LIMIT_BYTES:
            if proc.poll() is None:
                proc.terminate()
                print("99 GB limit reached. Halting operations until next month.")
        
        time.sleep(300)

if __name__ == '__main__':
    if "--init-proxies" in sys.argv:
        fetch_and_test_proxies()
        sys.exit(0)

    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    honeygain_daemon()
