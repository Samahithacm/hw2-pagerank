#!/usr/bin/env python3
import http.server
import socketserver
import urllib.request
import sys

PORT = 8080

def get_zone():
    """Fetch zone from GCP metadata server. Returns e.g. 'us-central1-a'."""
    try:
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/zone",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            full = resp.read().decode().strip()
            # Format is 'projects/NNN/zones/us-central1-a'
            return full.split("/")[-1]
    except Exception as e:
        print(f"Could not fetch zone: {e}", file=sys.stderr)
        return "unknown"

ZONE = get_zone()
print(f"Server starting in zone: {ZONE}", file=sys.stderr)

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("X-Zone", ZONE)
        self.end_headers()
        self.wfile.write(f"Hello from zone {ZONE}\n".encode())

    def log_message(self, format, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving on port {PORT}", file=sys.stderr)
    httpd.serve_forever()