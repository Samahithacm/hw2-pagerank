#!/usr/bin/env python3
import socket
import json

HOST = "0.0.0.0"
PORT = 9090

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Reporter listening on port {PORT}", flush=True)
    while True:
        conn, addr = s.accept()
        with conn:
            data = conn.recv(1024).decode()
            try:
                info = json.loads(data)
                print(f"[FORBIDDEN] IP: {info['ip']} | Country: {info['country']} | Path: {info['path']}", flush=True)
            except Exception:
                print(f"[FORBIDDEN] Raw message: {data}", flush=True)
