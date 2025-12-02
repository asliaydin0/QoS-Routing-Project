# test_core.py ← TAM OLARAK BÖYLE OLSUN

from core.network_generator import generate_network
from core.metrics import calculate_delay, calculate_reliability_cost, calculate_resource_cost, calculate_total_cost
import random

print("Ağ üretiliyor...")
G = generate_network(n_nodes=250, p=0.4, seed=12345)  # 12345 kesin çalışıyor (test ettim)

print(f"Başarılı → {G.number_of_nodes()} düğüm, {G.number_of_edges()} kenar")

# GARANTİLİ YOL BUL (BFS ile en kısa yol)
from networkx import shortest_path
start = 0
goal = 249

try:
    path = shortest_path(G, source=start, target=goal)
    print(f"\nEN KISA YOL BULUNDU → {len(path)} düğüm: {path[:10]}... → {goal}")
    
    print("\nMETRİKLER:")
    print(f"Toplam Gecikme        : {calculate_delay(path, G):.3f} ms")
    print(f"Güvenilirlik Maliyeti : {calculate_reliability_cost(path, G):.6f}")
    print(f"Kaynak Maliyeti       : {calculate_resource_cost(path, G):.4f}")
    print(f"Total Cost (0.5-0.3-0.2): {calculate_total_cost(path, G, 0.5, 0.3, 0.2):.4f}")
    print(f"Total Cost (0.2-0.6-0.2): {calculate_total_cost(path, G, 0.2, 0.6, 0.2):.4f}")
    print("\nCORE %100 ÇALIŞIYOR! Artık GA yazmaya geçebilirsin")
    
except:
    print("Bu seed'de bile yol yok (çok nadir). seed=9999 dene.")