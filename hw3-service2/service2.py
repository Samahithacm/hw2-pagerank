from google.cloud import pubsub_v1, storage
import json
from datetime import datetime

PROJECT_ID = "constant-idiom-485622-f3"
SUBSCRIPTION_ID = "forbidden-requests-sub"
BUCKET_NAME = "bu-cs528-mahicm13"
LOG_FOLDER = "forbidden-logs"

def append_to_bucket(message_data):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    log_filename = LOG_FOLDER + "/forbidden_log.txt"
    blob = bucket.blob(log_filename)
    try:
        existing = blob.download_as_text()
    except Exception:
        existing = ""
    timestamp = datetime.utcnow().isoformat()
    new_entry = "[" + timestamp + "] " + message_data + "\n"
    blob.upload_from_string(existing + new_entry)
    print("[LOGGED TO BUCKET]: " + new_entry.strip())

def callback(message):
    data = message.data.decode("utf-8")
    print("\n[FORBIDDEN REQUEST RECEIVED]: " + data)
    append_to_bucket(data)
    message.ack()

def main():
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
    print("Service 2 is running. Listening on: " + subscription_path)
    print("Waiting for forbidden country requests...\n")
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    try:
        streaming_pull_future.result()
    except KeyboardInterrupt:
        streaming_pull_future.cancel()
        print("\nService 2 stopped.")

if __name__ == "__main__":
    main()
