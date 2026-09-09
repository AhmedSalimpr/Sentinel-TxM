import os
import uuid
import argparse
import pandas as pd

def detect_structuring(data_dir="data", threshold=10000.0, window_days=3, ratio_trigger=1.8):
    tx_file = os.path.join(data_dir, "transactions.csv")
    users_file = os.path.join(data_dir, "users.csv")
    alerts_file = os.path.join(data_dir, "alerts.csv")
    
    if not os.path.exists(tx_file) or not os.path.exists(users_file):
        print("Error: transactions.csv or users.csv not found. Run generate_data.py first.")
        return
        
    df_txs = pd.read_csv(tx_file)
    df_users = pd.read_csv(users_file)
    
    df_txs['timestamp'] = pd.to_datetime(df_txs['timestamp'])
    
    # Filter for sub-threshold band: 85% to 99.99% of threshold
    lower_bound = threshold * 0.85
    upper_bound = threshold * 0.9999
    candidates = df_txs[(df_txs['amount'] >= lower_bound) & (df_txs['amount'] < upper_bound)].copy()
    candidates = candidates.sort_values(by='timestamp')
    
    alerts = []
    
    # Group by sender to evaluate individual behavior
    for sender_id, group in candidates.groupby('sender_id'):
        tx_records = group.to_dict('records')
        alerted_txs = set()
        
        for i, tx in enumerate(tx_records):
            if tx['tx_id'] in alerted_txs:
                continue
                
            tx_time = tx['timestamp']
            window_start = tx_time - pd.Timedelta(days=window_days)
            
            # Find all candidate transactions within the sliding window [window_start, tx_time]
            window_txs = [t for t in tx_records[:i+1] if t['timestamp'] >= window_start]
            
            total_amount = sum(t['amount'] for t in window_txs)
            
            # Fetch user risk early for dynamic threshold
            user_info = df_users[df_users['user_id'] == sender_id]
            base_risk = user_info['risk_score'].values[0] if not user_info.empty else 0.5
            
            # High-risk users only need 2 transactions to trigger (structurers), others need 3
            required_count = 2 if base_risk >= 0.70 else 3
            
            # Trigger alert if sum exceeds ratio_trigger * threshold
            # and there are enough transactions in the window
            if total_amount >= ratio_trigger * threshold and len(window_txs) >= required_count:
                # Build alert details
                contributing_ids = [t['tx_id'] for t in window_txs]
                
                # Use already-fetched user baseline risk
                
                # Risk weight calculation (combination of amount velocity & user baseline risk)
                # Maximize risk weight at 1.0
                risk_weight = min(1.0, round(float(base_risk * 0.4 + (total_amount / (threshold * 3)) * 0.6), 3))
                
                w_start = min(t['timestamp'] for t in window_txs)
                w_end = max(t['timestamp'] for t in window_txs)
                
                alerts.append({
                    "alert_id": str(uuid.uuid4()),
                    "user_id": sender_id,
                    "rule_name": "structuring",
                    "window_start": w_start.strftime("%Y-%m-%d %H:%M:%S"),
                    "window_end": w_end.strftime("%Y-%m-%d %H:%M:%S"),
                    "total_amount": round(total_amount, 2),
                    "contributing_tx_ids": ",".join(contributing_ids),
                    "risk_weight": risk_weight,
                    "details": f"User executed {len(window_txs)} transfers totaling ${total_amount:,.2f} within a {window_days}-day window, each transfer between ${lower_bound:,.2f} and ${threshold:,.2f}."
                })
                
                # Mark these transactions as alerted to avoid multiple overlapping alerts for the same activity
                alerted_txs.update(contributing_ids)
                
    df_new_alerts = pd.DataFrame(alerts)
    
    # Read existing alerts and merge/overwrite structuring alerts
    if os.path.exists(alerts_file) and os.path.getsize(alerts_file) > 0:
        try:
            df_existing = pd.read_csv(alerts_file)
            # Filter out old structuring alerts to update them
            df_existing = df_existing[df_existing['rule_name'] != 'structuring']
            df_combined = pd.concat([df_existing, df_new_alerts], ignore_index=True)
        except Exception:
            df_combined = df_new_alerts
    else:
        df_combined = df_new_alerts
        
    df_combined.to_csv(alerts_file, index=False)
    print(f"Structuring detection complete. Found {len(df_new_alerts)} structuring alerts.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect structuring (smurfing) alerts.")
    parser.add_argument("--data-dir", type=str, default="data", help="Directory containing CSV data")
    parser.add_argument("--threshold", type=float, default=10000.0, help="Reporting threshold")
    parser.add_argument("--window", type=int, default=3, help="Sliding window size in days")
    parser.add_argument("--ratio", type=float, default=1.8, help="Ratio of threshold for alert trigger")
    args = parser.parse_args()
    
    detect_structuring(data_dir=args.data_dir, threshold=args.threshold, window_days=args.window, ratio_trigger=args.ratio)
