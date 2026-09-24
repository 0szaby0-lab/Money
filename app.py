# app.py - Direct Render Node for Honeygain (Native IP, No VPN, No Proxy)
import os
import sys
import time
import shutil
import subprocess
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

PORT = int(os.environ.get("PORT", 10000))

node_state = {
    "start_time": time.time(),
    "mode": "Direct Render Native IP (No VPN / No Proxy)",
    "honeygain_running": False,
    "device_name": os.getenv("DEVICE_NAME", "Render-Direct-Node"),
    "last_log": "Initializing direct node...",
    "restarts": 0
}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {
            "service": "Honeygain Render Direct Node",
            "mode": node_state["mode"],
            "honeygain_running": node_state["honeygain_running"],
            "device_name": node_state["device_name"],
            "uptime_seconds": int(time.time() - node_state["start_time"]),
            "last_log": node_state["last_log"],
            "restarts": node_state["restarts"]
        }
        self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        pass

def run_health_server():
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    httpd.serve_forever()

def find_honeygain_binary():
    b = shutil.which("honeygain")
    if b:
        return b
    for p in ["/app/honeygain", "/honeygain", "/bin/honeygain", "/usr/local/bin/honeygain"]:
        if os.path.exists(p):
            return p
    return None

def run_direct_honeygain():
    email = os.getenv("HNY_EMAIL", "").strip()
    password = os.getenv("HNY_PASS", "").strip()
    device = os.getenv("DEVICE_NAME", "Render-Direct-Node").strip()

    if not email or not password:
        print("[DIRECT] ERROR: HNY_EMAIL or HNY_PASS environment variables are missing.")
        node_state["last_log"] = "Missing HNY_EMAIL / HNY_PASS"
        while True:
            time.sleep(30)

    bin_path = find_honeygain_binary()
    if not bin_path:
        print("[DIRECT] ERROR: Honeygain binary not found in container.")
        node_state["last_log"] = "Binary honeygain missing"
        while True:
            time.sleep(30)

    cmd = [
        bin_path,
        "-tou-accept",
        "-email", email,
        "-pass", password,
        "-device", device
    ]

    print("==================================================")
    print(" Launching Honeygain directly on Render Native IP")
    print(f" Target binary: {bin_path}")
    print(f" Device name:   {device}")
    print("==================================================")

    while True:
        try:
            node_state["honeygain_running"] = True
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in proc.stdout:
                clean = line.strip()
                print(f"[HG-DIRECT] {clean}")
                node_state["last_log"] = clean

            proc.wait()
            node_state["honeygain_running"] = False
            node_state["restarts"] += 1
            print(f"[DIRECT] Process exited with code {proc.returncode}. Restarting in 15 seconds...")
            time.sleep(15)
        except Exception as e:
            print(f"[DIRECT] Execution error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    # 1. Start HTTP health check server for Render
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    print(f"[SERVER] Health check server running on 0.0.0.0:{PORT}")

    # 2. Run Honeygain directly
    run_direct_honeygain()
