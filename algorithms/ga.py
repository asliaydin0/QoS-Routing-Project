import pandas as pd
import networkx as nx
import numpy as np
import random
import time
import os

# =============================================================================
# 1. AYARLAR VE PARAMETRELER
# =============================================================================
DATA_FOLDER = "datalar"  # Verilerin bulunduğu klasör
NODE_FILE = "BSM307_317_Guz2025_TermProject_NodeData.csv"
EDGE_FILE = "BSM307_317_Guz2025_TermProject_EdgeData.csv"
DEMAND_FILE = "BSM307_317_Guz2025_TermProject_DemandData.csv"

# Genetik Algoritma Hiperparametreleri
POPULATION_SIZE = 60      # Popülasyon büyüklüğü
GENERATIONS = 100         # Jenerasyon sayısı
MUTATION_RATE = 0.3       # Mutasyon olasılığı
ELITISM_COUNT = 4         # Her nesilde korunan en iyi birey sayısı
REPETITIONS = 5           # Her senaryo için tekrar sayısı (Hocanın isteği: 5)

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
        df_node = pd.read_csv(os.path.join(DATA_FOLDER, NODE_FILE), sep=';')
        df_edge = pd.read_csv(os.path.join(DATA_FOLDER, EDGE_FILE), sep=';')
        df_demand = pd.read_csv(os.path.join(DATA_FOLDER, DEMAND_FILE), sep=';')
    except FileNotFoundError:
        print("HATA: CSV dosyaları bulunamadı. Lütfen dosya yollarını kontrol edin.")
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
# 3. GENETİK ALGORİTMA SINIFI
# =============================================================================
class GeneticAlgorithmRouter:
    def __init__(self, G, source, target, demand):
        self.G = G
        self.source = source
        self.target = target
        self.demand = demand
        self.population = [] # Liste: (cost, path) tuple'ları

    def calculate_fitness(self, path):
        """
        Proje dokümanındaki formüllere göre Maliyet (Cost) hesaplar.
        Düşük Maliyet = Yüksek Fitness
        """
        # 1. Yol Geçerliliği Kontrolü
        if not path or path[0] != self.source or path[-1] != self.target:
            return float('inf')

        total_delay = 0
        total_rel_log = 0 # Logaritmik toplam (Çarpım yerine)
        resource_cost = 0

        # 2. Düğüm Maliyetleri (Ara düğümler)
        if len(path) > 2:
            for node in path[1:-1]:
                if node not in self.G: return float('inf')
                d = self.G.nodes[node]
                total_delay += d.get('proc_delay', 0)
                # Güvenilirlik maliyeti: -log(R)
                r_node = d.get('reliability', 0.999)
                total_rel_log += -np.log(r_node if r_node > 0 else 1e-9)

        # 3. Kenar (Link) Maliyetleri
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            if not self.G.has_edge(u, v):
                return float('inf') # Bağlantı kopuk
            
            edge = self.G[u][v]
            
            # Bant genişliği kontrolü (Opsiyonel: Katı kısıt istenirse açılabilir)
            # if edge['bandwidth'] < self.demand: return float('inf')

            total_delay += edge.get('link_delay', 0)
            
            r_link = edge.get('reliability', 0.999)
            total_rel_log += -np.log(r_link if r_link > 0 else 1e-9)
            
            # Kaynak Maliyeti: 1000 / BW
            bw = edge.get('bandwidth', 100)
            resource_cost += (1000.0 / bw)

        # 4. Toplam Ağırlıklı Maliyet (Weighted Sum)
        total_cost = (W_DELAY * total_delay) + \
                     (W_RELIABILITY * total_rel_log) + \
                     (W_RESOURCE * resource_cost)
        
        return total_cost

    def generate_random_path(self):
        """DFS tabanlı rastgele geçerli yol oluşturucu."""
        path = [self.source]
        current = self.source
        visited = {self.source}
        
        while current != self.target:
            neighbors = [n for n in self.G.neighbors(current) if n not in visited]
            
            if not neighbors:
                return None # Çıkmaz sokak (Dead end)
            
            # Hedef komşulardaysa oraya gitme şansını artır
            if self.target in neighbors:
                next_node = self.target
            else:
                next_node = random.choice(neighbors)
            
            path.append(next_node)
            visited.add(next_node)
            
            # Çok uzun yolları engelle (Performans için)
            if len(path) > 250: 
                return None
            
            current = next_node
            
        return path

    def initialize_population(self):
        """Başlangıç popülasyonunu oluşturur."""
        self.population = []
        attempts = 0
        max_attempts = POPULATION_SIZE * 10
        
        # En kısa yolu ekleyerek kaliteyi artır (Heuristic Seeding)
        try:
            sp = nx.shortest_path(self.G, self.source, self.target, weight='delay')
            self.population.append((self.calculate_fitness(sp), sp))
        except:
            pass # Yol yoksa geç

        # Rastgele yollarla doldur
        while len(self.population) < POPULATION_SIZE and attempts < max_attempts:
            path = self.generate_random_path()
            if path:
                cost = self.calculate_fitness(path)
                if cost != float('inf'):
                    self.population.append((cost, path))
            attempts += 1
        
        # Maliyete göre sırala (Küçükten büyüğe)
        self.population.sort(key=lambda x: x[0])

    def crossover(self, parent1, parent2):
        """
        Path-Based Crossover: İki yolun ortak bir düğümünü bulur ve yolları takas eder.
        """
        # Baş ve son hariç ortak düğümler
        common = list(set(parent1[1:-1]) & set(parent2[1:-1]))
        
        if not common:
            return parent1 # Ortak nokta yoksa kopyala geç
        
        pivot = random.choice(common)
        
        # P1'in başı + P2'nin sonu
        idx1 = parent1.index(pivot)
        idx2 = parent2.index(pivot)
        
        child = parent1[:idx1] + parent2[idx2:]
        
        # Döngü kontrolü (Loop check)
        if len(child) != len(set(child)):
            return parent1
            
        return child

    def mutate(self, path):
        """
        Path Repair Mutation: Yolun bir kısmını silip yeniden rastgele rotalar.
        """
        if len(path) < 4: return path
        
        # Rastgele bir kopma noktası seç
        cut_point = random.randint(1, len(path)-2)
        node = path[cut_point]
        
        # O noktadan hedefe yeni bir yol bulmaya çalış
        # (Basit bir random walk ile tamamla)
        partial_path = path[:cut_point+1]
        current = node
        visited = set(partial_path)
        
        # Maksimum 50 adımda hedefe gitmeyi dene
        for _ in range(50):
            if current == self.target:
                return partial_path
                
            neighbors = [n for n in self.G.neighbors(current) if n not in visited]
            if not neighbors:
                return path # Başarısız olursa orijinali döndür
            
            if self.target in neighbors:
                current = self.target
            else:
                current = random.choice(neighbors)
            
            partial_path.append(current)
            visited.add(current)
            
        return path # Hedefe ulaşamazsa orijinali döndür

    def run(self):
        """Algoritmayı çalıştırır ve en iyi sonucu döndürür."""
        self.initialize_population()
        
        if not self.population:
            return None, float('inf')

        for gen in range(GENERATIONS):
            new_pop = []
            
            # 1. Elitism: En iyileri koru
            new_pop.extend(self.population[:ELITISM_COUNT])
            
            # 2. Yeni nesil üretimi
            while len(new_pop) < POPULATION_SIZE:
                # Turnuva Seçimi (Tournament Selection)
                candidates = random.sample(self.population, 5)
                candidates.sort(key=lambda x: x[0])
                parent1 = candidates[0][1]
                
                candidates = random.sample(self.population, 5)
                candidates.sort(key=lambda x: x[0])
                parent2 = candidates[0][1]
                
                # Crossover
                child = self.crossover(parent1, parent2)
                
                # Mutation
                if random.random() < MUTATION_RATE:
                    child = self.mutate(child)
                
                cost = self.calculate_fitness(child)
                if cost != float('inf'):
                    new_pop.append((cost, child))
            
            # Popülasyonu güncelle ve sırala
            self.population = sorted(new_pop, key=lambda x: x[0])
            
            # (Opsiyonel) Eğer en iyi çözüm 10 jenerasyondur değişmiyorsa durdurulabilir.

        best_solution = self.population[0]
        return best_solution[1], best_solution[0]

# =============================================================================
# 4. ANA ÇALIŞTIRMA VE RAPORLAMA BLOĞU
# =============================================================================
if __name__ == "__main__":
    G, df_demand = load_data()
    
    if G is not None:
        experiment_results = []
        
        print("\n" + "="*80)
        print(f"DENEY BAŞLIYOR: Toplam {len(df_demand)} Senaryo, Her biri {REPETITIONS} tekrar.")
        print("="*80 + "\n")
        
        total_scenarios = len(df_demand)
        
        for idx, row in df_demand.iterrows():
            src = int(row['src'])
            dst = int(row['dst'])
            demand = row['demand_mbps']
            
            scenario_costs = []
            scenario_times = []
            best_path_str = "Yok"
            
            print(f"[{idx+1}/{total_scenarios}] Senaryo: {src} -> {dst} ({demand} Mbps) işleniyor...")
            
            for rep in range(REPETITIONS):
                start_time = time.time()
                
                ga = GeneticAlgorithmRouter(G, src, dst, demand)
                path, cost = ga.run()
                
                duration = time.time() - start_time
                
                if path:
                    scenario_costs.append(cost)
                    scenario_times.append(duration)
                    # Sadece bu senaryonun en iyisini görsel amaçlı sakla
                    if cost == min(scenario_costs):
                        best_path_str = str(path)
                else:
                    scenario_costs.append(float('inf'))
                    scenario_times.append(duration)

            # --- İstatistikleri Hesapla ---
            valid_costs = [c for c in scenario_costs if c != float('inf')]
            
            if valid_costs:
                mean_val = np.mean(valid_costs)
                std_val = np.std(valid_costs)
                best_val = np.min(valid_costs)
                worst_val = np.max(valid_costs)
                avg_time = np.mean(scenario_times)
                status = "SUCCESS"
            else:
                mean_val = std_val = best_val = worst_val = avg_time = 0
                status = "FAIL"

            # Sonuçları listeye ekle
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
            
            # Anlık Bilgi Bas
            if status == "SUCCESS":
                print(f"   >>> Tamamlandı. En İyi Maliyet: {best_val:.4f}, Ort. Süre: {avg_time:.3f}s")
            else:
                print(f"   >>> BAŞARISIZ (Yol Bulunamadı)")

        # --- CSV'ye Kaydet ---
        output_file = "Genetik_Algoritma_Sonuclar.csv"
        df_res = pd.DataFrame(experiment_results)
        df_res.to_csv(output_file, sep=';', index=False)
        
        print("\n" + "="*80)
        print(f"TÜM İŞLEMLER BİTTİ. Sonuçlar '{output_file}' dosyasına kaydedildi.")
        print("="*80)