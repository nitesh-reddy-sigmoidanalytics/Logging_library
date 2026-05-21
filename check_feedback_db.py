import time
from azure.cosmos import CosmosClient
import os
import json
from dotenv import load_dotenv
import smartllmops

load_dotenv("/home/sigmoid/smart_factory_ai/finalsmartfactory-own/.env")

print("Initializing tracer...")
tracer = smartllmops.init(application_name="RAG_Test", environment="test")

print("Submitting feedback via SDK...")
tracer.log_feedback(
    trace_id="trace-test-container",
    thumb="up",
    session_id="session-container",
    user_id="user-container"
)

# Wait for background thread
time.sleep(3)

# 2. Query DB to verify
conn_str = os.getenv("COSMOS_CONN_WRITE")
client = CosmosClient.from_connection_string(conn_str)
db = client.get_database_client("llmops-data")
container = db.get_container_client("user_feedback")

print(f"Querying for feedback documents in 'user_feedback'...")
items = list(container.query_items(
    query="SELECT * FROM c WHERE c.trace_id = 'trace-test-container'",
    enable_cross_partition_query=True
))

if not items:
    print("❌ Failed! No items found in user_feedback container.")
else:
    for item in items:
        print(f"✅ Success! Found Doc ID: {item.get('id')} in user_feedback container.")
