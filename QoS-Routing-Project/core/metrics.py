# core/metrics.py
import math

# core/metrics.py – sadece bu fonksiyonu değiştir
def calculate_delay(path, G):
    if len(path) < 2:
        return float('inf')
    delay = 0.0
    for i in range(len(path)-1):
        u, v = path[i], path[i+1]
        if not G.has_edge(u, v):  # kenar yoksa
            return float('inf')
        delay += G.edges[u, v]['delay']
    for node in path[1:-1]:
        delay += G.nodes[node]['processing_delay']
    return round(delay, 4)

def calculate_reliability_cost(path, G):
    if len(path) < 2: return float('inf')
    cost = 0
    for i in range(len(path)-1):
        r = G.edges[path[i], path[i+1]]['reliability']
        cost += -math.log(r) if r > 0 else 20
    for node in path:
        r = G.nodes[node]['reliability']
        cost += -math.log(r) if r > 0 else 20
    return round(cost, 6)

def calculate_resource_cost(path, G):
    if len(path) < 2: return float('inf')
    cost = 0
    for i in range(len(path)-1):
        bw = G.edges[path[i], path[i+1]]['bandwidth']
        cost += 1000.0 / bw
    return round(cost, 4)

def calculate_total_cost(path, G, w_delay=0.33, w_rel=0.33, w_res=0.34):
    return round(w_delay * calculate_delay(path, G) +
                 w_rel * calculate_reliability_cost(path, G) +
                 w_res * calculate_resource_cost(path, G), 6)