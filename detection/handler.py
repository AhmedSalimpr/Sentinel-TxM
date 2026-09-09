"""
Sentinel-TxM — Serverless Detection Engine
=====================================================
AWS Lambda function triggered by Kinesis Data Streams.
Ingests transaction events, writes them to Amazon Neptune, and runs real-time Gremlin queries
to detect structuring and mule cycle typologies.
"""

import os
import json
import base64
import uuid
import datetime
from gremlin_python.driver import client, serializer
from gremlin_python.driver.protocol import GremlinServerError

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "localhost")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")
ALERTS_BUCKET = os.environ.get("ALERTS_BUCKET") # Optional: to save alerts

# Initialize Neptune Client (cached across Lambda invocations)
gremlin_client = None

def get_gremlin_client():
    global gremlin_client
    if gremlin_client is None:
        url = f"wss://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
        try:
            gremlin_client = client.Client(url, 'g', 
                                           message_serializer=serializer.GraphSONSerializersV3d0())
            print(f"Connected to Neptune at {url}")
        except Exception as e:
            print(f"Failed to connect to Neptune: {e}")
    return gremlin_client

def process_transaction(tx, g_client):
    """Upsert nodes and edge into Neptune"""
    sender_id = tx['sender_id']
    receiver_id = tx['receiver_id']
    tx_id = tx['tx_id']
    amount = float(tx['amount'])
    
    # Simple Gremlin script to upsert nodes and edges.
    # Note: In production, parameterized queries or bytecode should be used to prevent injection.
    query = f"""
    g.V('{sender_id}').fold().coalesce(unfold(), addV('User').property(id, '{sender_id}')).
      V('{receiver_id}').fold().coalesce(unfold(), addV('User').property(id, '{receiver_id}')).
      V('{sender_id}').addE('transfers').to(V('{receiver_id}')).
        property('tx_id', '{tx_id}').
        property('amount', {amount})
    """
    try:
        g_client.submit(query).all().result()
    except Exception as e:
        print(f"Graph DB Insert Error for TX {tx_id}: {e}")

def detect_structuring(sender_id, g_client):
    """
    Gremlin query to find structuring:
    Finds if the sender has sent multiple transactions between 8500 and 10000.
    """
    query = f"""
    g.V('{sender_id}').outE('transfers').has('amount', P.between(8500.0, 10000.0)).count()
    """
    try:
        result = g_client.submit(query).all().result()
        count = result[0] if result else 0
        if count >= 3:
            print(f"ALERT: Structuring detected for User {sender_id}. Count: {count}")
            return {
                "alert_id": str(uuid.uuid4()),
                "user_id": sender_id,
                "rule_name": "structuring",
                "risk_weight": 0.95,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
    except Exception as e:
        print(f"Detection Error (Structuring): {e}")
    return None

def detect_cycles(sender_id, g_client):
    """
    Gremlin query to find mule cycles:
    Finds if there's a path of length 3-5 that returns to the sender.
    """
    query = f"""
    g.V('{sender_id}').repeat(out().simplePath()).times(4).emit().hasId('{sender_id}').path().limit(1)
    """
    try:
        result = g_client.submit(query).all().result()
        if result:
            print(f"ALERT: Mule Cycle detected involving User {sender_id}. Path: {result}")
            return {
                "alert_id": str(uuid.uuid4()),
                "user_id": sender_id,
                "rule_name": "mule_cycle",
                "risk_weight": 0.88,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
    except Exception as e:
        print(f"Detection Error (Cycles): {e}")
    return None

def lambda_handler(event, context):
    g_client = get_gremlin_client()
    alerts = []
    
    if not g_client:
        print("Warning: Running without Neptune connection.")
    
    records = event.get('Records', [])
    print(f"Processing {len(records)} Kinesis records")
    
    for record in records:
        try:
            # Kinesis data is base64 encoded
            payload = base64.b64decode(record['kinesis']['data']).decode('utf-8')
            tx = json.loads(payload)
            
            if g_client:
                # 1. Ingest Data
                process_transaction(tx, g_client)
                
                # 2. Run Real-Time Graph Analytics
                # In a real system, you might not run this synchronously per tx to avoid bottlenecks,
                # but instead batch evaluate or use async triggers.
                struct_alert = detect_structuring(tx['sender_id'], g_client)
                if struct_alert: alerts.append(struct_alert)
                
                cycle_alert = detect_cycles(tx['sender_id'], g_client)
                if cycle_alert: alerts.append(cycle_alert)
                
        except Exception as e:
            print(f"Error processing record: {e}")
            
    print(f"Generated {len(alerts)} alerts.")
    # Here you could push alerts to S3, SNS, or another Kinesis stream for the Dashboard to consume.
    return {
        'statusCode': 200,
        'body': json.dumps(f"Processed {len(records)} txs. Found {len(alerts)} alerts.")
    }
