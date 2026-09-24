import os
import sys
import time
import shutil
import subprocess
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 10000))
TOKEN = os.environ.get("EARNFM_TOKEN", "").strip()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"active","service":"earnfm-node"}')
    
    def log_message(self, format, *args):
        pass

def run_server():
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    print(f"[HTTP] Health check server listening on port {PORT}")
    httpd.serve_forever()

def find_client_binary():
    # Log files in /app for debugging visibility
    if os.path.isdir("/app"):
        try:
            files = os.listdir("/app")
            print(f"[DEBUG] Files in /app: {files}")
        except Exception as e:
            print(f"[DEBUG] Could not list /app: {e}")

    candidates = [
        "/app/earnfm_example",
        "/app/main",
        "/usr/local/bin/earnfm",
        shutil.which("earnfm_example"),
        shutil.which("earnfm")
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            try:
                os.chmod(c, 0o755)
            except Exception:
                pass
            return c
    
    # Fallback search inside /app
    if os.path.isdir("/app"):
        for fname in os.listdir("/app"):
            fpath = os.path.join("/app", fname)
            if os.path.isfile(fpath) and not fname.endswith(".py"):
                try:
                    os.chmod(fpath, 0o755)
                except Exception:
                    pass
                return fpath

    return "/app/earnfm_example"

def earnfm_daemon():
    if not TOKEN:
        print("[EARNFM] WARNING: EARNFM_TOKEN is not set!")
        print("[EARNFM] Please add EARNFM_TOKEN to your Render Environment Variables.")
        while True:
            time.sleep(30)
            
    binary = find_client_binary()
    print(f"[EARNFM] Launching client binary: {binary}")
    
    env = os.environ.copy()
    env["EARNFM_TOKEN"] = TOKEN

    while True:
        try:
            print("[EARNFM] Process starting...")
            proc = subprocess.Popen(
                [binary],
                env=env,
                stdout=sys.stdout,
                stderr=sys.stderr
            )
            ret = proc.wait()
            print(f"[EARNFM] Process exited with code {ret}. Restarting in 10s...")
        except Exception as e:
            print(f"[EARNFM] Execution error: {e}")
        time.sleep(10)

if __name__ == '__main__':
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    earnfm_daemon()
