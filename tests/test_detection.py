import os
import shutil
import pytest
import pandas as pd
from data_generator.generate_data import generate_synthetic_data
from detection.detect_structuring import detect_structuring
from detection.detect_mule_networks import detect_mule_networks

TEST_DATA_DIR = "test_data"

@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    # Clean and recreate test data directory
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    
    # Generate a small test dataset
    generate_synthetic_data(num_users=100, num_txs=500, seed=42, out_dir=TEST_DATA_DIR)
    
    yield
    
    # Teardown test environment
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)

def test_data_generation():
    users_file = os.path.join(TEST_DATA_DIR, "users.csv")
    txs_file = os.path.join(TEST_DATA_DIR, "transactions.csv")
    gt_file = os.path.join(TEST_DATA_DIR, "ground_truth.csv")
    
    assert os.path.exists(users_file)
    assert os.path.exists(txs_file)
    assert os.path.exists(gt_file)
    
    df_users = pd.read_csv(users_file)
    df_txs = pd.read_csv(txs_file)
    df_gt = pd.read_csv(gt_file)
    
    # Assert columns
    assert "user_id" in df_users.columns
    assert "kyc_status" in df_users.columns
    assert "risk_score" in df_users.columns
    
    assert "tx_id" in df_txs.columns
    assert "sender_id" in df_txs.columns
    assert "receiver_id" in df_txs.columns
    assert "amount" in df_txs.columns
    
    assert "entity_id" in df_gt.columns
    assert "pattern_type" in df_gt.columns
    
    # Check injected anomalies
    assert len(df_gt[df_gt['pattern_type'] == 'structuring_sender']) > 0
    assert len(df_gt[df_gt['pattern_type'] == 'mule_hub']) > 0
    assert len(df_gt[df_gt['pattern_type'] == 'mule_cycle_user']) > 0

def test_structuring_detection():
    alerts_file = os.path.join(TEST_DATA_DIR, "alerts.csv")
    
    # Run structuring detection on test data
    detect_structuring(data_dir=TEST_DATA_DIR, threshold=10000.0, window_days=3, ratio_trigger=1.5)
    
    assert os.path.exists(alerts_file)
    df_alerts = pd.read_csv(alerts_file)
    
    # Should find structuring alerts
    structuring_alerts = df_alerts[df_alerts['rule_name'] == 'structuring']
    assert len(structuring_alerts) > 0
    
    first_alert = structuring_alerts.iloc[0]
    assert "user_id" in first_alert
    assert "contributing_tx_ids" in first_alert
    assert first_alert["total_amount"] >= 15000.0

def test_mule_network_detection():
    alerts_file = os.path.join(TEST_DATA_DIR, "alerts.csv")
    subgraphs_dir = os.path.join(TEST_DATA_DIR, "subgraphs")
    
    # Run mule network detection
    detect_mule_networks(data_dir=TEST_DATA_DIR, window_hours=12, min_spokes=5, outflow_ratio=0.90, cycle_window_days=3)
    
    assert os.path.exists(alerts_file)
    df_alerts = pd.read_csv(alerts_file)
    
    # Should find mule hubs & cycles
    hub_alerts = df_alerts[df_alerts['rule_name'] == 'mule_hub']
    cycle_alerts = df_alerts[df_alerts['rule_name'] == 'mule_cycle']
    
    assert len(hub_alerts) > 0
    assert len(cycle_alerts) > 0
    
    # Check that subgraph exports exist
    for alert_id in df_alerts[df_alerts['rule_name'].isin(['mule_hub', 'mule_cycle'])]['alert_id']:
        subgraph_path = os.path.join(subgraphs_dir, f"{alert_id}.json")
        assert os.path.exists(subgraph_path)
