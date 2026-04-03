import functions_framework
from googleapiclient import discovery

PROJECT_ID = "constant-idiom-485622-f3"
INSTANCE_NAME = "hw5-sql-instance"

@functions_framework.http
def stop_sql(request):
    service = discovery.build('sqladmin', 'v1beta4')
    instance = service.instances().get(
        project=PROJECT_ID, instance=INSTANCE_NAME
    ).execute()

    state = instance.get("state", "")
    if state == "RUNNABLE":
        service.instances().patch(
            project=PROJECT_ID, instance=INSTANCE_NAME,
            body={"settings": {"activationPolicy": "NEVER"}}
        ).execute()
        msg = f"Stopped {INSTANCE_NAME}"
    else:
        msg = f"Already stopped (state: {state})"

    print(msg)
    return msg
