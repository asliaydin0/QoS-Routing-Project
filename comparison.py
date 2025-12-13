import pandas as pd
import networkx as nx
import numpy as np
import time
import os
import random
import math

# --- ALGORITHM IMPORTS ---
try:
    from algorithms.ga import GeneticAlgorithmRouter
    import algorithms.ga as ga_module  # To set weights dynamically
except ImportError:
    print("Warning: Could not import GeneticAlgorithmRouter")

try:
    from algorithms.Q_Learning import q_learning_routing
except ImportError:
    print("Warning: Could not import Q_Learning")

try:
    from algorithms.model import ABC_Routing
except ImportError:
    print("Warning: Could not import ABC_Routing")


def run_single(algo_key, G, src, dst, weights):
    """
    Called by GUI.py to run a specific algorithm.
    args:
        algo_key: "GA", "Q", "ABC", "SA"
        G: NetworkX graph
        src: Source node ID
        dst: Destination node ID
        weights: Tuple (w_delay, w_rel, w_resource)
    returns:
        path: List of nodes
        cost: Total cost (float)
        metrics: Dict with details {'delay':..., 'time_ms':...}
    """
    
    path = []
    cost = float('inf')
    metrics = {}

    
    # --- NORMALIZE GRAPH ATTRIBUTES ---
    # GUI uses: reliability, delay, bandwidth
    # Algos expect: node_reliability, link_delay, link_reliability, capacity
    _normalize_graph_attributes(G) # Ensure G has all keys

    start_time = time.time()
    
    try:
        # ==========================================
        # 1. GENETİK ALGORİTMA (GA)
        # ==========================================
        if algo_key == "GA":
            # Set weights dynamically in the module
            if 'ga_module' in locals():
                ga_module.W_DELAY = weights[0]
                ga_module.W_RELIABILITY = weights[1]
                ga_module.W_RESOURCE = weights[2]
            
            # Initialize and run
            # Demand is assumed 0 or default since GUI doesn't provide it
            ga = GeneticAlgorithmRouter(G, src, dst, demand=100) 
            path, cost = ga.run()
            
            # GA returns (path, cost). We need to calculate component metrics manually
            if path:
                d, rel, res = _calculate_metrics_helper(G, path)
                metrics["delay"] = d
                metrics["rel_cost"] = rel
                metrics["res_cost"] = res
        
        # ==========================================
        # 2. Q-LEARNING (RL)
        # ==========================================
        elif algo_key == "Q":
            # q_learning_routing returns: final_path, final_cost, delay, reliability_val, res_cost
            res = q_learning_routing(G, src, dst, weights, episodes=2000)
            path = res[0]
            cost = res[1]
            
            if path:
                metrics["delay"] = res[2]
                r_val = res[3] if res[3] > 0 else 1e-9
                metrics["rel_cost"] = -math.log(r_val)
                metrics["res_cost"] = res[4]

        # ==========================================
        # 3. YAPAY ARI KOLONİSİ (ABC)
        # ==========================================
        elif algo_key == "ABC":
            abc = ABC_Routing(G, pop_size=20, max_iter=30)
            solution = abc.solve(src, dst, demand=100)
            
            if solution:
                path = solution['path']
                cost = solution['fitness']
                metrics["delay"] = solution['delay']
                r_val = solution['rel'] if solution['rel'] > 0 else 1e-9
                metrics["rel_cost"] = -math.log(r_val)
                metrics["res_cost"] = 0 

        # ==========================================
        # 4. BENZETİMLİ TAVLAMA (SA)
        # ==========================================
        elif algo_key == "SA":
            print("SA not implemented yet.")
            return None, float('inf'), {}

    except Exception as e:
        print(f"Algorithm Error ({algo_key}): {e}")
        return None, float('inf'), {"error": str(e)}

    # Finalize Metrics
    duration_ms = (time.time() - start_time) * 1000
    metrics["time_ms"] = duration_ms
    metrics["total_cost"] = cost
    
    return path, cost, metrics


def _normalize_graph_attributes(G):
    """
    Adds missing aliases to the graph nodes/edges so that
    different algorithms can find what they expect.
    """
    # 1. Edges
    for u, v in G.edges():
        data = G[u][v]
        # bandwidth -> capacity
        if 'capacity' not in data and 'bandwidth' in data:
            data['capacity'] = data['bandwidth']
        # delay -> link_delay
        if 'link_delay' not in data and 'delay' in data:
            data['link_delay'] = data['delay']
        # reliability -> link_reliability
        if 'link_reliability' not in data and 'reliability' in data:
            data['link_reliability'] = data['reliability']

    # 2. Nodes
    for n in G.nodes():
        data = G.nodes[n]
        # reliability -> node_reliability
        if 'node_reliability' not in data and 'reliability' in data:
            data['node_reliability'] = data['reliability']


def _calculate_metrics_helper(G, path):
    """Helper to calculate breakdown of costs for GA or others"""
    total_delay = 0
    total_rel_log = 0 
    resource_cost = 0
    
    # Nodes
    if len(path) > 2:
        for node in path[1:-1]:
            d = G.nodes[node]
            # Handle different key names if necessary
            delay_val = d.get('processing_delay', d.get('proc_delay', 0))
            total_delay += delay_val
            
            r_node = d.get('reliability', d.get('node_reliability', 0.999))
            total_rel_log += -math.log(r_node if r_node > 0 else 1e-9)

    # Edges
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        edge = G[u][v]
        total_delay += edge.get('link_delay', edge.get('delay', 0))
        
        r_link = edge.get('reliability', edge.get('link_reliability', 0.999))
        total_rel_log += -math.log(r_link if r_link > 0 else 1e-9)
        
        bw = edge.get('bandwidth', edge.get('capacity', 100))
        resource_cost += (1000.0 / bw) if bw > 0 else 0
        
    return total_delay, total_rel_log, resource_cost
