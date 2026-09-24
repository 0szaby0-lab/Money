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
        pass # Ne logoljon minden webes kérést, hogy spóroljon a lemezműveletekkel

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
    
    # Megkeressük a hivatalos Honeygain bináris pontos helyét a konténerben
    bin_path = shutil.which("honeygain")
    if not bin_path:
        for path in ["/app/honeygain", "/honeygain", "./honeygain"]:
            if os.path.exists(path):
                bin_path = path
                break
    
    proc = subprocess.Popen([
        bin_path, 
        "-tou-accept", 
        "-email", os.getenv("HNY_EMAIL"), 
        "-pass", os.getenv("HNY_PASS"), 
        "-device", os.getenv("DEVICE_NAME")
    ])

    while True:
        # Ha új hónap kezdődik, nullázzuk a számlálót
        if datetime.now().month != current_month:
            current_month = datetime.now().month
            start_tx = get_tx_bytes()
            if proc.poll() is not None:
                proc = subprocess.Popen([
                    bin_path, 
                    "-tou-accept", 
                    "-email", os.getenv("HNY_EMAIL"), 
                    "-pass", os.getenv("HNY_PASS"), 
                    "-device", os.getenv("DEVICE_NAME")
                ])

        # Adatforgalom ellenőrzése
        current_tx = get_tx_bytes() - start_tx
        if current_tx >= LIMIT_BYTES:
            if proc.poll() is None:
                proc.terminate()
                print("99 GB limit reached. Halting operations until next month.")
        
        time.sleep(300) # 5 percenként ellenőriz

if __name__ == '__main__':
    # Web szerver indítása külön szálon (hogy a Render lássa, a szolgáltatás fut)
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Fő Honeygain folyamat indítása
    honeygain_daemon()
