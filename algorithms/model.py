import pandas as pd
import numpy as np
import networkx as nx
import random
import copy
import time
import argparse
import sys

# ==========================================
# 1. VERİ YÖNETİMİ VE GRAF OLUŞTURMA
# ==========================================
class NetworkManager:
    def __init__(self, node_file, edge_file):
        try:
            self.node_df = pd.read_csv(node_file, sep=';')
            self.edge_df = pd.read_csv(edge_file, sep=';')
        except FileNotFoundError as e:
            print(f"HATA: Veri dosyaları bulunamadı! ({e})")
            sys.exit(1)
            
        self.G = nx.DiGraph()
        self._build_graph()

    def _clean_float(self, x):
        """Virgüllü string sayıları (0,95) float'a (0.95) çevirir."""
        if isinstance(x, str):
            return float(x.replace(',', '.'))
        return x

    def _build_graph(self):
        # Node verilerini temizle ve ekle
        for col in ['s_ms', 'r_node']:
            self.node_df[col] = self.node_df[col].apply(self._clean_float)
        
        for _, row in self.node_df.iterrows():
            self.G.add_node(int(row['node_id']), 
                            processing_delay=row['s_ms'], 
                            reliability=row['r_node'])

        # Edge verilerini temizle ve ekle
        for col in ['r_link']:
            self.edge_df[col] = self.edge_df[col].apply(self._clean_float)
            
        for _, row in self.edge_df.iterrows():
            self.G.add_edge(int(row['src']), int(row['dst']), 
                            capacity=row['capacity_mbps'], 
                            delay=row['delay_ms'], 
                            reliability=row['r_link'],
                            original_capacity=row['capacity_mbps'])

    def get_graph(self):
        return self.G

# ==========================================
# 2. ARI ALGORİTMASI (ABC)
# ==========================================
class ABC_Routing:
    def __init__(self, graph, pop_size=20, max_iter=50, limit=5):
        self.G = graph
        self.pop_size = pop_size     
        self.max_iter = max_iter     
        self.limit = limit           
        
        # Ağırlıklar (QoS Metrikleri)
        self.w_delay = 0.4
        self.w_reliability = 0.4
        self.w_hop = 0.2

    def calculate_fitness(self, path):
        """
        QoS Hesaplama:
        - Toplam Gecikme (Link + Node) -> Minimize
        - Toplam Güvenilirlik (Link * Node) -> Maximize
        """
        if not path:
            return float('inf'), 0, 0, 0

        total_delay = 0
        total_reliability = 1.0
        
        # Link maliyetleri
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            data = self.G[u][v]
            total_delay += data['delay']
            total_reliability *= data['reliability']
            
        # Node maliyetleri
        for node in path:
            data = self.G.nodes[node]
            total_delay += data['processing_delay']
            total_reliability *= data['reliability']

        # Güvenilirliği maliyet fonksiyonuna çevir (1 - Rel)
        reliability_cost = (1.0 - total_reliability) * 1000
        
        # Fitness Skoru (Düşük olan daha iyi)
        score = (self.w_delay * total_delay) + \
                (self.w_reliability * reliability_cost) + \
                (self.w_hop * len(path) * 10) 
        
        return score, total_delay, total_reliability, len(path)

    def find_random_path(self, src, dst, demand):
        """Kapasite kontrollü rastgele yol bulucu (Randomized Dijkstra)"""
        valid_edges = [(u, v, d) for u, v, d in self.G.edges(data=True) if d['capacity'] >= demand]
        if not valid_edges:
            return None
        
        temp_G = nx.DiGraph()
        for u, v, d in valid_edges:
            # Rastgele ağırlık vererek çeşitlilik sağla
            temp_G.add_edge(u, v, weight=random.randint(1, 100))
            
        try:
            return nx.shortest_path(temp_G, source=src, target=dst, weight='weight')
        except nx.NetworkXNoPath:
            return None

    def mutate_path(self, path, src, dst, demand):
        """Mevcut yolu mutasyona uğratarak komşu çözüm üretir"""
        if len(path) <= 2: return path
            
        pivot_idx = random.randint(0, len(path) - 2)
        pivot_node = path[pivot_idx]
        
        valid_edges = [(u, v, d) for u, v, d in self.G.edges(data=True) if d['capacity'] >= demand]
        temp_G = nx.DiGraph()
        for u, v, d in valid_edges:
            temp_G.add_edge(u, v, weight=random.randint(1, 100))
            
        try:
            new_tail = nx.shortest_path(temp_G, source=pivot_node, target=dst, weight='weight')
            new_path = path[:pivot_idx] + new_tail
            if len(new_path) == len(set(new_path)): # Döngü kontrolü
                return new_path
        except:
            pass
        return path

    def solve(self, src, dst, demand):
        # 1. Başlangıç (Initialization)
        population = [] 
        for _ in range(self.pop_size):
            path = self.find_random_path(src, dst, demand)
            if path:
                fit, d, r, h = self.calculate_fitness(path)
                population.append({'path': path, 'fitness': fit, 'delay': d, 'rel': r, 'trial': 0})
        
        if not population:
            return None 
            
        best_sol = min(population, key=lambda x: x['fitness'])

        # 2. Döngü
        for iter_no in range(self.max_iter):
            # --- Employed Bees ---
            for i in range(len(population)):
                new_path = self.mutate_path(population[i]['path'], src, dst, demand)
                fit, d, r, h = self.calculate_fitness(new_path)
                if fit < population[i]['fitness']:
                    population[i] = {'path': new_path, 'fitness': fit, 'delay': d, 'rel': r, 'trial': 0}
                else:
                    population[i]['trial'] += 1

            # --- Onlooker Bees ---
            total_fitness_inv = sum(1.0 / (sol['fitness'] + 1e-9) for sol in population)
            probs = [(1.0 / (sol['fitness'] + 1e-9)) / total_fitness_inv for sol in population]
            
            for _ in range(self.pop_size):
                idx = np.random.choice(range(len(population)), p=probs)
                sol = population[idx]
                new_path = self.mutate_path(sol['path'], src, dst, demand)
                fit, d, r, h = self.calculate_fitness(new_path)
                if fit < sol['fitness']:
                    population[idx] = {'path': new_path, 'fitness': fit, 'delay': d, 'rel': r, 'trial': 0}
                else:
                    population[idx]['trial'] += 1

            # --- Scout Bees ---
            for i in range(len(population)):
                if population[i]['trial'] > self.limit:
                    new_path = self.find_random_path(src, dst, demand)
                    if new_path:
                        fit, d, r, h = self.calculate_fitness(new_path)
                        population[i] = {'path': new_path, 'fitness': fit, 'delay': d, 'rel': r, 'trial': 0}

            current_best = min(population, key=lambda x: x['fitness'])
            if current_best['fitness'] < best_sol['fitness']:
                best_sol = copy.deepcopy(current_best)

        return best_sol

# ==========================================
# 3. TERMİNAL PARAMETRE YÖNETİMİ
# ==========================================
def main():
    # Terminalden argümanları okuyan yapı
    parser = argparse.ArgumentParser(description="ABC Algoritması ile QoS Rotalama Testi")
    
    # Parametre tanımları
    parser.add_argument('--src', type=int, required=True, help="Kaynak Düğüm ID (Örn: 8)")
    parser.add_argument('--dst', type=int, required=True, help="Hedef Düğüm ID (Örn: 44)")
    parser.add_argument('--demand', type=float, required=True, help="Talep edilen Bant Genişliği Mbps (Örn: 200)")
    parser.add_argument('--pop_size', type=int, default=20, help="Arı Sayısı (Varsayılan: 20)")
    parser.add_argument('--iter', type=int, default=50, help="İterasyon Sayısı (Varsayılan: 50)")

    args = parser.parse_args()

    print("\n" + "="*50)
    print(f"🚀 ABC ALGORİTMASI BAŞLATILIYOR")
    print("="*50)
    print(f"📌 Kaynak (Source): {args.src}")
    print(f"🎯 Hedef (Dest)   : {args.dst}")
    print(f"📦 Talep (Demand) : {args.demand} Mbps")
    print("-" * 50)

    # Grafı Yükle
    manager = NetworkManager(
        'BSM307_317_Guz2025_TermProject_NodeData(in).csv', 
        'BSM307_317_Guz2025_TermProject_EdgeData(in).csv'
    )
    
    # Kaynak ve Hedef kontrolü
    if args.src not in manager.G.nodes or args.dst not in manager.G.nodes:
        print("❌ HATA: Girilen düğüm ID'leri verisetinde bulunamadı!")
        return

    # Algoritmayı Çalıştır
    abc = ABC_Routing(manager.get_graph(), pop_size=args.pop_size, max_iter=args.iter, limit=5)
    
    start_time = time.time()
    solution = abc.solve(args.src, args.dst, args.demand)
    end_time = time.time()

    # Sonuçları Yazdır
    print("\n✅ SONUÇLAR:")
    if solution:
        print(f"🔹 Bulunan Rota: {solution['path']}")
        print(f"⏱️  Toplam Gecikme (Delay): {solution['delay']:.2f} ms")
        print(f"🛡️  Toplam Güvenilirlik   : %{solution['rel']*100:.4f}")
        print(f"👟 Hop Sayısı (Adım)     : {len(solution['path'])-1}")
        print(f"🏆 Fitness Skoru         : {solution['fitness']:.4f}")
        print(f"⏳ Hesaplama Süresi      : {end_time - start_time:.4f} saniye")
    else:
        print("❌ ROTA BULUNAMADI!")
        print("Muhtemel Sebepler:")
        print("1. İstenen bant genişliğini (Mbps) karşılayacak bir yol yok.")
        print("2. Kaynak ve hedef arasında bağlantı kopuk.")

    print("="*50 + "\n")

if __name__ == "__main__":
    main()