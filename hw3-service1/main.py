import functions_framework
from google.cloud import storage, pubsub_v1
import json
import logging

BUCKET_NAME = "bu-cs528-mahicm13"
PROJECT_ID = "constant-idiom-485622-f3"
TOPIC_ID = "forbidden-requests"

FORBIDDEN_COUNTRIES = {
    "north korea", "iran", "cuba", "myanmar",
    "iraq", "libya", "sudan", "zimbabwe", "syria"
}

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH",
    "Access-Control-Allow-Headers": "X-country, Content-Type"
}

@functions_framework.http
def handle_request(request):

    if request.method == "OPTIONS":
        return ("", 204, CORS_HEADERS)

    if request.method != "GET":
        log_entry = {
            "severity": "ERROR",
            "message": "501 - Unsupported method: " + request.method,
            "method": request.method,
            "path": request.path
        }
        logging.error(json.dumps(log_entry))
        print(json.dumps(log_entry))
        return ("Not Implemented", 501, CORS_HEADERS)

    country = request.headers.get("X-country", "").strip().lower()
    if country in FORBIDDEN_COUNTRIES:
        log_entry = {
            "severity": "ERROR",
            "message": "400 - Forbidden country: " + country,
            "country": country,
            "path": request.path
        }
        logging.error(json.dumps(log_entry))
        print(json.dumps(log_entry))
        _publish_forbidden(country, request.path)
        return ("Permission Denied - Forbidden Country", 400, CORS_HEADERS)

    filename = request.path.lstrip("/")
    if not filename:
        return ("Please provide a filename", 400, CORS_HEADERS)

    full_path = filename
    print("DEBUG full_path=" + full_path)

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(full_path)
        exists = blob.exists()
        print("DEBUG exists=" + str(exists))
        if not exists:
            log_entry = {
                "severity": "ERROR",
                "message": "404 - File not found: " + full_path,
                "filename": full_path
            }
            logging.error(json.dumps(log_entry))
            print(json.dumps(log_entry))
            return ("File Not Found", 404, CORS_HEADERS)
        content = blob.download_as_text()
        return (content, 200, CORS_HEADERS)
    except Exception as e:
        print("DEBUG Exception: " + str(e))
        return ("Internal Server Error: " + str(e), 500, CORS_HEADERS)


def _publish_forbidden(country, path):
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        message = json.dumps({
            "country": country,
            "path": path,
            "event": "forbidden_request"
        }).encode("utf-8")
        publisher.publish(topic_path, message)
    except Exception as e:
        logging.error("Failed to publish: " + str(e))
