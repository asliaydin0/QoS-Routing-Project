# core/network_generator.py  ← BU DOSYANIN TAMAMI BU OLSUN (kopyala-yapıştır)

import networkx as nx
import random
import numpy as np

def generate_network(n_nodes=250, p=0.4, seed=None):
    """
    250 düğümlü, %100 bağlı, özellikli ağ üretir.
    Bağlılık garantilidir → testlerde asla yol bulamama sorunu çıkmaz.
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)
    np.random.seed(seed)

    # Bağlılık garantilene kadar üret
    while True:
        G = nx.erdos_renyi_graph(n_nodes, p, seed=seed, directed=False)
        if nx.is_connected(G):
            print(f"Ağ başarıyla üretildi → {G.number_of_nodes()} düğüm, {G.number_of_edges()} kenar")
            break
        else:
            print("Bağlı değil, tekrar deneniyor...")

    # Düğüm özellikleri
    for node in G.nodes():
        G.nodes[node]['processing_delay'] = round(random.uniform(0.5, 2.0), 3)   # ms
        G.nodes[node]['reliability']       = round(random.uniform(0.95, 0.999), 5)

    # Kenar özellikleri
    for u, v in G.edges():
        G.edges[u, v]['bandwidth']    = round(random.uniform(100, 1000), 2)   # Mbps
        G.edges[u, v]['delay']        = round(random.uniform(3, 15), 3)       # ms
        G.edges[u, v]['reliability']  = round(random.uniform(0.95, 0.999), 5)

    return G