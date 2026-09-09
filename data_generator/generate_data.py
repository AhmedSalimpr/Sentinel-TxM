"""
Sentinel-TxM — Serverless Kinesis Producer
=====================================================
Generates synthetic transaction data in real-time and pushes it to an AWS Kinesis stream.
This script is designed to run as an AWS Lambda function invoked via EventBridge (e.g. every minute).
"""

import os
import json
import random
import uuid
import boto3
from datetime import datetime, timedelta
from faker import Faker

# ---------------------------------------------------------------------------
# Country risk tiers (FATF-inspired)
# ---------------------------------------------------------------------------
HIGH_RISK_COUNTRIES   = ["IR", "KP", "MM", "SY", "YE", "VE"]
MEDIUM_RISK_COUNTRIES = ["KY", "PA", "CY", "MT", "LB", "PK", "UA"]
LOW_RISK_COUNTRIES    = ["US", "GB", "DE", "FR", "CA", "AU", "SG", "JP", "CH", "NL", "NZ", "SE"]
ALL_COUNTRIES = HIGH_RISK_COUNTRIES + MEDIUM_RISK_COUNTRIES + LOW_RISK_COUNTRIES

COUNTRY_RISK = {c: 0.85 for c in HIGH_RISK_COUNTRIES}
COUNTRY_RISK.update({c: 0.45 for c in MEDIUM_RISK_COUNTRIES})
COUNTRY_RISK.update({c: 0.10 for c in LOW_RISK_COUNTRIES})

COUNTRY_WEIGHTS = (
    [0.5]  * len(HIGH_RISK_COUNTRIES) +
    [2.0]  * len(MEDIUM_RISK_COUNTRIES) +
    [5.0]  * len(LOW_RISK_COUNTRIES)
)

# Kinesis Client setup
STREAM_NAME = os.environ.get("STREAM_NAME", "TransactionsStream")
try:
    kinesis_client = boto3.client('kinesis')
except Exception:
    kinesis_client = None

# Pre-generate a pool of 1000 users in memory to simulate a stable user base
# In a real system, these would be pulled from a database, but for the generator
# keeping them in memory across Lambda invocations (warm starts) is efficient.
fake = Faker()
USERS = []

def uid():
    return str(uuid.uuid4())

def rand_country():
    return random.choices(ALL_COUNTRIES, weights=COUNTRY_WEIGHTS)[0]

def rand_account_age():
    return random.randint(1, 3650)

def normal_amount():
    if random.random() < 0.75:
        a = round(random.lognormvariate(5.5, 0.9), 2)
    else:
        a = round(random.lognormvariate(9.0, 0.7), 2)
    return max(1.0, min(a, 9_800.0))

def make_user(is_pep=False, risk_override=None):
    kyc = random.choices(["verified", "pending", "rejected"], [0.82, 0.14, 0.04])[0]
    
    if risk_override is not None:
        risk = risk_override
    else:
        # Simplified risk generation without numpy
        if kyc == "verified": risk = random.betavariate(1.2, 6)
        elif kyc == "pending": risk = random.betavariate(2.5, 3.5)
        else: risk = random.betavariate(5, 1.5)
        risk = round(risk, 3)

    if is_pep: risk = min(1.0, round(risk + 0.25, 3))
    c = rand_country()
    
    return {
        "user_id": uid(),
        "kyc_status": kyc,
        "risk_score": risk,
        "country_code": c,
        "country_risk": round(COUNTRY_RISK.get(c, 0.2), 3),
        "device_ip": fake.ipv4(),
        "account_age_days": rand_account_age(),
        "is_pep": int(is_pep)
    }

def init_users():
    global USERS
    if not USERS:
        for _ in range(1000):
            USERS.append(make_user(is_pep=(random.random() < 0.01)))

def make_tx(sender, receiver, amount, timestamp, pattern_type=None, pattern_id=None):
    return {
        "tx_id": uid(),
        "sender_id": sender["user_id"],
        "receiver_id": receiver["user_id"],
        "sender_country": sender["country_code"],
        "receiver_country": receiver["country_code"],
        "amount": round(amount, 2),
        "currency": "USD",
        "timestamp": timestamp.isoformat(),
        "is_cross_border": int(sender["country_code"] != receiver["country_code"]),
        # Ground truth labels for ML evaluation
        "pattern_type": pattern_type,
        "pattern_id": pattern_id
    }

def generate_structuring(current_time):
    # Simulate a quick burst structuring event
    pid = f"structuring_{uid()[:8]}"
    sender = make_user(risk_override=random.uniform(0.6, 0.9))
    receivers = random.choices(USERS, k=random.randint(3, 7))
    
    txs = []
    threshold = 10_000.0
    for r in receivers:
        amt = round(random.uniform(threshold * 0.85, threshold * 0.99), 2)
        # Offset time slightly for realism
        ts = current_time + timedelta(seconds=random.randint(-300, 300))
        txs.append(make_tx(sender, r, amt, ts, "structuring_tx", pid))
    return txs

def lambda_handler(event, context):
    init_users()
    current_time = datetime.utcnow()
    records = []
    
    # Generate 50-100 background transactions
    num_bg = random.randint(50, 100)
    for _ in range(num_bg):
        sender = random.choice(USERS)
        receiver = random.choice(USERS)
        while receiver == sender:
            receiver = random.choice(USERS)
            
        ts = current_time + timedelta(seconds=random.randint(-60, 60))
        records.append(make_tx(sender, receiver, normal_amount(), ts, "background", None))
        
    # Inject 1 Structuring Pattern (10% probability per invocation)
    if random.random() < 0.10:
        records.extend(generate_structuring(current_time))
        
    # Shuffle records
    random.shuffle(records)
    
    # Push to Kinesis
    if kinesis_client and STREAM_NAME:
        kinesis_records = []
        for r in records:
            # We partition by sender_id to ensure order per sender
            kinesis_records.append({
                'Data': json.dumps(r).encode('utf-8'),
                'PartitionKey': r['sender_id']
            })
            
        # Send in batches of 500 max (Kinesis limit)
        for i in range(0, len(kinesis_records), 500):
            batch = kinesis_records[i:i+500]
            try:
                response = kinesis_client.put_records(
                    Records=batch,
                    StreamName=STREAM_NAME
                )
                print(f"Pushed {len(batch)} records to {STREAM_NAME}. Failed: {response.get('FailedRecordCount', 0)}")
            except Exception as e:
                print(f"Failed to put records to Kinesis: {e}")
    else:
        print(f"Dry run. Generated {len(records)} records. (No Kinesis client)")

    return {
        'statusCode': 200,
        'body': json.dumps(f"Generated {len(records)} transactions.")
    }

if __name__ == "__main__":
    # Local testing
    print(lambda_handler({}, None))
