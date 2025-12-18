import pandas as pd
import networkx as nx
import random
import copy
import time
import numpy as np
import argparse
import sys
import os

# ==========================================
# 1. AĞ YÖNETİCİSİ (VERİ VE GRAF İŞLEMLERİ)
# ==========================================
class NetworkManager:
    """
    CSV dosyalarını okur, NetworkX grafını oluşturur ve
    kapasite/kısıt yönetimini sağlar.
    """
    def __init__(self, node_file, edge_file):
        self.node_file = node_file
        self.edge_file = edge_file
        self.G = nx.DiGraph()
        self._load_data()

    def _clean_float(self, x):
        """Virgüllü string sayıları (0,95) float'a (0.95) çevirir."""
        if isinstance(x, str):
            return float(x.replace(',', '.'))
        return x

    def _load_data(self):
        try:
            # Dosyaları noktalı virgül ile oku
            node_df = pd.read_csv(self.node_file, sep=';')
            edge_df = pd.read_csv(self.edge_file, sep=';')
        except FileNotFoundError as e:
            print(f"\n[KRİTİK HATA] Veri dosyası bulunamadı!")
            print(f"Aranan Yol: {self.node_file}")
            print(f"Sistem Hatası: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n[KRİTİK HATA] Dosya okunurken beklenmedik bir hata oluştu: {e}")
            sys.exit(1)

        # Node verilerini temizle ve ekle
        for col in ['s_ms', 'r_node']:
            node_df[col] = node_df[col].apply(self._clean_float)
        
        for _, row in node_df.iterrows():
            self.G.add_node(int(row['node_id']), 
                            processing_delay=row['s_ms'], 
                            reliability=row['r_node'])

        # Edge verilerini temizle ve ekle
        for col in ['r_link']:
            edge_df[col] = edge_df[col].apply(self._clean_float)
            
        for _, row in edge_df.iterrows():
            self.G.add_edge(int(row['src']), int(row['dst']), 
                            capacity=row['capacity_mbps'], 
                            delay=row['delay_ms'], 
                            reliability=row['r_link'],
                            original_capacity=row['capacity_mbps'])
        
        print(f"[NetworkManager] Graf başarıyla oluşturuldu: {self.G.number_of_nodes()} Düğüm, {self.G.number_of_edges()} Kenar.")

    def get_graph(self):
        return self.G

    def check_node_exists(self, node_id):
        """Düğümün var olup olmadığını kontrol eder."""
        return node_id in self.G.nodes

    def check_connectivity(self, src, dst):
        """İki düğüm arasında teorik olarak bir yol var mı bakar (Kapasitesiz)."""
        return nx.has_path(self.G, src, dst)

# ==========================================
# 2. ARI ALGORİTMASI YÖNETİCİSİ (ABC LOGIC)
# ==========================================
class ABC_Manager:
    """
    Yapay Arı Kolonisi (ABC) algoritmasını çalıştırır.
    GUI ve Test ekibi için optimize edilmiş ve detaylı hata raporlaması eklenmiştir.
    """
    def __init__(self, graph_manager):
        self.manager = graph_manager
        self.G = graph_manager.get_graph()
        
        # Varsayılan Algoritma Parametreleri
        self.params = {
            'pop_size': 20,      # Popülasyon (Besin Kaynağı) Sayısı
            'max_iter': 50,      # Maksimum İterasyon
            'limit': 5,          # Gelişmeme Limiti (Limit değeri)
            'w_delay': 0.4,      # Gecikme Ağırlığı
            'w_rel': 0.4,        # Güvenilirlik Ağırlığı
            'w_hop': 0.2         # Hop (Sıçrama) Ağırlığı
        }

    def set_params(self, **kwargs):
        """Dışarıdan (GUI/Terminal) parametre güncellemek için."""
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

    def calculate_fitness(self, path):
        """
        QoS Fitness Fonksiyonu (Minimizasyon)
        Düşük Puan = Daha İyi Rota
        """
        if not path:
            return float('inf'), 0, 0

        total_delay = 0
        total_reliability = 1.0
        
        # Link maliyetleri
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            try:
                data = self.G[u][v]
                total_delay += data['delay']
                total_reliability *= data['reliability']
            except KeyError:
                return float('inf'), 0, 0 
            
        # Node maliyetleri
        for node in path:
            data = self.G.nodes[node]
            total_delay += data['processing_delay']
            total_reliability *= data['reliability']

        # Güvenilirlik Maliyeti: (1 - Reliability) * 1000
        reliability_cost = (1.0 - total_reliability) * 1000
        
        # Weighted Sum
        score = (self.params['w_delay'] * total_delay) + \
                (self.params['w_rel'] * reliability_cost) + \
                (self.params['w_hop'] * len(path) * 10)
        
        return score, total_delay, total_reliability

    def _random_path_weighted(self, src, dst, demand):
        """
        HIZLANDIRILMIŞ RANDOM PATH (Randomized Dijkstra)
        """
        valid_edges = [(u, v, d) for u, v, d in self.G.edges(data=True) if d['capacity'] >= demand]
        if not valid_edges: return None
        
        temp_G = nx.DiGraph()
        for u, v, d in valid_edges:
            temp_G.add_edge(u, v, weight=random.randint(1, 100))
            
        try:
            return nx.shortest_path(temp_G, source=src, target=dst, weight='weight')
        except nx.NetworkXNoPath:
            return None

    def _mutate(self, path, src, dst, demand):
        """
        MUTASYON: Rotayı kopar ve onar.
        """
        if len(path) <= 2: return path
        
        pivot_idx = random.randint(0, len(path) - 2)
        pivot_node = path[pivot_idx]
        
        new_tail = self._random_path_weighted(pivot_node, dst, demand)
        
        if new_tail:
            new_path = path[:pivot_idx] + new_tail
            if len(new_path) == len(set(new_path)): # Döngü kontrolü
                return new_path
        
        return path 

    def run_algorithm_generator(self, src, dst, demand):
        """
        GUI İÇİN GENERATOR FONKSİYONU (Yield)
        Detaylı hata kontrolleri içerir.
        """
        # --- 0. Ön Kontroller (Detaylı Hata Mesajları İçin) ---
        if not self.manager.check_node_exists(src):
            yield {'status': 'failed', 'message': f"Kaynak Düğüm (ID: {src}) veri setinde bulunamadı!"}
            return
        if not self.manager.check_node_exists(dst):
            yield {'status': 'failed', 'message': f"Hedef Düğüm (ID: {dst}) veri setinde bulunamadı!"}
            return
        if not self.manager.check_connectivity(src, dst):
             yield {'status': 'failed', 'message': f"Graf üzerinde {src} -> {dst} arasında fiziksel bir bağlantı yok (Kapasiteden bağımsız)."}
             return

        # --- 1. Başlangıç (Initialization) ---
        population = []
        for _ in range(self.params['pop_size']):
            p = self._random_path_weighted(src, dst, demand)
            if p:
                fit, d, r = self.calculate_fitness(p)
                population.append({'path': p, 'fit': fit, 'd': d, 'r': r, 'trial': 0})

        if not population:
            # Buraya düştüyse fiziksel yol var ama kapasite yetmiyor demektir.
            yield {'status': 'failed', 'message': f"Kapasite Yetersiz! {src}->{dst} arasında {demand} Mbps taşıyabilecek uygun bir rota bulunamadı."}
            return

        best_sol = min(population, key=lambda x: x['fit'])
        history = [best_sol['fit']]

        # --- 2. Ana Döngü ---
        for iter_no in range(self.params['max_iter']):
            
            # A) İşçi Arılar
            for i in range(len(population)):
                new_path = self._mutate(population[i]['path'], src, dst, demand)
                fit, d, r = self.calculate_fitness(new_path)
                if fit < population[i]['fit']:
                    population[i] = {'path': new_path, 'fit': fit, 'd': d, 'r': r, 'trial': 0}
                else:
                    population[i]['trial'] += 1

            # B) Gözcü Arılar (Rulet)
            fitness_values = [1.0 / (ind['fit'] + 1e-9) for ind in population]
            total_fit = sum(fitness_values)
            probs = [f / total_fit for f in fitness_values]
            
            for _ in range(self.params['pop_size']):
                idx = np.random.choice(range(len(population)), p=probs)
                new_path = self._mutate(population[idx]['path'], src, dst, demand)
                fit, d, r = self.calculate_fitness(new_path)
                if fit < population[idx]['fit']:
                    population[idx] = {'path': new_path, 'fit': fit, 'd': d, 'r': r, 'trial': 0}
                else:
                    population[idx]['trial'] += 1

            # C) Kaşif Arılar
            for i in range(len(population)):
                if population[i]['trial'] > self.params['limit']:
                    p = self._random_path_weighted(src, dst, demand)
                    if p:
                        fit, d, r = self.calculate_fitness(p)
                        population[i] = {'path': p, 'fit': fit, 'd': d, 'r': r, 'trial': 0}

            # En iyiyi güncelle
            current_best = min(population, key=lambda x: x['fit'])
            if current_best['fit'] < best_sol['fit']:
                best_sol = copy.deepcopy(current_best)
            
            history.append(best_sol['fit'])

            yield {
                'status': 'running',
                'iteration': iter_no + 1,
                'max_iter': self.params['max_iter'],
                'current_best_fitness': best_sol['fit'],
                'current_best_path': best_sol['path'],
                'history': history
            }

        yield {
            'status': 'completed',
            'result': {
                'path': best_sol['path'],
                'total_delay': round(best_sol['d'], 2),
                'total_reliability': round(best_sol['r'], 4),
                'fitness': round(best_sol['fit'], 2),
                'hop_count': len(best_sol['path']) - 1,
                'convergence_history': history
            }
        }

# ==========================================
# 3. PATH AYARLARI VE MAIN (KRİTİK KISIM)
# ==========================================
if __name__ == "__main__":
    
    # --- DİNAMİK DOSYA YOLU BULMA ---
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, 'data')

    node_path = os.path.join(data_dir, "BSM307_317_Guz2025_TermProject_NodeData(in).csv")
    edge_path = os.path.join(data_dir, "BSM307_317_Guz2025_TermProject_EdgeData(in).csv")
    
    # Hızlı Kontrol: Data klasörü var mı?
    if not os.path.exists(node_path):
        print("\n[HATA] Veri dosyaları bulunamıyor!")
        print(f"Beklenen Konum: {data_dir}")
        print("Lütfen projenin 'algorithms' ve 'data' klasörlerini içeren ana klasörde olduğundan emin ol.")
        sys.exit(1)
        
    # --- ARGÜMAN PARSER ---
    parser = argparse.ArgumentParser(description="ABC QoS Rotalama Algoritması")
    parser.add_argument('--src', type=int, help="Kaynak Düğüm ID", default=8)
    parser.add_argument('--dst', type=int, help="Hedef Düğüm ID", default=44)
    parser.add_argument('--demand', type=float, help="İstenen Bant Genişliği", default=200)
    
    parser.add_argument('--node_file', type=str, default=node_path)
    parser.add_argument('--edge_file', type=str, default=edge_path)
    
    args = parser.parse_args()

    print("\n" + "="*60)
    print(f"📂 Veri Yolu     : {data_dir}")
    print(f"⚙️  Parametreler  : Kaynak={args.src}, Hedef={args.dst}, Talep={args.demand} Mbps")
    print("🐝 YAPAY ARI KOLONİSİ (ABC) BAŞLATILIYOR...")
    print("="*60)

    net_manager = NetworkManager(args.node_file, args.edge_file)
    abc_manager = ABC_Manager(net_manager)
    
    start_time = time.time()
    
    # Generator başlatılıyor
    generator = abc_manager.run_algorithm_generator(args.src, args.dst, args.demand)
    
    final_result = None
    
    print("\n[İşlem Durumu]")
    for update in generator:
        if update['status'] == 'running':
            # Her 10 adımda bir veya ilk adımda bilgi ver
            if update['iteration'] % 10 == 0 or update['iteration'] == 1:
                print(f" >> Iter: {update['iteration']}/{update['max_iter']} | En İyi Fitness: {update['current_best_fitness']:.2f}")
        
        elif update['status'] == 'completed':
            final_result = update['result']
        
        elif update['status'] == 'failed':
            print("\n" + "!"*40)
            print("🛑 İŞLEM BAŞARISIZ OLDU")
            print(f"Hata Detayı: {update['message']}")
            print("!"*40)
            sys.exit(0)

    total_time = time.time() - start_time

    if final_result:
        print("\n" + "="*60)
        print("✅ SONUÇ BAŞARIYLA BULUNDU!")
        print("="*60)
        print(f"📍 Rota              : {final_result['path']}")
        print(f"⏱️  Toplam Gecikme    : {final_result['total_delay']} ms")
        print(f"🛡️  Toplam Güvenilirlik: %{final_result['total_reliability']*100:.4f}")
        print(f"🏆 Fitness Skoru     : {final_result['fitness']}")
        print(f"⏳ Hesaplama Süresi  : {total_time:.4f} saniye")
        print("="*60)