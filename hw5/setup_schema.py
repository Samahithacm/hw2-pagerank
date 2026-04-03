#!/usr/bin/env python3
import pymysql
import sys

DB_HOST = sys.argv[1] if len(sys.argv) > 1 else "10.6.0.3"
DB_USER = "root"
DB_PASS = "cs528hw5pass"
DB_NAME = "hw5db"

def create_schema():
    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            country VARCHAR(100),
            client_ip VARCHAR(45),
            gender VARCHAR(10),
            age VARCHAR(10),
            income VARCHAR(20),
            is_banned BOOLEAN,
            time_of_day VARCHAR(20),
            requested_file VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS failed_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            time_of_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            requested_file VARCHAR(255),
            error_code INT
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Schema created successfully.")

if __name__ == "__main__":
    create_schema()
