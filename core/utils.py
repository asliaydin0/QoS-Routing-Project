# core/utils.py
from networkx import shortest_path

def get_guaranteed_path(G, start, goal, seed=None):
    """0-249 arası kesin yol bulur, yoksa yeni ağ üretir"""
    import random
    random.seed(seed)
    
    while True:
        try:
            return shortest_path(G, source=start, target=goal)
        except:
            print("Yol yok, yeni ağ üretiliyor...")
            from core.network_generator import generate_network
            G = generate_network(seed=random.randint(1, 999999))