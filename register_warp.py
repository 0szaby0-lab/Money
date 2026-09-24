#!/usr/bin/env python3
"""
register_warp.py
Helper utility to generate Cloudflare WARP credentials and output them
as ready-to-paste environment variables for Render.com.
"""
import os
import sys
import subprocess
import urllib.request
import base64
import platform

def main():
    print("=" * 60)
    print(" Cloudflare 1.1.1.1 WARP Credentials Generator for Render")
    print("=" * 60)

    is_windows = platform.system() == "Windows"
    binary_name = "wgcf.exe" if is_windows else "wgcf"

    # Check if wgcf is in PATH or current dir
    wgcf_cmd = None
    if shutil_which := getattr(os, "which", None):
        import shutil
        wgcf_cmd = shutil.which("wgcf")

    if not wgcf_cmd and os.path.exists(binary_name):
        wgcf_cmd = os.path.abspath(binary_name)

    if not wgcf_cmd:
        print("[+] wgcf not found locally. Downloading latest release...")
        if is_windows:
            url = "https://github.com/ViRb3/wgcf/releases/download/v2.3.0/wgcf_2.3.0_windows_amd64.exe"
        elif platform.system() == "Darwin":
            url = "https://github.com/ViRb3/wgcf/releases/download/v2.3.0/wgcf_2.3.0_darwin_amd64"
        else:
            url = "https://github.com/ViRb3/wgcf/releases/download/v2.3.0/wgcf_2.3.0_linux_amd64"

        print(f"[+] Fetching from {url}...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(binary_name, "wb") as f:
                f.write(resp.read())
            if not is_windows:
                os.chmod(binary_name, 0o755)
            wgcf_cmd = os.path.abspath(binary_name)
            print("[+] Download complete.")
        except Exception as e:
            print(f"[-] Failed to download wgcf: {e}")
            sys.exit(1)

    print("[+] Registering new Cloudflare WARP device...")
    subprocess.run([wgcf_cmd, "register", "--accept-tos"], check=True)

    print("[+] Generating WireGuard profile (wgcf-profile.conf)...")
    subprocess.run([wgcf_cmd, "generate"], check=True)

    conf_file = "wgcf-profile.conf"
    if not os.path.exists(conf_file):
        print("[-] Could not find generated wgcf-profile.conf!")
        sys.exit(1)

    with open(conf_file, "r") as f:
        conf_data = f.read()

    b64_val = base64.b64encode(conf_data.encode("utf-8")).decode("utf-8")

    # Extract PrivateKey and Address
    priv_key = ""
    address = "172.16.0.2/32"
    for line in conf_data.splitlines():
        if line.strip().startswith("PrivateKey"):
            priv_key = line.split("=")[1].strip()
        if line.strip().startswith("Address") and "172." in line:
            address = line.split("=")[1].strip()

    print("\n" + "=" * 60)
    print("SUCCESS! Copy and paste these into your Render Environment:")
    print("=" * 60)
    print(f"\nOption 1 (Full Config Base64):\nWARP_CONF_BASE64={b64_val}\n")
    print(f"Option 2 (Key Variables):\nWARP_PRIVATE_KEY={priv_key}\nWARP_ADDRESS={address}\n")
    print("=" * 60)

if __name__ == "__main__":
    main()
