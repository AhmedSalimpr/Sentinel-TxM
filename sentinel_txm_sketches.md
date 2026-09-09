# Sentinel-TxM Architectural & Algorithmic Sketches

This document contains Mermaid diagrams illustrating the structure, logical flow, and graph algorithms used in **Project Sentinel-TxM**.

---

## 1. End-to-End System Data Flow

This diagram illustrates how transaction data is generated, processed, stored, and served to the user interface.

```mermaid
graph TD
    %% Component Blocks
    subgraph DataGen["Phase 1: Procedural Generator"]
        A[faker Engine] --> B["User Accounts (with beta-risk scores)"]
        A --> C["Normal Transactions (log-normal values)"]
        D["Suspicious Pattern Injections"] --> B
        D --> C
        B & C --> E["Ground Truth Labels (ground_truth.csv)"]
    end

    subgraph Detect["Phases 2 & 3: Detection Rules"]
        F[DuckDB / Pandas] --> G["Structuring Rule (3-day aggregation)"]
        H[NetworkX Graph Engine] --> I["Mule Hubs (degree & outflow ratios)"]
        H --> J["Layering Cycles (depth-limited DFS)"]
    end

    subgraph Serve["Phase 4: Serving Layer"]
        K[(data/alerts.csv)] --> L[FastAPI App]
        M[(data/subgraphs/*.json)] --> L
        N[(data/users.csv & transactions.csv)] --> L
    end

    subgraph Client["Phase 5: Analyst UI"]
        O[React Dashboard] -- GET /alerts --> L
        O -- GET /metrics --> L
        O -- GET /users/id --> L
    end

    %% Linkages
    B & C --> F & H
    G & I & J --> K
    I & J --> M
```

---

## 2. Structuring (Smurfing) Sliding-Window Logic

This diagram details the transaction-filtering and sliding-window aggregation logic used to identify attempts to bypass threshold reporting limits.

```mermaid
flowchart TD
    Start([Load Transactions CSV]) --> Filter{Is Amount inside sub-threshold range?}
    Filter -- No (< $8,500 or >= $10,000) --> Ignore[Skip Transaction]
    Filter -- "Yes ($8,500 - $9,990)" --> Group[Group by sender_id]
    
    Group --> Loop[Iterate sender's transactions chronologically]
    Loop --> Window["Define lookback window [t - 3 Days, t]"]
    Window --> Sum[Calculate sum of transactions inside window]
    
    Sum --> Verify{Is cumulative sum >= $15,000 & count > 1?}
    Verify -- No --> Next[Move to next transaction]
    Verify -- Yes --> Risk[Calculate Risk Weight based on baseline user risk & velocity]
    
    Risk --> Deduplicate{Have these contributing transaction IDs triggered an alert already?}
    Deduplicate -- Yes --> Next
    Deduplicate -- No --> Create["Generate Alert & mark transaction IDs as alerted"]
    
    Create --> Next
    Next --> End([Save alerts.csv])
```

---

## 3. Mule Hub (Hub-and-Spoke) Detection Algorithm

This diagram demonstrates how NetworkX identifies high-velocity hub-and-spoke layering structures.

```mermaid
flowchart TD
    Start([Build NetworkX MultiDiGraph]) --> LoopNodes[Iterate each node H in graph]
    LoopNodes --> CheckIn{Is in-degree >= 5?}
    
    CheckIn -- No --> NextNode[Move to next node]
    CheckIn -- Yes --> SortIn[Sort inbound transactions chronologically]
    
    SortIn --> SlideWindow["Slide 12-hour window over inbound transfers"]
    SlideWindow --> CheckSpokes{Are there >= 5 unique senders in window?}
    
    CheckSpokes -- No --> NextNode
    CheckSpokes -- Yes --> SumIn[Calculate Total Received sum]
    
    SumIn --> ScanOut["Scan outbound transfers from H in lookahead window"]
    ScanOut --> GroupRecv[Group outbound transfers by receiver]
    
    GroupRecv --> MatchSink{Does any single receiver S receive >= 90% of Total Received?}
    MatchSink -- No --> NextNode
    MatchSink -- Yes --> Save["Create Mule Hub Alert & export subgraph {H, S, Spokes} to JSON"]
    
    Save --> NextNode
    NextNode --> End([Process Complete])
```

---

## 4. Layering Cycle DFS Loop Validation

This diagram details the optimized DFS search and timestamp sequence check used to locate laundering transaction loops.

```mermaid
flowchart TD
    Start([Build Directed Graph G]) --> LoopStart[Iterate each node StartNode]
    LoopStart --> DFS["Run depth-limited DFS (depth limit = 5)"]
    
    DFS --> Path{Does path lead back to StartNode?}
    Path -- No --> NextPath[Continue DFS search]
    Path -- Yes --> CycleCheck{Is cycle length between 3 and 5 nodes?}
    
    CycleCheck -- No --> NextPath
    CycleCheck -- Yes --> OrderCheck{Are node indices ordered to prevent duplicates?}
    
    OrderCheck -- No --> NextPath
    OrderCheck -- Yes --> Collect[Collect structural cycle node path]
    
    Collect --> ChronoCheck{Do transactions occur in sequential order: t1 < t2 < t3 < t4?}
    ChronoCheck -- No --> NextCycle[Move to next collected cycle]
    
    ChronoCheck -- Yes --> TimeWindow{Does cycle complete in <= 3 days?}
    TimeWindow -- No --> NextCycle
    
    TimeWindow -- Yes --> AmountCheck{Are transaction amounts consistent: hop decay <= 30%?}
    AmountCheck -- No --> NextCycle
    
    AmountCheck -- Yes --> Save["Generate mule_cycle alert & export subgraph path JSON"]
    
    Save --> NextCycle
    NextCycle --> LoopStart
    LoopStart --> End([Save alerts.csv])
```
