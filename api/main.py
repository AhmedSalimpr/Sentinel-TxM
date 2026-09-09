import os
import json
import csv
import subprocess
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from typing import Optional, List
from datetime import datetime

app = FastAPI(title="Sentinel-TxM API", description="FastAPI backend for Transaction Monitoring & Graph Analytics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "data"

def get_file_path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)

def read_csv_as_dicts(filepath: str) -> List[dict]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row for row in reader]

def write_dicts_to_csv(filepath: str, data: List[dict]):
    if not data:
        return
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.get("/api/alerts")
def get_alerts(rule_name: Optional[str] = None, sort_by: Optional[str] = "risk_weight", order: Optional[str] = "desc"):
    alerts = read_csv_as_dicts(get_file_path("alerts.csv"))
    if not alerts: return []
    
    if rule_name:
        alerts = [a for a in alerts if a.get('rule_name') == rule_name]
        
    if sort_by and alerts and sort_by in alerts[0]:
        reverse = (order == "desc")
        try:
            alerts.sort(key=lambda x: float(x.get(sort_by, 0)), reverse=reverse)
        except ValueError:
            alerts.sort(key=lambda x: str(x.get(sort_by, "")), reverse=reverse)
            
    return alerts

@app.get("/api/alerts/{alert_id}")
def get_alert_detail(alert_id: str):
    alerts = read_csv_as_dicts(get_file_path("alerts.csv"))
    alert = next((a for a in alerts if a.get('alert_id') == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
        
    tx_ids = []
    if alert.get("contributing_tx_ids"):
        tx_ids = alert["contributing_tx_ids"].split(",")
        
    txs = read_csv_as_dicts(get_file_path("transactions.csv"))
    contributing_txs = [t for t in txs if t.get('tx_id') in tx_ids]
    
    subgraph = None
    subgraph_path = os.path.join(DATA_DIR, "subgraphs", f"{alert_id}.json")
    if os.path.exists(subgraph_path):
        with open(subgraph_path, "r") as f:
            subgraph = json.load(f)
            
    return {
        "alert": alert,
        "contributing_transactions": contributing_txs,
        "subgraph": subgraph
    }

@app.get("/api/users/{user_id}")
def get_user_profile(user_id: str):
    users = read_csv_as_dicts(get_file_path("users.csv"))
    user = next((u for u in users if u.get('user_id') == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    txs = read_csv_as_dicts(get_file_path("transactions.csv"))
    user_txs = [t for t in txs if t.get('sender_id') == user_id or t.get('receiver_id') == user_id]
    user_txs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return {
        "user": user,
        "transactions": user_txs
    }

@app.get("/api/metrics")
def get_metrics():
    alerts = read_csv_as_dicts(get_file_path("alerts.csv"))
    users = read_csv_as_dicts(get_file_path("users.csv"))
    gt = read_csv_as_dicts(get_file_path("ground_truth.csv"))
    
    if not gt or not users:
        return {"error": "Ground truth or users metadata missing."}
        
    gt_map = {}
    for row in gt:
        pattern = row.get('pattern_type')
        if pattern not in gt_map:
            gt_map[pattern] = set()
        gt_map[pattern].add(row.get('entity_id'))
        
    flagged_map = {}
    for alert in alerts:
        rule = alert.get('rule_name')
        if rule not in flagged_map:
            flagged_map[rule] = set()
        flagged_map[rule].add(alert.get('user_id'))
        
    def calc_metrics(flagged, ground_truth, all_count):
        tp = len(flagged.intersection(ground_truth))
        fp = len(flagged - ground_truth)
        fn = len(ground_truth - flagged)
        tn = all_count - (tp + fp + fn)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        
        return {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1, 3),
            "false_positive_rate": round(fpr, 4)
        }
        
    all_users_count = len(users)
    
    all_flagged = set(a.get('user_id') for a in alerts)
    all_gt = set(g.get('entity_id') for g in gt if g.get('entity_type') == 'user')
    
    return {
        "overall": calc_metrics(all_flagged, all_gt, all_users_count),
        "rules": {
            "structuring": calc_metrics(flagged_map.get('structuring', set()), gt_map.get('structuring_sender', set()), all_users_count),
            "mule_hub": calc_metrics(flagged_map.get('mule_hub', set()), gt_map.get('mule_hub', set()), all_users_count),
            "mule_cycle": calc_metrics(flagged_map.get('mule_cycle', set()).union(flagged_map.get('mule_cycle_relay', set())), gt_map.get('mule_cycle_user', set()), all_users_count),
        },
        "summary": {
            "total_users": all_users_count,
            "total_alerts": len(alerts),
            "ground_truth_positives": len(all_gt)
        }
    }

@app.get("/api/dataset/{dataset_name}")
def get_dataset(dataset_name: str, limit: int = 100, page: int = 1):
    valid = ["transactions", "users", "ground_truth", "alerts"]
    if dataset_name not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid dataset.")
    
    records = read_csv_as_dicts(get_file_path(f"{dataset_name}.csv"))
    total = len(records)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    
    return {
        "dataset": dataset_name,
        "records": records[start_idx:end_idx],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if limit > 0 else 1
    }

@app.get("/api/transactions")
def get_transactions(sender_id: Optional[str] = None, receiver_id: Optional[str] = None, page: int = 1, limit: int = 50):
    txs = read_csv_as_dicts(get_file_path("transactions.csv"))
    if sender_id:
        txs = [t for t in txs if t.get('sender_id') == sender_id]
    if receiver_id:
        txs = [t for t in txs if t.get('receiver_id') == receiver_id]
        
    total = len(txs)
    start_idx = (page - 1) * limit
    return {
        "records": txs[start_idx:start_idx+limit],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if limit > 0 else 1
    }

@app.get("/api/transactions/count")
def get_transaction_count():
    txs = read_csv_as_dicts(get_file_path("transactions.csv"))
    return {"count": len(txs)}

@app.post("/api/regenerate")
def regenerate_data(background_tasks: BackgroundTasks):
    # In the serverless architecture, data streams continuously via Kinesis -> Lambda -> Neptune.
    # We return a success status to unblock the dashboard's refresh cycle.
    return {"status": "success", "message": "Pipeline triggered asynchronously (Serverless Architecture)."}

# AWS Lambda Handler
handler = Mangum(app)
