#!/usr/bin/env python3
"""
HW9 web server - runs inside a GKE pod.
Ported from HW4. Adds:
  - Reads BUCKET_NAME and REPORTER_HOST from environment variables
    (set via Kubernetes Deployment env)
  - Optional X-Test-Country header so we can demo the forbidden flow
    even though the load-test client lives on a US-region VM.
"""

import http.server
import socketserver
import requests
import json
import socket
import os
from google.cloud import storage, logging as gcloud_logging

PORT          = 8080
BUCKET_NAME   = os.environ.get("BUCKET_NAME", "bu-cs528-mahicm13")
REPORTER_HOST = os.environ.get("REPORTER_HOST", "")
REPORTER_PORT = int(os.environ.get("REPORTER_PORT", "9090"))

BANNED_COUNTRIES = {"KP", "IR", "CU", "MM", "IQ", "LY", "SD", "ZW", "SY"}

logging_client = gcloud_logging.Client()
logger = logging_client.logger("hw9-webserver")
storage_client = storage.Client()


def get_country_from_ip(ip):
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        return resp.json().get("countryCode", "")
    except Exception:
        return ""


def notify_reporter(ip, country, path):
    if not REPORTER_HOST:
        print("REPORTER_HOST not set; skipping notify", flush=True)
        return
    try:
        msg = json.dumps({"ip": ip, "country": country, "path": path})
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect((REPORTER_HOST, REPORTER_PORT))
            s.sendall(msg.encode())
    except Exception as e:
        print(f"Could not notify reporter: {e}", flush=True)


class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        client_ip = self.client_address[0]
        path = self.path.lstrip("/")

        # Test override: lets us demo banned-country handling without
        # actually originating a request from North Korea.
        test_country = self.headers.get("X-Test-Country", "").upper()
        country = test_country if test_country else get_country_from_ip(client_ip)

        if country in BANNED_COUNTRIES:
            logger.log_struct(
                {"message": f"Forbidden request from {country}",
                 "ip": client_ip, "path": path},
                severity="CRITICAL",
            )
            notify_reporter(client_ip, country, path)
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"403 Forbidden - Export regulations apply")
            return

        try:
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(path)
            if not blob.exists():
                raise FileNotFoundError
            content = blob.download_as_bytes()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(content)

        except FileNotFoundError:
            logger.log_struct(
                {"message": f"File not found: {path}", "ip": client_ip},
                severity="WARNING",
            )
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def _send_501(self):
        client_ip = self.client_address[0]
        logger.log_struct(
            {"message": f"Unsupported method: {self.command}",
             "ip": client_ip, "path": self.path},
            severity="WARNING",
        )
        self.send_response(501)
        self.end_headers()
        self.wfile.write(b"501 Not Implemented")

    do_POST    = _send_501
    do_PUT     = _send_501
    do_DELETE  = _send_501
    do_HEAD    = _send_501
    do_OPTIONS = _send_501
    do_PATCH   = _send_501
    do_CONNECT = _send_501
    do_TRACE   = _send_501

    def log_message(self, format, *args):
        # Silence default access log; Cloud Logging handles structured logs.
        pass


# allow_reuse_address speeds up pod restarts
class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with ReusableTCPServer(("", PORT), Handler) as httpd:
        print(f"HW9 webserver listening on :{PORT} | bucket={BUCKET_NAME} | reporter={REPORTER_HOST}:{REPORTER_PORT}", flush=True)
        httpd.serve_forever()
