# app.py - Cloudflare 1.1.1.1 WARP Tunnel & Honeygain Node Orchestrator
import os
import sys
import time
import shutil
import base64
import socket
import subprocess
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse

PORT = int(os.environ.get("PORT", 10000))
PROXY_PORT = 1080
WARP_ENDPOINT_DEFAULT = "engage.cloudflareclient.com:2408"
WARP_PEER_PUBKEY_DEFAULT = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="
APP_DIR = "/app"
WGCF_PROFILE_PATH = os.path.join(APP_DIR, "wgcf-profile.conf")
WIREPROXY_CONF_PATH = os.path.join(APP_DIR, "wireproxy.conf")

node_state = {
    "start_time": time.time(),
    "warp_connected": False,
    "warp_ip": "unknown",
    "warp_type": "none",
    "honeygain_running": False,
    "last_log": "Initializing system...",
    "restarts": 0
}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {
            "service": "Honeygain Cloudflare WARP Node",
            "mode": "Traffic and DNS (UDP) - 1.1.1.1 WARP",
            "warp_connected": node_state.get("warp_connected", False),
            "warp_ip": node_state.get("warp_ip", "unknown"),
            "warp_type": node_state.get("warp_type", "none"),
            "custom_proxy_enabled": bool(os.getenv("CUSTOM_PROXY")),
            "honeygain_running": node_state.get("honeygain_running", False),
            "device_name": os.getenv("DEVICE_NAME", "Render-Cloudflare-Warp-01"),
            "uptime_seconds": int(time.time() - node_state["start_time"]),
            "last_log": node_state.get("last_log", "")
        }
        self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        pass

def run_health_server():
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    httpd.serve_forever()

def setup_warp():
    """Configures WireGuard / Cloudflare WARP configuration file."""
    # 1. Check if user provided manual base64 config
    b64_conf = os.getenv("WARP_CONF_BASE64", "").strip()
    if b64_conf:
        print("[WARP-INIT] Found WARP_CONF_BASE64 environment variable. Decoding...")
        try:
            raw_conf = base64.b64decode(b64_conf).decode("utf-8")
            with open(WGCF_PROFILE_PATH, "w") as f:
                f.write(raw_conf)
            print(f"[WARP-INIT] Saved decoded WARP configuration to {WGCF_PROFILE_PATH}")
            return True
        except Exception as e:
            print(f"[WARP-INIT] Error decoding WARP_CONF_BASE64: {e}")

    # 2. Check if user provided WARP_PRIVATE_KEY
    priv_key = os.getenv("WARP_PRIVATE_KEY", "").strip()
    if priv_key:
        print("[WARP-INIT] Found WARP_PRIVATE_KEY environment variable. Generating profile...")
        address = os.getenv("WARP_ADDRESS", "172.16.0.2/32").strip()
        pubkey = os.getenv("WARP_PEER_PUBLIC_KEY", WARP_PEER_PUBKEY_DEFAULT).strip()
        endpoint = os.getenv("WARP_ENDPOINT", WARP_ENDPOINT_DEFAULT).strip()

        conf_content = f"""[Interface]
PrivateKey = {priv_key}
Address = {address}
DNS = 1.1.1.1

[Peer]
PublicKey = {pubkey}
Endpoint = {endpoint}
AllowedIPs = 0.0.0.0/0
"""
        with open(WGCF_PROFILE_PATH, "w") as f:
            f.write(conf_content)
        print(f"[WARP-INIT] Custom WARP profile created at {WGCF_PROFILE_PATH}")
        return True

    # 3. Check if profile already exists in working dir
    if os.path.exists(WGCF_PROFILE_PATH) and os.path.getsize(WGCF_PROFILE_PATH) > 0:
        print(f"[WARP-INIT] Existing configuration found at {WGCF_PROFILE_PATH}")
        return True

    # 4. Attempt automated registration using wgcf
    print("[WARP-INIT] Attempting automated WARP registration via wgcf...")
    try:
        reg_res = subprocess.run(
            ["wgcf", "register", "--accept-tos"],
            cwd=APP_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )
        if reg_res.returncode == 0:
            print("[WARP-INIT] Cloudflare WARP account registered successfully.")
            gen_res = subprocess.run(
                ["wgcf", "generate"],
                cwd=APP_DIR,
                capture_output=True,
                text=True,
                timeout=30
            )
            if gen_res.returncode == 0 and os.path.exists(WGCF_PROFILE_PATH):
                print("[WARP-INIT] wgcf WireGuard profile generated successfully.")
                return True
            else:
                err_msg = gen_res.stderr or gen_res.stdout
                print(f"[WARP-INIT] Failed to generate wgcf profile: {err_msg}")
        else:
            err_msg = reg_res.stderr or reg_res.stdout
            print(f"[WARP-INIT] wgcf register failed (code {reg_res.returncode}): {err_msg}")
    except Exception as e:
        print(f"[WARP-INIT] Auto-registration encountered exception: {e}")

    print("[WARP-INIT] Notice: Automated registration was rate-limited or blocked by Cloudflare API.")
    print("[WARP-INIT] You can run 'python register_warp.py' on your local computer,")
    print("[WARP-INIT] then copy WARP_PRIVATE_KEY or WARP_CONF_BASE64 into the Render dashboard.")
    return False

def build_wireproxy_conf():
    """Generates wireproxy.conf from the WireGuard profile, ensuring proper IPv4 routing and SOCKS5 proxy."""
    if not os.path.exists(WGCF_PROFILE_PATH):
        raise FileNotFoundError(f"Missing {WGCF_PROFILE_PATH}")

    with open(WGCF_PROFILE_PATH, "r") as f:
        raw_conf = f.read()

    clean_lines = []
    for line in raw_conf.splitlines():
        line_s = line.strip()
        if not line_s or line_s.startswith("#"):
            continue
        if line_s.startswith("["):
            clean_lines.append(line_s)
            continue
        if "=" in line_s:
            key, val = [x.strip() for x in line_s.split("=", 1)]
            if key == "Address":
                ipv4_parts = [p.strip() for p in val.split(",") if ":" not in p]
                val = ipv4_parts[0] if ipv4_parts else "172.16.0.2/32"
                clean_lines.append(f"Address = {val}")
            elif key == "AllowedIPs":
                clean_lines.append("AllowedIPs = 0.0.0.0/0")
            elif key == "DNS":
                clean_lines.append("DNS = 1.1.1.1")
            elif key == "Endpoint":
                clean_lines.append(f"Endpoint = {val}")
            else:
                clean_lines.append(f"{key} = {val}")

    proxy_section = f"""
[Socks5]
BindAddress = 127.0.0.1:{PROXY_PORT}
"""
    with open(WIREPROXY_CONF_PATH, "w") as f:
        f.write("\n".join(clean_lines) + proxy_section)

    print(f"[WIREPROXY] wireproxy.conf created successfully at {WIREPROXY_CONF_PATH}")

def start_wireproxy():
    """Launches wireproxy daemon in userspace and verifies the Cloudflare WARP tunnel."""
    build_wireproxy_conf()
    print("[WIREPROXY] Starting wireproxy daemon (Userspace WireGuard UDP tunnel)...")
    proc = subprocess.Popen(
        ["wireproxy", "-c", WIREPROXY_CONF_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    def log_stream():
        for line in proc.stdout:
            print(f"[WIREPROXY] {line.strip()}")

    Thread(target=log_stream, daemon=True).start()

    # Wait for SOCKS5 proxy to listen
    print(f"[WIREPROXY] Waiting for SOCKS5 port {PROXY_PORT}...")
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", PROXY_PORT), timeout=1):
                print(f"[WIREPROXY] SOCKS5 proxy is listening on 127.0.0.1:{PROXY_PORT}!")
                break
        except (socket.error, ConnectionRefusedError):
            time.sleep(1)
    else:
        print("[WIREPROXY] SOCKS5 proxy port failed to open within 30s.")
        return proc, False

    # Verify connection through Cloudflare trace
    print("[WIREPROXY] Testing connection through Cloudflare WARP tunnel...")
    for attempt in range(6):
        try:
            res = subprocess.run(
                [
                    "curl", "-s",
                    "--socks5-hostname", f"127.0.0.1:{PROXY_PORT}",
                    "--max-time", "8",
                    "https://cloudflare.com/cdn-cgi/trace"
                ],
                capture_output=True,
                text=True
            )
            output = res.stdout.strip()
            if "warp=" in output:
                warp_val = "off"
                ip_val = "unknown"
                for line in output.splitlines():
                    if line.startswith("warp="):
                        warp_val = line.split("=")[1].strip()
                    if line.startswith("ip="):
                        ip_val = line.split("=")[1].strip()

                if warp_val in ("on", "plus"):
                    node_state["warp_connected"] = True
                    node_state["warp_ip"] = ip_val
                    node_state["warp_type"] = warp_val
                    print(f"[WIREPROXY] Tunnel confirmed! WARP: {warp_val}, Exit IP: {ip_val}")
                    return proc, True
                else:
                    print(f"[WIREPROXY] Trace responded but warp={warp_val}")
        except Exception as e:
            print(f"[WIREPROXY] Tunnel verification attempt {attempt+1} failed: {e}")
        time.sleep(2)

    return proc, False

def parse_custom_proxy(proxy_str):
    """
    Parses a proxy string into proxychains format:
    Supported formats:
      - socks5://user:pass@host:port
      - http://user:pass@host:port
      - socks5 host port user pass
      - http host port
    """
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None

    if "://" in proxy_str:
        try:
            parsed = urlparse(proxy_str)
            proto = parsed.scheme.lower()
            if proto not in ("socks5", "socks4", "http"):
                proto = "socks5"
            host = parsed.hostname
            port = parsed.port or (1080 if "socks" in proto else 8080)
            user = parsed.username or ""
            pwd = parsed.password or ""
            if user and pwd:
                return f"{proto} {host} {port} {user} {pwd}"
            return f"{proto} {host} {port}"
        except Exception as e:
            print(f"[PROXYCHAINS] Error parsing proxy URL: {e}")
            return None
    else:
        # Already in proxychains space-delimited format
        return proxy_str

def setup_proxychains():
    """Configures proxychains to tunnel all outgoing Honeygain traffic through wireproxy (and optional chained residential proxy)."""
    proxy_entries = [f"socks5 127.0.0.1 {PROXY_PORT}"]

    custom_proxy = os.getenv("CUSTOM_PROXY", "").strip()
    if custom_proxy:
        parsed_custom = parse_custom_proxy(custom_proxy)
        if parsed_custom:
            proxy_entries.append(parsed_custom)
            print(f"[PROXYCHAINS] Chaining custom proxy: {parsed_custom.split()[0]} {parsed_custom.split()[1]}")

    config_body = f"""strict_chain
proxy_dns
remote_dns_subnet 224
tcp_read_time_out 15000
tcp_connect_time_out 8000

[ProxyList]
""" + "\n".join(proxy_entries) + "\n"

    for path in ["/etc/proxychains.conf", "/etc/proxychains4.conf"]:
        try:
            with open(path, "w") as f:
                f.write(config_body)
            print(f"[PROXYCHAINS] Written proxy configuration to {path}")
        except Exception as e:
            pass

def find_honeygain_binary():
    """Locates the Honeygain executable inside the container."""
    candidate = shutil.which("honeygain")
    if candidate:
        return candidate
    for p in ["/app/honeygain", "/honeygain", "/bin/honeygain", "/usr/local/bin/honeygain"]:
        if os.path.exists(p):
            return p
    return None

def run_honeygain():
    """Executes the Honeygain client routed through proxychains and Cloudflare WARP."""
    email = os.getenv("HNY_EMAIL", "").strip()
    password = os.getenv("HNY_PASS", "").strip()
    device = os.getenv("DEVICE_NAME", "Render-Cloudflare-Warp-01").strip()

    if not email or not password:
        print("[HONEYGAIN] WARNING: HNY_EMAIL or HNY_PASS environment variables are missing.")
        print("[HONEYGAIN] Go to Render Dashboard -> Environment Variables to set HNY_EMAIL and HNY_PASS.")
        node_state["last_log"] = "Waiting for HNY_EMAIL and HNY_PASS configuration"
        while True:
            time.sleep(30)

    bin_path = find_honeygain_binary()
    if not bin_path:
        print("[HONEYGAIN] ERROR: Unable to locate honeygain binary in container.")
        node_state["last_log"] = "honeygain binary not found"
        while True:
            time.sleep(30)

    proxychains_bin = "proxychains4" if shutil.which("proxychains4") else "proxychains"
    print(f"[HONEYGAIN] Using proxy wrapper: {proxychains_bin}")
    print(f"[HONEYGAIN] Executable path: {bin_path}")
    print(f"[HONEYGAIN] Device Name: {device}")
    print(f"[HONEYGAIN] Email: {email[:3]}***@{email.split('@')[-1] if '@' in email else '***'}")

    cmd = [
        proxychains_bin, "-q",
        bin_path,
        "-tou-accept",
        "-email", email,
        "-pass", password,
        "-device", device
    ]

    while True:
        try:
            print("[HONEYGAIN] Starting Honeygain daemon over 1.1.1.1 WARP...")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            node_state["honeygain_running"] = True
            node_state["last_log"] = "Honeygain daemon active"

            for line in proc.stdout:
                clean_line = line.strip()
                print(f"[HG-NODE] {clean_line}")
                node_state["last_log"] = clean_line

            proc.wait()
            node_state["honeygain_running"] = False
            node_state["restarts"] += 1
            print(f"[HONEYGAIN] Process exited (code {proc.returncode}). Restarting in 10s...")
            time.sleep(10)
        except Exception as e:
            print(f"[HONEYGAIN] Exception during execution: {e}")
            node_state["honeygain_running"] = False
            time.sleep(15)

if __name__ == "__main__":
    node_state["start_time"] = time.time()
    print("==================================================")
    print(" Honeygain + Cloudflare 1.1.1.1 WARP (Render Node)")
    print(" Mode: Traffic and DNS (UDP)")
    print("==================================================")

    # 1. Boot HTTP Health Check Server
    http_thread = Thread(target=run_health_server, daemon=True)
    http_thread.start()
    print(f"[SERVER] Health check web server running on 0.0.0.0:{PORT}")

    # 2. Establish Cloudflare WARP Profile
    warp_configured = False
    retry_attempt = 0
    while not warp_configured:
        warp_configured = setup_warp()
        if not warp_configured:
            retry_attempt += 1
            node_state["last_log"] = f"Waiting for WARP setup (attempt #{retry_attempt})"
            print(f"[SERVER] Retrying WARP setup in 20 seconds (attempt #{retry_attempt})...")
            time.sleep(20)

    # 3. Start wireproxy daemon and loop until tunnel is confirmed active!
    wireproxy_proc = None
    tunnel_active = False
    attempt = 0
    while not tunnel_active:
        attempt += 1
        print(f"[INIT] Establishing Cloudflare WARP tunnel (attempt #{attempt})...")
        if wireproxy_proc and wireproxy_proc.poll() is None:
            wireproxy_proc.terminate()
            time.sleep(2)

        wireproxy_proc, tunnel_active = start_wireproxy()
        if not tunnel_active:
            node_state["last_log"] = f"WARP connecting... (attempt #{attempt})"
            print(f"[INIT] WARP tunnel not verified yet. Retrying in 10s...")
            time.sleep(10)

    print("[INIT] Cloudflare WARP verified and active!")

    # 4. Configure proxychains (WARP + optional CUSTOM_PROXY chain)
    setup_proxychains()

    # 5. Launch Honeygain Daemon (only starts after WARP is verified!)
    run_honeygain()
