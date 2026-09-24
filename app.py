import os
import sys
import time
import json
import glob
import shutil
import subprocess
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

state_lock = Lock()
app_states = {}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        with state_lock:
            body = json.dumps({
                "service": "Multi-App Passive Income Node",
                "apps": dict(app_states)
            }).encode()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass

def run_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    print(f"[HTTP] Render health check server running on port {PORT}")
    server.serve_forever()

def find_binary(search_dirs, names):
    """Search for an executable binary by name in given directories."""
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            for name in names:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    os.chmod(path, 0o755)
                    return path
        # Fallback: find any executable
        for root, dirs, files in os.walk(d):
            for f in files:
                fpath = os.path.join(root, f)
                if os.path.isfile(fpath) and os.access(fpath, os.X_OK) and not f.endswith(('.py', '.sh', '.conf', '.txt', '.md', '.json', '.yml', '.yaml')):
                    st = os.stat(fpath)
                    if st.st_size > 50000:  # Real binary, not a script
                        return fpath
    return None

def list_stage_contents(label, path):
    """Debug: list files in a stage directory."""
    if not os.path.isdir(path):
        print(f"[DEBUG] {label}: directory {path} does not exist")
        return
    for root, dirs, files in os.walk(path):
        for f in files:
            fpath = os.path.join(root, f)
            try:
                sz = os.path.getsize(fpath)
                ex = os.access(fpath, os.X_OK)
                if sz > 10000:
                    print(f"[DEBUG] {label}: {fpath} ({sz} bytes, exec={ex})")
            except:
                pass

def run_earnfm():
    """Run EarnFM client in a loop."""
    if not EARNFM_TOKEN:
        print("[EARNFM] Skipped: EARNFM_TOKEN not set")
        with state_lock:
            app_states["earnfm"] = "Skipped (no token)"
        return

    list_stage_contents("EARNFM", "/app/earnfm")
    binary = find_binary(["/app/earnfm"], ["earnfm_example", "main", "earnfm"])
    if not binary:
        print("[EARNFM] ERROR: Binary not found in /app/earnfm/")
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
            print("[EARNFM] Starting process...")
            proc = subprocess.Popen(
                [binary], env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            for line in proc.stdout:
                print(f"[EARNFM] {line.strip()}")
            ret = proc.wait()
            print(f"[EARNFM] Exited with code {ret}. Restarting in 10s...")
        except Exception as e:
            print(f"[EARNFM] Error: {e}")
        with state_lock:
            app_states["earnfm"] = "Restarting..."
        time.sleep(10)

def run_traffmonetizer():
    """Run Traffmonetizer client in a loop."""
    if not TM_TOKEN:
        print("[TRAFFMON] Skipped: TM_TOKEN not set")
        with state_lock:
            app_states["traffmonetizer"] = "Skipped (no token)"
        return

    list_stage_contents("TRAFFMON", "/app/tm-stage")
    binary = find_binary(["/app/tm-stage"], ["Cli", "cli", "traffmonetizer", "tm"])
    if not binary:
        # Try searching more broadly
        for d in ["/app/tm-stage/usr", "/app/tm-stage/bin", "/app/tm-stage/opt"]:
            binary = find_binary([d], ["Cli", "cli"])
            if binary:
                break
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
            print("[TRAFFMON] Starting process...")
            proc = subprocess.Popen(
                [binary, "start", "accept", "--token", TM_TOKEN],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            for line in proc.stdout:
                print(f"[TRAFFMON] {line.strip()}")
            ret = proc.wait()
            print(f"[TRAFFMON] Exited with code {ret}. Restarting in 10s...")
        except Exception as e:
            print(f"[TRAFFMON] Error: {e}")
        with state_lock:
            app_states["traffmonetizer"] = "Restarting..."
        time.sleep(10)

def run_repocket():
    """Run Repocket client in a loop."""
    if not RP_EMAIL or not RP_API_KEY:
        print("[REPOCKET] Skipped: RP_EMAIL or RP_API_KEY not set")
        with state_lock:
            app_states["repocket"] = "Skipped (no credentials)"
        return

    list_stage_contents("REPOCKET", "/app/rp-stage")
    binary = find_binary(["/app/rp-stage"], ["repocket", "rp"])
    if not binary:
        for d in ["/app/rp-stage/usr", "/app/rp-stage/bin", "/app/rp-stage/opt"]:
            binary = find_binary([d], ["repocket", "rp"])
            if binary:
                break
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
            print("[REPOCKET] Starting process...")
            proc = subprocess.Popen(
                [binary], env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            for line in proc.stdout:
                print(f"[REPOCKET] {line.strip()}")
            ret = proc.wait()
            print(f"[REPOCKET] Exited with code {ret}. Restarting in 10s...")
        except Exception as e:
            print(f"[REPOCKET] Error: {e}")
        with state_lock:
            app_states["repocket"] = "Restarting..."
        time.sleep(10)

if __name__ == "__main__":
    print("=========================================================")
    print(" Multi-App Passive Income Node for Render.com Free Tier")
    print(" EarnFM + Traffmonetizer + Repocket")
    print(" All accept datacenter IPs - no proxy needed!")
    print("=========================================================")

    # 1. HTTP health check for Render
    server_t = Thread(target=run_health_server, daemon=True)
    server_t.start()

    # 2. Launch all configured apps in parallel
    threads = []

    if EARNFM_TOKEN:
        t = Thread(target=run_earnfm, daemon=True)
        t.start()
        threads.append(("EarnFM", t))

    if TM_TOKEN:
        t = Thread(target=run_traffmonetizer, daemon=True)
        t.start()
        threads.append(("Traffmonetizer", t))

    if RP_EMAIL and RP_API_KEY:
        t = Thread(target=run_repocket, daemon=True)
        t.start()
        threads.append(("Repocket", t))

    active = [name for name, _ in threads]
    if active:
        print(f"[SYSTEM] Active apps: {', '.join(active)}")
    else:
        print("[SYSTEM] WARNING: No app tokens configured!")
        print("[SYSTEM] Set environment variables in Render:")
        print("[SYSTEM]   EARNFM_TOKEN  - from https://app.earn.fm/")
        print("[SYSTEM]   TM_TOKEN      - from https://app.traffmonetizer.com/")
        print("[SYSTEM]   RP_EMAIL + RP_API_KEY - from https://app.repocket.com/")

    # Keep main thread alive
    while True:
        time.sleep(60)
