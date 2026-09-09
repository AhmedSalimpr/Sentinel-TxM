import os
import json
import uuid
import argparse
import pandas as pd
import networkx as nx

def save_subgraph(alert_ids, nodes_data, edges_data, subgraphs_dir):
    for aid in alert_ids:
        data = {
            "alert_id": aid,
            "nodes": nodes_data,
            "edges": edges_data
        }
        with open(os.path.join(subgraphs_dir, f"{aid}.json"), "w") as f:
            json.dump(data, f, indent=2)

def detect_mule_networks(data_dir="data", window_hours=12, min_spokes=5, outflow_ratio=0.90, cycle_window_days=5):
    tx_file = os.path.join(data_dir, "transactions.csv")
    users_file = os.path.join(data_dir, "users.csv")
    alerts_file = os.path.join(data_dir, "alerts.csv")
    subgraphs_dir = os.path.join(data_dir, "subgraphs")
    
    os.makedirs(subgraphs_dir, exist_ok=True)
    
    if not os.path.exists(tx_file) or not os.path.exists(users_file):
        print("Error: transactions.csv or users.csv not found. Run generate_data.py first.")
        return
        
    df_txs = pd.read_csv(tx_file)
    df_users = pd.read_csv(users_file)
    
    df_txs['timestamp'] = pd.to_datetime(df_txs['timestamp'])
    user_metadata = df_users.set_index('user_id').to_dict('index')
    
    # 1. Build Directed Graph
    G = nx.MultiDiGraph()
    for _, user in df_users.iterrows():
        G.add_node(user['user_id'], **user)
        
    for _, tx in df_txs.iterrows():
        G.add_edge(
            tx['sender_id'],
            tx['receiver_id'],
            tx_id=tx['tx_id'],
            sender_id=tx['sender_id'],
            receiver_id=tx['receiver_id'],
            amount=tx['amount'],
            timestamp=tx['timestamp'],
            currency=tx['currency']
        )
        
    alerts = []
    
    # --- Part A: Hub-and-Spoke Detection ---
    print("Running Hub-and-Spoke (Mule Hub) detection...")
    hubs_detected = 0
    
    for node in G.nodes:
        in_edges = [data for u, v, key, data in G.in_edges(node, keys=True, data=True)]
        if len(in_edges) < min_spokes:
            continue
            
        in_edges = sorted(in_edges, key=lambda x: x['timestamp'])
        
        for i, in_tx in enumerate(in_edges):
            window_start = in_tx['timestamp']
            window_end = window_start + pd.Timedelta(hours=window_hours)
            
            window_in = [t for t in in_edges[i:] if t['timestamp'] <= window_end]
            unique_senders = set(t['sender_id'] for t in window_in)
            if len(unique_senders) < min_spokes:
                continue
                
            total_inbound = sum(t['amount'] for t in window_in)
            out_edges = [data for u, v, key, data in G.out_edges(node, keys=True, data=True)]
            out_window_end = window_end + pd.Timedelta(hours=window_hours)
            window_out = [t for t in out_edges if window_start <= t['timestamp'] <= out_window_end]
            
            out_by_receiver = {}
            for t in window_out:
                recv = t['receiver_id']
                out_by_receiver.setdefault(recv, []).append(t)
                
            for receiver_id, tx_list in out_by_receiver.items():
                receiver_total = sum(t['amount'] for t in tx_list)
                if receiver_total >= total_inbound * outflow_ratio:
                    alert_id = str(uuid.uuid4())
                    contributing_tx_ids = [t['tx_id'] for t in window_in] + [t['tx_id'] for t in tx_list]
                    
                    hub_meta = user_metadata.get(node, {"kyc_status": "unknown", "risk_score": 0.5})
                    hub_risk = hub_meta.get("risk_score", 0.5)
                    risk_weight = min(1.0, round(float(hub_risk * 0.5 + (len(unique_senders) / 10) * 0.3 + min(total_inbound / 50000, 1.0) * 0.2), 3))
                    
                    w_start = window_start.strftime("%Y-%m-%d %H:%M:%S")
                    w_end = max(t['timestamp'] for t in tx_list).strftime("%Y-%m-%d %H:%M:%S")
                    
                    sink_alert_id = str(uuid.uuid4())
                    spoke_alert_map = {sp: str(uuid.uuid4()) for sp in unique_senders}

                    # Primary hub alert
                    alerts.append({
                        "alert_id": alert_id,
                        "user_id": node,
                        "rule_name": "mule_hub",
                        "window_start": w_start,
                        "window_end": w_end,
                        "total_amount": round(total_inbound, 2),
                        "contributing_tx_ids": ",".join(contributing_tx_ids),
                        "risk_weight": risk_weight,
                        "details": f"Node flagged as money mule hub: received ${total_inbound:,.2f} from {len(unique_senders)} distinct spokes within {window_hours} hours, and transferred {receiver_total/total_inbound:.1%} (${receiver_total:,.2f}) to sink node {receiver_id[:8]} within 12 hours."
                    })
                    
                    # T5: Flag associated sink and spokes
                    alerts.append({
                        "alert_id": sink_alert_id,
                        "user_id": receiver_id,
                        "rule_name": "mule_sink",
                        "window_start": w_start,
                        "window_end": w_end,
                        "total_amount": round(receiver_total, 2),
                        "contributing_tx_ids": ",".join(t['tx_id'] for t in tx_list),
                        "risk_weight": round(risk_weight * 0.9, 3),
                        "details": f"Node flagged as mule sink receiving concentrated funds from hub {node[:8]}."
                    })
                    
                    for spoke_id in unique_senders:
                        spoke_txs = [t['tx_id'] for t in window_in if t['sender_id'] == spoke_id]
                        spoke_amt = sum(t['amount'] for t in window_in if t['sender_id'] == spoke_id)
                        alerts.append({
                            "alert_id": spoke_alert_map[spoke_id],
                            "user_id": spoke_id,
                            "rule_name": "mule_spoke",
                            "window_start": w_start,
                            "window_end": w_end,
                            "total_amount": round(spoke_amt, 2),
                            "contributing_tx_ids": ",".join(spoke_txs),
                            "risk_weight": round(risk_weight * 0.75, 3),
                            "details": f"Node flagged as mule spoke feeding hub {node[:8]}."
                        })
                        
                    # Save subgraph
                    sink_meta = user_metadata.get(receiver_id, {})
                    nodes_data = [
                        {"id": node, "label": "hub", "kyc": hub_meta.get("kyc_status", "pending"), "risk": float(hub_meta.get("risk_score", 0.9))},
                        {"id": receiver_id, "label": "sink", "kyc": sink_meta.get("kyc_status", "verified"), "risk": float(sink_meta.get("risk_score", 0.2))}
                    ]
                    for sp in unique_senders:
                        sp_meta = user_metadata.get(sp, {})
                        nodes_data.append({"id": sp, "label": "spoke", "kyc": sp_meta.get("kyc_status", "pending"), "risk": float(sp_meta.get("risk_score", 0.4))})
                    
                    edges_data = []
                    for t in window_in:
                        edges_data.append({"source": t['sender_id'], "target": node, "amount": float(t['amount']), "tx_id": t['tx_id']})
                    for t in tx_list:
                        edges_data.append({"source": node, "target": receiver_id, "amount": float(t['amount']), "tx_id": t['tx_id']})
                        
                    all_hub_ids = [alert_id, sink_alert_id] + list(spoke_alert_map.values())
                    save_subgraph(all_hub_ids, nodes_data, edges_data, subgraphs_dir)
                        
                    hubs_detected += 1
                    break
                    
    # --- Part B: Cycle Detection (T2 & T5) ---
    print("Running Layering Cycle detection...")
    cycles_detected = 0
    
    nodes = list(G.nodes())
    
    adj = {node: set() for node in nodes}
    for u, v in G.edges():
        adj[u].add(v)

    # Build a condensed DiGraph for cycle detection.
    # Include edges >= $800 between active nodes with in_degree >= 1 and out_degree >= 1
    G_simple = nx.DiGraph()
    for u, v, key, data in G.edges(keys=True, data=True):
        if data.get('amount', 0) >= 500.0:
            G_simple.add_edge(u, v)

    cycle_nodes = [n for n in G_simple.nodes() if G_simple.in_degree(n) >= 1 and G_simple.out_degree(n) >= 1]
    G_simple = G_simple.subgraph(cycle_nodes)

    print(f"  Cycle search subgraph (amount >= $500): {G_simple.number_of_nodes()} nodes, {G_simple.number_of_edges()} edges")

    # Ultra-fast depth-bounded DFS (max depth 7)
    structural_cycles = []
    node_map = {n: i for i, n in enumerate(cycle_nodes)}
    for i, start_node in enumerate(cycle_nodes):
        stack = [(start_node, [start_node])]
        while stack:
            curr, path = stack.pop()
            for neighbor in G_simple.successors(curr):
                if neighbor == start_node:
                    if 3 <= len(path) <= 7:
                        structural_cycles.append(path)
                elif neighbor not in path and len(path) < 7 and node_map.get(neighbor, -1) > i:
                    stack.append((neighbor, path + [neighbor]))
    
    print(f"  Found {len(structural_cycles)} structural cycles of length 3-7.")
    
    # Deduplicate cycles (same node set)
    seen_cycles = set()
    deduped_cycles = []
    for cycle in structural_cycles:
        key = frozenset(cycle)
        if key not in seen_cycles:
            seen_cycles.add(key)
            deduped_cycles.append(cycle)
    
    edge_cache = {}
    def get_edges_between(u, v):
        """Return all direct edges u->v plus 2-hop relay edges u->relay->v (cached)."""
        pair_key = (u, v)
        if pair_key in edge_cache:
            return edge_cache[pair_key]
            
        edges = []
        if G.has_edge(u, v):
            for k in G[u][v]:
                e = dict(G[u][v][k])
                e['via_relay'] = None
                edges.append(e)
        # 1-hop relay edges: find relay nodes
        for relay in adj[u]:
            if relay != v and G.has_edge(relay, v):
                for k1 in G[u][relay]:
                    for k2 in G[relay][v]:
                        e1 = G[u][relay][k1]
                        e2 = G[relay][v][k2]
                        merged = {
                            'tx_id': f"{e1['tx_id']},{e2['tx_id']}",
                            'sender_id': u,
                            'receiver_id': v,
                            'amount': e2['amount'],
                            'timestamp': e2['timestamp'],
                            'currency': e1.get('currency', 'USD'),
                            'via_relay': relay,
                            '_first_ts': e1['timestamp'],
                        }
                        edges.append(merged)
        edge_cache[pair_key] = edges
        return edges
    
    for cycle in deduped_cycles:
        cycle_edges_txs = []
        possible_flow = True
        for idx in range(len(cycle)):
            u = cycle[idx]
            v = cycle[(idx + 1) % len(cycle)]
            edges = get_edges_between(u, v)
            if not edges:
                possible_flow = False
                break
            cycle_edges_txs.append(edges)
            
        if not possible_flow:
            continue
            
        # Find if there is any sliding window where every leg has a transaction within cycle_window_days
        all_tx_timestamps = []
        for leg in cycle_edges_txs:
            for t in leg:
                all_tx_timestamps.append(t.get('_first_ts', t['timestamp']))
                
        all_tx_timestamps = sorted(all_tx_timestamps)
        seq = None
        t_start = None
        t_end = None
        
        for t_ref in all_tx_timestamps:
            window_limit = t_ref + pd.Timedelta(days=cycle_window_days)
            candidate_seq = []
            valid_leg_match = True
            for leg in cycle_edges_txs:
                matching_txs = [t for t in leg if t_ref <= t.get('_first_ts', t['timestamp']) <= window_limit]
                if not matching_txs:
                    valid_leg_match = False
                    break
                candidate_seq.append(matching_txs[0])
            if valid_leg_match:
                seq = candidate_seq
                t_start = t_ref
                t_end = max(t.get('_first_ts', t['timestamp']) for t in seq)
                break
                
        if seq is not None:
                alert_id = str(uuid.uuid4())
                contributing_tx_ids = []
                for t in seq:
                    contributing_tx_ids.extend(t['tx_id'].split(','))
                total_flow_amount = sum(t['amount'] for t in seq) / len(seq)
                
                avg_node_risk = sum(user_metadata.get(n, {}).get("risk_score", 0.5) for n in cycle) / len(cycle)
                risk_weight = min(1.0, round(float(avg_node_risk * 0.6 + 0.4), 3))
                
                w_start_str = t_start.strftime("%Y-%m-%d %H:%M:%S")
                w_end_str = t_end.strftime("%Y-%m-%d %H:%M:%S")
                
                # Origin cycle alert
                alerts.append({
                    "alert_id": alert_id,
                    "user_id": cycle[0],
                    "rule_name": "mule_cycle",
                    "window_start": w_start_str,
                    "window_end": w_end_str,
                    "total_amount": round(total_flow_amount, 2),
                    "contributing_tx_ids": ",".join(contributing_tx_ids),
                    "risk_weight": risk_weight,
                    "details": f"Suspicious closed transaction cycle detected: {' -> '.join([n[:8] for n in cycle])} -> {cycle[0][:8]} within {cycle_window_days} days. Average transfer size: ${total_flow_amount:,.2f}."
                })
                
                cycle_relay_alert_map = {c_node: str(uuid.uuid4()) for c_node in cycle[1:]}
                
                # T5: Flag cycle relay/spoke nodes
                for c_node in cycle[1:]:
                    alerts.append({
                        "alert_id": cycle_relay_alert_map[c_node],
                        "user_id": c_node,
                        "rule_name": "mule_cycle_relay",
                        "window_start": w_start_str,
                        "window_end": w_end_str,
                        "total_amount": round(total_flow_amount, 2),
                        "contributing_tx_ids": ",".join(contributing_tx_ids),
                        "risk_weight": round(risk_weight * 0.9, 3),
                        "details": f"Node participating in transaction cycle led by {cycle[0][:8]}."
                    })
                
                spoke_alert_ids = []
                spoke_nodes_list = []
                # Flag incoming senders to cycle[0] within 24h before cycle start as mule_cycle_spoke
                t_window_start = t_start - pd.Timedelta(hours=24)
                in_txs = df_txs[(df_txs['receiver_id'] == cycle[0]) & (df_txs['timestamp'] >= t_window_start) & (df_txs['timestamp'] <= t_start)]
                for _, r_spoke in in_txs.iterrows():
                    if r_spoke['sender_id'] not in cycle:
                        sp_aid = str(uuid.uuid4())
                        spoke_alert_ids.append(sp_aid)
                        spoke_nodes_list.append(r_spoke['sender_id'])
                        alerts.append({
                            "alert_id": sp_aid,
                            "user_id": r_spoke['sender_id'],
                            "rule_name": "mule_cycle_spoke",
                            "window_start": r_spoke['timestamp'].strftime("%Y-%m-%d %H:%M:%S"),
                            "window_end": w_start_str,
                            "total_amount": round(r_spoke['amount'], 2),
                            "contributing_tx_ids": r_spoke['tx_id'],
                            "risk_weight": round(risk_weight * 0.75, 3),
                            "details": f"Node feeding funds into transaction cycle leader {cycle[0][:8]}."
                        })
                
                # Build cycle subgraph
                nodes_data = []
                for idx, c_node in enumerate(cycle):
                    c_meta = user_metadata.get(c_node, {})
                    nodes_data.append({
                        "id": c_node,
                        "label": "hub" if idx == 0 else "cycle_node",
                        "kyc": c_meta.get("kyc_status", "pending"),
                        "risk": float(c_meta.get("risk_score", 0.7))
                    })
                for sp in set(spoke_nodes_list):
                    sp_meta = user_metadata.get(sp, {})
                    nodes_data.append({
                        "id": sp,
                        "label": "spoke",
                        "kyc": sp_meta.get("kyc_status", "pending"),
                        "risk": float(sp_meta.get("risk_score", 0.5))
                    })
                
                edges_data = []
                for t in seq:
                    edges_data.append({
                        "source": t['sender_id'],
                        "target": t['receiver_id'],
                        "amount": float(t['amount']),
                        "tx_id": t['tx_id']
                    })
                for _, r_spoke in in_txs.iterrows():
                    if r_spoke['sender_id'] not in cycle:
                        edges_data.append({
                            "source": r_spoke['sender_id'],
                            "target": cycle[0],
                            "amount": float(r_spoke['amount']),
                            "tx_id": r_spoke['tx_id']
                        })
                
                all_cycle_ids = [alert_id] + list(cycle_relay_alert_map.values()) + spoke_alert_ids
                save_subgraph(all_cycle_ids, nodes_data, edges_data, subgraphs_dir)
                    
                cycles_detected += 1

    # --- Part C: Round-trip / Carousel Detection (T3) ---
    # The generator creates rings of 3-5 actors (A->B->C->A) with amount jitter <=3%.
    # We reuse structural_cycles (already found above) and filter for near-flat amounts.
    print("Running Round-trip detection...")
    roundtrip_detected = 0
    roundtrip_alert_user_ids = set()
    
    rt_candidates = [c for c in deduped_cycles if 3 <= len(c) <= 5]
    
    for cycle in rt_candidates:
        cycle_edges_txs = []
        possible_flow = True
        for idx in range(len(cycle)):
            u = cycle[idx]
            v = cycle[(idx + 1) % len(cycle)]
            edges = get_edges_between(u, v)
            if not edges:
                possible_flow = False
                break
            cycle_edges_txs.append(edges)
        if not possible_flow:
            continue
        
        # Try to find a chronological sequence with near-flat amounts (variance <= 15%)
        def find_roundtrip_seq(edge_idx, current_seq):
            if edge_idx == len(cycle):
                t_start = current_seq[0]['timestamp']
                t_end = current_seq[-1]['timestamp']
                if (t_end - t_start).total_seconds() / 86400.0 <= 7.0:
                    amounts = [t['amount'] for t in current_seq]
                    mean_amt = sum(amounts) / len(amounts)
                    variance = max(abs(a - mean_amt) / mean_amt for a in amounts)
                    if variance <= 0.15:
                        return list(current_seq)
                return None
            for tx in cycle_edges_txs[edge_idx]:
                if not current_seq:
                    result = find_roundtrip_seq(edge_idx + 1, [tx])
                elif tx['timestamp'] > current_seq[-1]['timestamp']:
                    result = find_roundtrip_seq(edge_idx + 1, current_seq + [tx])
                else:
                    result = None
                if result is not None:
                    return result
            return None
        
        seq = find_roundtrip_seq(0, [])
        if seq:
            already_flagged = set(cycle) & roundtrip_alert_user_ids
            if not already_flagged:
                amounts = [t['amount'] for t in seq]
                mean_amt = sum(amounts) / len(amounts)
                t_start = seq[0]['timestamp']
                t_end = seq[-1]['timestamp']
                contributing = []
                for t in seq:
                    contributing.extend(t['tx_id'].split(','))
                rt_aids = []
                for ring_node in cycle:
                    aid = str(uuid.uuid4())
                    rt_aids.append(aid)
                    roundtrip_alert_user_ids.add(ring_node)
                    alerts.append({
                        "alert_id": aid,
                        "user_id": ring_node,
                        "rule_name": "roundtrip",
                        "window_start": t_start.strftime("%Y-%m-%d %H:%M:%S"),
                        "window_end": t_end.strftime("%Y-%m-%d %H:%M:%S"),
                        "total_amount": round(mean_amt, 2),
                        "contributing_tx_ids": ",".join(contributing),
                        "risk_weight": 0.82,
                        "details": f"Round-trip carousel ring of {len(cycle)} actors detected, mean transfer ${mean_amt:,.2f}."
                    })
                
                # Build roundtrip subgraph
                rt_nodes = []
                for idx, r_node in enumerate(cycle):
                    r_meta = user_metadata.get(r_node, {})
                    rt_nodes.append({
                        "id": r_node,
                        "label": "cycle_node",
                        "kyc": r_meta.get("kyc_status", "verified"),
                        "risk": float(r_meta.get("risk_score", 0.6))
                    })
                rt_edges = []
                for t in seq:
                    rt_edges.append({
                        "source": t['sender_id'],
                        "target": t['receiver_id'],
                        "amount": float(t['amount']),
                        "tx_id": t['tx_id']
                    })
                save_subgraph(rt_aids, rt_nodes, rt_edges, subgraphs_dir)
                roundtrip_detected += 1

    # --- Part D: Layered Chain Detection (T4) ---
    print("Running Layered Chain detection...")
    chain_detected = 0
    chain_start_seen = set()  # one alert per start node
    # Find simple paths of 4–7 hops, amounts decaying 80%-99% per hop, complete <= 7 days
    for start_node in nodes:
        if start_node in chain_start_seen:
            continue
        stack = [(start_node, [start_node], [])]
        while stack:
            curr, path, tx_path = stack.pop()
            if len(path) >= 5 and start_node not in chain_start_seen:
                t_start = tx_path[0]['timestamp']
                t_end = tx_path[-1]['timestamp']
                if (t_end - t_start) <= pd.Timedelta(days=7):
                    avg_amt = sum(t['amount'] for t in tx_path) / len(tx_path)
                    chain_start_seen.add(start_node)
                    c_aid = str(uuid.uuid4())
                    alerts.append({
                        "alert_id": c_aid,
                        "user_id": start_node,
                        "rule_name": "chain",
                        "window_start": t_start.strftime("%Y-%m-%d %H:%M:%S"),
                        "window_end": t_end.strftime("%Y-%m-%d %H:%M:%S"),
                        "total_amount": round(avg_amt, 2),
                        "contributing_tx_ids": ",".join(t['tx_id'] for t in tx_path),
                        "risk_weight": 0.85,
                        "details": f"Layered chain of {len(path)-1} hops detected starting from {start_node[:8]}."
                    })
                    
                    # Build chain subgraph
                    ch_nodes = []
                    for idx, p_node in enumerate(path):
                        p_meta = user_metadata.get(p_node, {})
                        role = "spoke" if idx == 0 else ("sink" if idx == len(path)-1 else "hub")
                        ch_nodes.append({
                            "id": p_node,
                            "label": role,
                            "kyc": p_meta.get("kyc_status", "verified"),
                            "risk": float(p_meta.get("risk_score", 0.6))
                        })
                    ch_edges = []
                    for t in tx_path:
                        ch_edges.append({
                            "source": t['sender_id'],
                            "target": t['receiver_id'],
                            "amount": float(t['amount']),
                            "tx_id": t['tx_id']
                        })
                    save_subgraph([c_aid], ch_nodes, ch_edges, subgraphs_dir)
                    chain_detected += 1
                    continue  # one alert per start node is enough
                    
            if len(path) < 7:
                for neighbor in adj[curr]:
                    if neighbor not in path:
                        if G.has_edge(curr, neighbor):
                            for key in G[curr][neighbor]:
                                tx = G[curr][neighbor][key]
                                if not tx_path:
                                    stack.append((neighbor, path + [neighbor], [tx]))
                                elif tx['timestamp'] > tx_path[-1]['timestamp']:
                                    ratio = tx['amount'] / tx_path[-1]['amount']
                                    # Strict monotone decay: 80-99% retention per hop
                                    if 0.80 <= ratio <= 0.99:
                                        stack.append((neighbor, path + [neighbor], tx_path + [tx]))
                                        
    df_new_alerts = pd.DataFrame(alerts)
    
    if os.path.exists(alerts_file) and os.path.getsize(alerts_file) > 0:
        try:
            df_existing = pd.read_csv(alerts_file)
            mule_rules = ['mule_hub', 'mule_cycle', 'mule_spoke', 'mule_relay', 'mule_sink', 'mule_cycle_spoke', 'mule_cycle_relay', 'roundtrip', 'chain']
            df_existing = df_existing[~df_existing['rule_name'].isin(mule_rules)]
            df_combined = pd.concat([df_existing, df_new_alerts], ignore_index=True)
        except Exception:
            df_combined = df_new_alerts
    else:
        df_combined = df_new_alerts
        
    df_combined.to_csv(alerts_file, index=False)
    print(f"Mule network detection complete. Found {hubs_detected} hubs, {cycles_detected} cycles, {roundtrip_detected} roundtrips, {chain_detected} chains.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect money mule network alerts using graph analytics.")
    parser.add_argument("--data-dir", type=str, default="data", help="Directory containing CSV data")
    parser.add_argument("--window", type=int, default=12, help="Sliding window in hours for hub inbound transfers")
    parser.add_argument("--spokes", type=int, default=5, help="Minimum number of unique spokes for hub")
    parser.add_argument("--ratio", type=float, default=0.90, help="Minimum ratio of outbound to inbound funds for hub")
    parser.add_argument("--cycle-window", type=int, default=5, help="Maximum window in days for sequential cycle completion")
    args = parser.parse_args()
    
    detect_mule_networks(
        data_dir=args.data_dir, 
        window_hours=args.window, 
        min_spokes=args.spokes, 
        outflow_ratio=args.ratio,
        cycle_window_days=args.cycle_window
    )

