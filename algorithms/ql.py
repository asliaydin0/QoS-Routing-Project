import pandas as pd
import networkx as nx
import numpy as np
import random
import time
import os

# =============================================================================
# 1. AYARLAR VE PARAMETRELER
# =============================================================================
DATA_FOLDER = "data"  # Verilerin bulunduğu klasör
NODE_FILE = "BSM307_317_Guz2025_TermProject_NodeData(in).csv"
EDGE_FILE = "BSM307_317_Guz2025_TermProject_EdgeData(in).csv"
DEMAND_FILE = "BSM307_317_Guz2025_TermProject_DemandData(in).csv"

# Q-Learning Hiperparametreleri
ALPHA = 0.1          # Öğrenme Oranı (Learning Rate)
GAMMA = 0.9          # Gelecek Ödül Çarpanı (Discount Factor)
EPSILON = 0.1        # Keşfetme Oranı (Exploration Rate)
EPISODES = 500       # Her senaryo için eğitim turu sayısı
REPETITIONS = 5      # Her senaryo için tekrar sayısı (İstatistik için)

# Optimizasyon Ağırlıkları (Toplam = 1.0)
W_DELAY = 0.33
W_RELIABILITY = 0.33
W_RESOURCE = 0.34

# =============================================================================
# 2. VERİ YÜKLEME VE GRAF OLUŞTURMA
# =============================================================================
def load_data():
    """CSV dosyalarını okur ve NetworkX grafını oluşturur."""
    print("Veri setleri yükleniyor...")
    
    def clean_float(x):
        if isinstance(x, str):
            return float(x.replace(',', '.'))
        return x

    try:
        # Kodun çalıştığı dizini baz alarak dosya yolunu bul
        base_path = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
        
        # Eğer 'datalar' klasörü script'in yanındaysa orayı kullan, yoksa direkt bak
        data_dir = os.path.join(base_path, DATA_FOLDER)
        if not os.path.exists(data_dir):
            data_dir = base_path # Datalar ana dizindeyse

        df_node = pd.read_csv(os.path.join(data_dir, NODE_FILE), sep=';')
        df_edge = pd.read_csv(os.path.join(data_dir, EDGE_FILE), sep=';')
        df_demand = pd.read_csv(os.path.join(data_dir, DEMAND_FILE), sep=';')
    except Exception as e:
        print(f"HATA: Dosya okuma hatası: {e}")
        return None, None

    # Veri Temizleme
    df_node['s_ms'] = df_node['s_ms'].apply(clean_float)
    df_node['r_node'] = df_node['r_node'].apply(clean_float)
    df_edge['r_link'] = df_edge['r_link'].apply(clean_float)
    df_edge['capacity_mbps'] = df_edge['capacity_mbps'].apply(clean_float)
    df_edge['delay_ms'] = df_edge['delay_ms'].apply(clean_float)

    # Graf Oluşturma
    G = nx.DiGraph()
    
    # Düğümler
    for _, row in df_node.iterrows():
        G.add_node(int(row['node_id']), 
                   proc_delay=row['s_ms'], 
                   reliability=row['r_node'])
    
    # Kenarlar
    for _, row in df_edge.iterrows():
        # Kapasite 0 ise hata vermemesi için minik bir değer ata
        bw = row['capacity_mbps'] if row['capacity_mbps'] > 0 else 0.1
        G.add_edge(int(row['src']), int(row['dst']), 
                   bandwidth=bw, 
                   link_delay=row['delay_ms'], 
                   reliability=row['r_link'])
    
    print(f"Graf Başarıyla Oluşturuldu: {G.number_of_nodes()} Node, {G.number_of_edges()} Edge.")
    return G, df_demand

# =============================================================================
# 3. Q-LEARNING ALGORİTMA SINIFI
# =============================================================================
class QLearningRouter:
    def __init__(self, G, source, target, demand):
        self.G = G
        self.source = source
        self.target = target
        self.demand = demand
        
        # Parametreler
        self.alpha = ALPHA
        self.gamma = GAMMA
        self.epsilon = EPSILON
        self.episodes = EPISODES
        
        # Q-Tablosu: Q[düğüm][komşu] -> Değer
        self.Q = {}
        self._initialize_q_table()

    def _initialize_q_table(self):
        """Ağdaki her düğüm ve komşusu için Q değerlerini 0 yapar."""
        for node in self.G.nodes():
            self.Q[node] = {}
            for neighbor in self.G.neighbors(node):
                self.Q[node][neighbor] = 0.0

    def calculate_fitness(self, path):
        """
        GA ile aynı maliyet fonksiyonu (Karşılaştırma için).
        """
        if not path or path[0] != self.source or path[-1] != self.target:
            return float('inf')

        total_delay = 0
        total_rel_log = 0 
        resource_cost = 0

        # Düğüm Maliyetleri
        if len(path) > 2:
            for node in path[1:-1]:
                if node not in self.G: return float('inf')
                d = self.G.nodes[node]
                total_delay += d.get('proc_delay', 0)
                r_node = d.get('reliability', 0.999)
                total_rel_log += -np.log(r_node if r_node > 0 else 1e-9)

        # Kenar Maliyetleri
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            if not self.G.has_edge(u, v): return float('inf')
            
            edge = self.G[u][v]
            total_delay += edge.get('link_delay', 0)
            
            r_link = edge.get('reliability', 0.999)
            total_rel_log += -np.log(r_link if r_link > 0 else 1e-9)
            
            bw = edge.get('bandwidth', 100)
            resource_cost += (1000.0 / bw)

        total_cost = (W_DELAY * total_delay) + \
                     (W_RELIABILITY * total_rel_log) + \
                     (W_RESOURCE * resource_cost)
        
        return total_cost

    def get_step_reward(self, u, v):
        """
        Bir adımdaki maliyetin negatifi ödüldür.
        Reward = - (Cost(u,v))
        """
        edge = self.G[u][v]
        node_v = self.G.nodes[v]
        
        # 1. Gecikme
        delay = edge.get('link_delay', 0) + node_v.get('proc_delay', 0)
        
        # 2. Güvenilirlik (Logaritmik Ceza)
        r_link = edge.get('reliability', 0.999)
        r_node = node_v.get('reliability', 0.999)
        rel_cost = -np.log(r_link if r_link > 0 else 1e-9) + \
                   -np.log(r_node if r_node > 0 else 1e-9)
        
        # 3. Kaynak
        bw = edge.get('bandwidth', 100)
        res_cost = (1000.0 / bw)
        
        step_cost = (W_DELAY * delay) + \
                    (W_RELIABILITY * rel_cost) + \
                    (W_RESOURCE * res_cost)
        
        # Hedefe ulaşmak büyük ödül, normal adım küçük ceza (maliyet)
        if v == self.target:
            return 1000.0 - step_cost
        else:
            return -step_cost

    def choose_action(self, current_node):
        """Epsilon-Greedy ile sonraki düğümü seç."""
        neighbors = list(self.G.neighbors(current_node))
        if not neighbors:
            return None
        
        # Keşfetme (Exploration)
        if random.random() < self.epsilon:
            return random.choice(neighbors)
        
        # Sömürme (Exploitation) - En iyi Q değerine git
        # Eğer Q değerleri eşitse rastgele seç (argmax'ın rastgele versiyonu)
        q_values = [self.Q[current_node][n] for n in neighbors]
        max_q = max(q_values)
        
        # En iyi olanların hepsini bul (eşitlik durumunda)
        best_candidates = [n for n, q in zip(neighbors, q_values) if q == max_q]
        return random.choice(best_candidates)

    def train(self):
        """Ajanı eğitir."""
        for episode in range(self.episodes):
            curr = self.source
            steps = 0
            
            while curr != self.target and steps < 250:
                nxt = self.choose_action(curr)
                if nxt is None: break # Çıkmaz sokak
                
                # Ödülü al
                reward = self.get_step_reward(curr, nxt)
                
                # Bellman Denklemi
                old_q = self.Q[curr][nxt]
                
                # Gelecekteki max Q
                next_neighbors = list(self.G.neighbors(nxt))
                if next_neighbors:
                    future_q = max([self.Q[nxt][n] for n in next_neighbors])
                else:
                    future_q = 0.0
                
                # Güncelleme
                new_q = old_q + self.alpha * (reward + (self.gamma * future_q) - old_q)
                self.Q[curr][nxt] = new_q
                
                curr = nxt
                steps += 1

    def reconstruct_path(self):
        """Eğitimden sonra Q tablosuna bakarak en iyi yolu çizer (Greedy)."""
        path = [self.source]
        curr = self.source
        visited = {self.source}
        
        while curr != self.target:
            neighbors = list(self.G.neighbors(curr))
            if not neighbors: return None
            
            # Döngüye girmemek için ziyaret edilmemişlerden en iyisini seç
            valid_neighbors = [n for n in neighbors if n not in visited]
            if not valid_neighbors: return None
            
            # En yüksek Q değerine sahip komşuyu seç
            nxt = max(valid_neighbors, key=lambda n: self.Q[curr].get(n, -float('inf')))
            
            path.append(nxt)
            visited.add(nxt)
            curr = nxt
            
            if len(path) > 250: return None
            
        return path

    def run(self):
        """Dışarıdan çağrılan ana metod."""
        self.train()
        best_path = self.reconstruct_path()
        
        if best_path:
            cost = self.calculate_fitness(best_path)
            return best_path, cost
        else:
            return None, float('inf')

# =============================================================================
# 4. GITHUB VE TEST UYUMLULUĞU İÇİN WRAPPER FONKSİYON
# =============================================================================
def find_ql_path(G, src=None, dst=None, demand=0, seed=None, **kwargs):
    """
    Q-Learning için köprü fonksiyonu (GA ile aynı imza).
    """
    if src is None: src = kwargs.get('start')
    if dst is None: dst = kwargs.get('goal')
    
    if src is None or dst is None:
        return None, float('inf'), {}

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    ql = QLearningRouter(G, src, dst, demand)
    path, cost = ql.run()
    
    # Metrics şimdilik boş
    return path, cost, {}

# =============================================================================
# 5. ANA ÇALIŞTIRMA VE RAPORLAMA BLOĞU
# =============================================================================
if __name__ == "__main__":
    G, df_demand = load_data()
    
    if G is not None:
        experiment_results = []
        
        print("\n" + "="*80)
        print(f"Q-LEARNING DENEYİ BAŞLIYOR: {len(df_demand)} Senaryo x {REPETITIONS} Tekrar")
        print("="*80 + "\n")
        
        total_scenarios = len(df_demand)
        
        for idx, row in df_demand.iterrows():
            src = int(row['src'])
            dst = int(row['dst'])
            demand = row['demand_mbps']
            
            costs = []
            times = []
            best_path_str = "Yok"
            
            print(f"[{idx+1}/{total_scenarios}] Senaryo: {src} -> {dst} ({demand} Mbps)...")
            
            for rep in range(REPETITIONS):
                start_time = time.time()
                
                ql = QLearningRouter(G, src, dst, demand)
                path, cost = ql.run()
                
                duration = time.time() - start_time
                
                if path:
                    costs.append(cost)
                    times.append(duration)
                    if cost == min(costs):
                        best_path_str = str(path)
                else:
                    costs.append(float('inf'))
                    times.append(duration)

            valid_costs = [c for c in costs if c != float('inf')]
            
            if valid_costs:
                mean_val = np.mean(valid_costs)
                std_val = np.std(valid_costs)
                best_val = np.min(valid_costs)
                worst_val = np.max(valid_costs)
                avg_time = np.mean(times)
                status = "SUCCESS"
            else:
                mean_val = std_val = best_val = worst_val = avg_time = 0
                status = "FAIL"

            experiment_results.append({
                "Scenario_ID": idx + 1,
                "Source": src,
                "Destination": dst,
                "Demand_Mbps": demand,
                "Status": status,
                "Mean_Cost": round(mean_val, 4),
                "Std_Dev": round(std_val, 4),
                "Best_Cost": round(best_val, 4),
                "Worst_Cost": round(worst_val, 4),
                "Avg_Time_Sec": round(avg_time, 4),
                "Best_Path_Found": best_path_str
            })
            
            if status == "SUCCESS":
                print(f"   >>> Tamamlandı. En İyi: {best_val:.4f}, Ort. Süre: {avg_time:.3f}s")
            else:
                print(f"   >>> BAŞARISIZ (Yol Bulunamadı)")

        output_file = "Q_Learning_Sonuclar.csv"
        df_res = pd.DataFrame(experiment_results)
        df_res.to_csv(output_file, sep=';', index=False)
        
        print("\n" + "="*80)
        print(f"SONUÇLAR KAYDEDİLDİ: {output_file}")
        print("="*80)