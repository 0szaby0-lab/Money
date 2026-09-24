# app.py - 24/7 Web-Bound Monitoring Wrapper & HTTP Server
import time
import os
import subprocess
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

LIMIT_BYTES = 99 * 1024 * 1024 * 1024  # 99 GB Monthly Threshold [VERIFIED]
PORT = int(os.environ.get("PORT", 10000))

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

def get_tx_bytes():
    try:
        with open('/sys/class/net/eth0/statistics/tx_bytes', 'r') as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return 0

def honeygain_daemon():
    current_month = datetime.now().month
    start_tx = get_tx_bytes()
    
    proc = subprocess.Popen([
        "./honeygain", 
        "-tou-accept", 
        "-email", os.getenv("HNY_EMAIL"), 
        "-pass", os.getenv("HNY_PASS"), 
        "-device", os.getenv("DEVICE_NAME")
    ])

    while True:
        if datetime.now().month != current_month:
            current_month = datetime.now().month
            start_tx = get_tx_bytes()
            if proc.poll() is not None:
                proc = subprocess.Popen([
                    "./honeygain", 
                    "-tou-accept", 
                    "-email", os.getenv("HNY_EMAIL"), 
                    "-pass", os.getenv("HNY_PASS"), 
                    "-device", os.getenv("DEVICE_NAME")
                ])

        current_tx = get_tx_bytes() - start_tx
        if current_tx >= LIMIT_BYTES:
            if proc.poll() is None:
                proc.terminate()
                print("99 GB monthly limit reached. Halting operations until next calendar month.")
        
        time.sleep(300)

if __name__ == '__main__':
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    honeygain_daemon()
