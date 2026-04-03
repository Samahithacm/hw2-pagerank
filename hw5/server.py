#!/usr/bin/env python3
import http.server
import socketserver
import json
import socket
import time
import pymysql
from google.cloud import storage

PORT = 8080
BUCKET_NAME = "bu-cs528-mahicm13"
REPORTER_HOST = "REPORTER_IP_PLACEHOLDER"
REPORTER_PORT = 9090

DB_HOST = "DB_IP_PLACEHOLDER"
DB_USER = "root"
DB_PASS = "DB_PASS_PLACEHOLDER"
DB_NAME = "hw5db"

BANNED_COUNTRIES = {
    "North Korea", "Iran", "Cuba", "Myanmar", "Iraq",
    "Libya", "Sudan", "Zimbabwe", "Syria"
}

storage_client = storage.Client(project="constant-idiom-485622-f3")

timing_data = {
    "header_extraction": [],
    "file_read": [],
    "send_response": [],
    "db_insert": []
}

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS,
        database=DB_NAME, autocommit=True
    )

def extract_headers(handler):
    start = time.perf_counter()
    headers = {
        "country": handler.headers.get("X-country", ""),
        "client_ip": handler.headers.get("X-client-IP", ""),
        "gender": handler.headers.get("X-gender", ""),
        "age": handler.headers.get("X-age", ""),
        "income": handler.headers.get("X-income", ""),
        "time_of_day": handler.headers.get("X-time", ""),
    }
    headers["is_banned"] = headers["country"] in BANNED_COUNTRIES
    headers["requested_file"] = handler.path.lstrip("/").replace("bu-cs528-mahicm13/", "", 1)
    elapsed = time.perf_counter() - start
    timing_data["header_extraction"].append(elapsed)
    return headers

def read_file_from_gcs(file_path):
    if not file_path or file_path.strip() == "":
        raise FileNotFoundError("Empty path")
    start = time.perf_counter()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_path)
    if not blob.exists():
        elapsed = time.perf_counter() - start
        timing_data["file_read"].append(elapsed)
        raise FileNotFoundError
    content = blob.download_as_bytes()
    elapsed = time.perf_counter() - start
    timing_data["file_read"].append(elapsed)
    return content

def send_response_to_client(handler, status_code, content):
    start = time.perf_counter()
    handler.send_response(status_code)
    handler.end_headers()
    handler.wfile.write(content)
    elapsed = time.perf_counter() - start
    timing_data["send_response"].append(elapsed)

def insert_into_db(headers, success=True, error_code=None):
    start = time.perf_counter()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if success:
            cursor.execute("""
                INSERT INTO requests
                (country, client_ip, gender, age, income, is_banned, time_of_day, requested_file)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                headers["country"], headers["client_ip"], headers["gender"],
                headers["age"], headers["income"], headers["is_banned"],
                headers["time_of_day"], headers["requested_file"]
            ))
        else:
            cursor.execute("""
                INSERT INTO failed_requests (requested_file, error_code)
                VALUES (%s, %s)
            """, (headers["requested_file"], error_code))
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"DB error: {e}")
    elapsed = time.perf_counter() - start
    timing_data["db_insert"].append(elapsed)

def notify_reporter(ip, country, path):
    try:
        msg = json.dumps({"ip": ip, "country": country, "path": path})
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((REPORTER_HOST, REPORTER_PORT))
            s.sendall(msg.encode())
    except Exception as e:
        print(f"Could not notify reporter: {e}")


class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        headers = extract_headers(self)

        if headers["is_banned"]:
            notify_reporter(headers["client_ip"], headers["country"], headers["requested_file"])
            send_response_to_client(self, 403, b"403 Forbidden")
            insert_into_db(headers, success=False, error_code=403)
            return

        try:
            content = read_file_from_gcs(headers["requested_file"])
        except FileNotFoundError:
            send_response_to_client(self, 404, b"404 Not Found")
            insert_into_db(headers, success=False, error_code=404)
            return

        send_response_to_client(self, 200, content)
        insert_into_db(headers, success=True)

    def _send_501(self):
        headers = extract_headers(self)
        send_response_to_client(self, 501, b"501 Not Implemented")
        insert_into_db(headers, success=False, error_code=501)

    do_POST = _send_501
    do_PUT = _send_501
    do_DELETE = _send_501
    do_HEAD = _send_501
    do_OPTIONS = _send_501
    do_PATCH = _send_501
    do_CONNECT = _send_501
    do_TRACE = _send_501

    def log_message(self, format, *args):
        pass


import atexit, signal

def print_timing_summary():
    print("\n" + "="*60)
    print("TIMING SUMMARY")
    print("="*60)
    for op, times in timing_data.items():
        if times:
            avg = sum(times) / len(times)
            print(f"{op}: count={len(times)}, avg={avg*1000:.4f}ms, "
                  f"min={min(times)*1000:.4f}ms, max={max(times)*1000:.4f}ms, "
                  f"total={sum(times):.4f}s")
    print("="*60)

atexit.register(print_timing_summary)

def signal_handler(sig, frame):
    print_timing_summary()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving on port {PORT}")
    httpd.serve_forever()
