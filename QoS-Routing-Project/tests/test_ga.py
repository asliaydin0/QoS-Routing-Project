# test_ga.py
from core.network_generator import generate_network
from algorithms.ga import find_ga_path

print("Ağ ve GA test ediliyor...")
G = generate_network(seed=12345)

print("GA çalışıyor, biraz bekle (15-25 saniye)...")
path, cost, metrics = find_ga_path(G, 0, 249, seed=42)

print("\n" + "="*50)
print("GA BAŞARIYLA BİTTİ!")
print(f"Yol uzunluğu     : {len(path)} düğüm ({len(path)-1} hop)")
print(f"Toplam Maliyet   : {cost:.3f}")
print(f"Çalışma süresi   : {metrics['runtime_sec']} saniye")
print(f"Gecikme          : {metrics['delay']:.1f} ms")
print(f"Güvenilirlik Maliyeti : {metrics['reliability_cost']:.6f}")
print(f"Kaynak Maliyeti  : {metrics['resource_cost']:.2f}")
print("="*50)