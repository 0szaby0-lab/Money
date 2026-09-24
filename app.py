import time
import os
import subprocess
import shutil
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

LIMIT_BYTES = 99 * 1024 * 1024 * 1024  # 99 GB Threshold
PORT = int(os.environ.get("PORT", 10000))

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Honeygain Node: Active")
    
    def log_message(self, format, *args):
        pass

def run_server():
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    httpd.serve_forever()

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
        for path in ["/app/honeygain", "/honeygain", "./honeygain", "/bin/honeygain"]:
            if os.path.exists(path):
                bin_path = path
                break
    if not bin_path:
        bin_path = "honeygain"
    
    email = str(os.getenv("HNY_EMAIL") or "").strip()
    password = str(os.getenv("HNY_PASS") or "").strip()
    device = str(os.getenv("DEVICE_NAME") or "ArmorOS-Render-Node-01").strip()

    print(f"[START] Launching Honeygain node: {device} using binary {bin_path}")
    
    cmd = [
        bin_path, 
        "-tou-accept", 
        "-email", email, 
        "-pass", password, 
        "-device", device
    ]

    proc = subprocess.Popen(cmd)

    while True:
        if datetime.now().month != current_month:
            current_month = datetime.now().month
            start_tx = get_tx_bytes()
            if proc.poll() is not None:
                proc = subprocess.Popen(cmd)

        current_tx = get_tx_bytes() - start_tx
        if current_tx >= LIMIT_BYTES:
            if proc.poll() is None:
                proc.terminate()
                print("99 GB limit reached. Halting operations until next month.")
        
        time.sleep(15)

if __name__ == '__main__':
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    honeygain_daemon()
