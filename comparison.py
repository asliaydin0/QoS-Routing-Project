import pandas as pd
import networkx as nx
import numpy as np
import time
import os
import random

# =============================================================================
# 1. ORTAK AYARLAR (Tüm algoritmalar için adil karşılaştırma)
# =============================================================================
DATA_FOLDER = "datalar"
NODE_FILE = "BSM307_317_Guz2025_TermProject_NodeData.csv"
EDGE_FILE = "BSM307_317_Guz2025_TermProject_EdgeData.csv"
DEMAND_FILE = "BSM307_317_Guz2025_TermProject_DemandData.csv"

# Ağırlıklar (Tüm gruplar bu ağırlıkları kullanmalı!)
W_DELAY = 0.33
W_RELIABILITY = 0.33
W_RESOURCE = 0.34

# =============================================================================
# 2. YARDIMCI FONKSİYONLAR (Veri Yükleme ve Puanlama)
# =============================================================================
def load_data():
    """Verileri yükler ve Grafı oluşturur."""
    print("Veri setleri yükleniyor...")
    def clean_float(x):
        return float(x.replace(',', '.')) if isinstance(x, str) else x

    try:
        df_node = pd.read_csv(os.path.join(DATA_FOLDER, NODE_FILE), sep=';')
        df_edge = pd.read_csv(os.path.join(DATA_FOLDER, EDGE_FILE), sep=';')
        df_demand = pd.read_csv(os.path.join(DATA_FOLDER, DEMAND_FILE), sep=';')
    except FileNotFoundError:
        print("HATA: Dosyalar bulunamadı!")
        return None, None

    df_node['s_ms'] = df_node['s_ms'].apply(clean_float)
    df_node['r_node'] = df_node['r_node'].apply(clean_float)
    df_edge['r_link'] = df_edge['r_link'].apply(clean_float)
    df_edge['capacity_mbps'] = df_edge['capacity_mbps'].apply(clean_float)
    df_edge['delay_ms'] = df_edge['delay_ms'].apply(clean_float)

    G = nx.DiGraph()
    for _, row in df_node.iterrows():
        G.add_node(int(row['node_id']), proc_delay=row['s_ms'], reliability=row['r_node'])
    
    for _, row in df_edge.iterrows():
        bw = row['capacity_mbps'] if row['capacity_mbps'] > 0 else 0.1
        G.add_edge(int(row['src']), int(row['dst']), bandwidth=bw, link_delay=row['delay_ms'], reliability=row['r_link'])
    
    return G, df_demand

def calculate_fitness(G, path):
    """
    ORTAK HAKEM FONKSİYONU
    Tüm algoritmaların bulduğu yol bu fonksiyonla puanlanır.
    """
    if not path: return float('inf')
    
    total_delay = 0
    total_rel_log = 0
    resource_cost = 0
    
    # Düğüm Maliyetleri
    if len(path) > 2:
        for node in path[1:-1]:
            if node not in G: return float('inf')
            d = G.nodes[node]
            total_delay += d.get('proc_delay', 0)
            r = d.get('reliability', 0.999)
            total_rel_log += -np.log(r if r > 0 else 1e-9)

    # Kenar Maliyetleri
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        if not G.has_edge(u, v): return float('inf')
        e = G[u][v]
        total_delay += e.get('link_delay', 0)
        r = e.get('reliability', 0.999)
        total_rel_log += -np.log(r if r > 0 else 1e-9)
        resource_cost += (1000.0 / e.get('bandwidth', 1))

    total_cost = (W_DELAY * total_delay) + (W_RELIABILITY * total_rel_log) + (W_RESOURCE * resource_cost)
    return total_cost

# =============================================================================
# 3. ALGORİTMA SINIFLARI (Burası Takım Çalışması Alanı)
# =============================================================================

# --- 1. GENETİK ALGORİTMA  ---
# Buraya ga.py dosyasındaki 'GeneticAlgorithmRouter' sınıfını olduğu gibi yapıştır.
# Ben örnek olarak senin kodunu buraya ekledim.
class GeneticAlgorithmRouter:
    def __init__(self, G, source, target, demand):
        self.name = "Genetik Algoritma (GA)" # İsim Eklemesi
        self.G = G
        self.source = source
        self.target = target
        self.demand = demand
        self.population = []
        self.pop_size = 60
        self.generations = 100
        self.mutation_rate = 0.3
        self.elitism_count = 4

    # ... (Buraya ga.py dosyasındaki sınıfın metodlarını yapıştırın: crossover, mutate, generate_random_path vb.) ...
    # KODUNUZUN ÇOK UZUN OLMAMASI İÇİN BURADA KISALTTIM. 
    # SİZ ga.py İÇİNDEKİ CLASS'I BURAYA KOPYALAYIN.
    
    def run(self):
        # Örnek çalışma (Gerçek kodunuzu yapıştırınca burası değişecek)
        # return path, cost
        return None, float('inf') 


# --- 2. Q-LEARNING  ---
class QLearningRouter:
    def __init__(self, G, source, target, demand):
        self.name = "Q-Learning (RL)"
        self.G = G
        self.source = source
        self.target = target
        # Q-Learning parametreleri (alpha, gamma, epsilon vb.)

    def run(self):
        # BURAYA Q-LEARNING KODUNU EKLE
        # time.sleep(0.5) # Simülasyon
        return None, float('inf') # (path, cost) döndürmeli


# --- 3. YAPAY ARI KOLONİSİ - ABC  ---
class ABCRouter:
    def __init__(self, G, source, target, demand):
        self.name = "Yapay Arı Kolonisi (ABC)"
        self.G = G
        self.source = source
        self.target = target

    def run(self):
        # BURAYA ABC KODUNU EKLE
        return None, float('inf')


# --- 4. BENZETİMLİ TAVLAMA - SA ---
class SimulatedAnnealingRouter:
    def __init__(self, G, source, target, demand):
        self.name = "Benzetimli Tavlama (SA)"
        self.G = G
        self.source = source
        self.target = target

    def run(self):
        # BURAYA SA KODUNU EKLE
        return None, float('inf')


# =============================================================================
# 4. KARŞILAŞTIRMA MOTORU
# =============================================================================
def run_comparison_test(scenario_id):
    G, df_demand = load_data()
    if G is None: return

    # Senaryo Kontrolü
    if scenario_id < 1 or scenario_id > len(df_demand):
        print(f"Hata: Geçersiz Senaryo ID (1-{len(df_demand)}).")
        return

    # Senaryo Verilerini Çek
    row = df_demand.iloc[scenario_id-1]
    src, dst, bw = int(row['src']), int(row['dst']), row['demand_mbps']

    print(f"\n{'='*80}")
    print(f"KARŞILAŞTIRMA ANALİZİ | Senaryo {scenario_id}: {src} -> {dst} (Talep: {bw} Mbps)")
    print(f"{'='*80}")
    print(f"{'Algoritma':<30} {'Durum':<10} {'Maliyet':<12} {'Süre(s)':<10} {'Yol Uzunluğu'}")
    print("-" * 80)

    # --- YARIŞACAK ALGORİTMALAR ---
    algorithms = [
        GeneticAlgorithmRouter(G, src, dst, bw),
        QLearningRouter(G, src, dst, bw),
        ABCRouter(G, src, dst, bw),
        SimulatedAnnealingRouter(G, src, dst, bw)
    ]

    results = []

    for algo in algorithms:
        start_time = time.time()
        
        try:
            # Her algoritmanın .run() metodu (path, cost) döndürmeli
            path, cost = algo.run()
            
            # Eğer algoritma kendi cost'unu hesaplamıyorsa, ortak hakem hesaplar:
            if path and (cost == 0 or cost == float('inf')):
                cost = calculate_fitness(G, path)

        except Exception as e:
            print(f"HATA ({algo.name}): {e}")
            path, cost = None, float('inf')

        duration = time.time() - start_time
        
        # Sonuçları Tabloya Bas
        status = "BAŞARILI" if path else "BAŞARISIZ"
        cost_str = f"{cost:.4f}" if path else "---"
        path_len = len(path) if path else 0
        
        print(f"{algo.name:<30} {status:<10} {cost_str:<12} {duration:.4f}      {path_len}")

        results.append({
            "Algoritma": algo.name,
            "Maliyet": cost,
            "Süre": duration
        })

    # --- KAZANANI BELİRLE ---
    print("-" * 80)
    successes = [r for r in results if r["Maliyet"] != float('inf')]
    
    if successes:
        # En düşük maliyetliyi bul
        best_cost = min(successes, key=lambda x: x["Maliyet"])
        print(f">>> EN İYİ SONUÇ: {best_cost['Algoritma']} (Maliyet: {best_cost['Maliyet']:.4f})")
    else:
        print(">>> KAZANAN YOK (Hiçbir algoritma geçerli yol bulamadı).")

if __name__ == "__main__":
    # Kullanıcıdan girdi al
    try:
        sid = int(input(f"Test edilecek Senaryo ID girin (1-30): "))
        run_comparison_test(sid)
    except ValueError:
        print("Lütfen sayı girin.")