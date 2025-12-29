import pandas as pd
import networkx as nx
import math

class NetworkManager:
    def __init__(self):
        self.G = nx.DiGraph() # Yönlü graf (Directed Graph)
        self.demands = []

    def load_data(self, node_file, edge_file, demand_file):
        """CSV dosyalarından verileri okur ve Grafı oluşturur."""
        try:
            # 1. NODE Verilerini Yükle
            # CSV formatına göre (noktalı virgül veya virgül) ayırıcıyı değiştirebilirsin
            df_nodes = pd.read_csv(node_file, sep=None, engine='python') 
            # Sütun isimlerini standartlaştır (küçük harf, boşluksuz)
            df_nodes.columns = [c.strip().lower() for c in df_nodes.columns]
            
            for _, row in df_nodes.iterrows():
                # Sütun isimlerini CSV'deki gerçek başlıklarına göre ayarla:
                # Örn: 'id', 'processing_delay', 'reliability'
                node_id = int(row.iloc[0]) # Genelde ilk sütun ID'dir
                proc_delay = float(row.get('processing_delay', row.get('delay', 0)))
                rel = float(row.get('reliability', 0.99))
                
                self.G.add_node(node_id, processing_delay=proc_delay, reliability=rel)

            # 2. EDGE Verilerini Yükle
            df_edges = pd.read_csv(edge_file, sep=None, engine='python')
            df_edges.columns = [c.strip().lower() for c in df_edges.columns]

            for _, row in df_edges.iterrows():
                u = int(row.iloc[0]) # Kaynak
                v = int(row.iloc[1]) # Hedef
                
                delay = float(row.get('delay', row.get('link_delay', 5)))
                bw = float(row.get('bandwidth', row.get('bw', 100)))
                rel = float(row.get('reliability', 0.99))
                
                # Grafiğe ekle
                self.G.add_edge(u, v, delay=delay, bandwidth=bw, reliability=rel)

            # 3. DEMAND (Talep) Verilerini Yükle
            if demand_file:
                df_demand = pd.read_csv(demand_file, sep=None, engine='python')
                df_demand.columns = [c.strip().lower() for c in df_demand.columns]
                
                for _, row in df_demand.iterrows():
                    s = int(row.iloc[0])
                    d = int(row.iloc[1])
                    bw = float(row.iloc[2]) # 3. sütun genelde bant genişliği talebi
                    self.demands.append({'src': s, 'dst': d, 'bw': bw})

            print(f"Veri Yüklendi: {len(self.G.nodes)} Düğüm, {len(self.G.edges)} Bağlantı.")
            return True

        except Exception as e:
            print(f"Veri Yükleme Hatası: {e}")
            return False

    def calculate_path_cost(self, path, weights, requested_bw=0):
        """
        PDF Madde 3 ve 4'teki formüllere göre maliyet hesabı.
        weights: (w_delay, w_reliability, w_resource)
        requested_bw: Talep edilen bant genişliği (Constraint)
        """
        if not path or len(path) < 2:
            return float('inf'), {}

        w_d, w_r, w_res = weights
        
        total_delay = 0       
        rel_cost_log = 0          
        res_cost = 0   
        
        # Ceza Puanı (Penalty): Eğer yolun bant genişliği yetersizse maliyeti sonsuz yap
        penalty = 0

        # --- 1. Düğüm Maliyetleri (Ara düğümler) ---
        for node in path[1:-1]: 
            node_data = self.G.nodes[node]
            total_delay += node_data.get('processing_delay', 0)
            r = node_data.get('reliability', 1.0)
            rel_cost_   log += -math.log(r) if r > 0 else 100

        # --- 2. Bağlantı Maliyetleri ---
        min_path_bw = float('inf') # Yol üzerindeki darboğaz bant genişliği

        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            if not self.G.has_edge(u, v):
                return float('inf'), {} # Geçersiz yol

            edge_data = self.G[u][v]
            
            # Bant Genişliği Kontrolü
            bw = edge_data.get('bandwidth', 0.1)
            if bw < min_path_bw: min_path_bw = bw
            
            # Gecikme [cite: 41]
            total_delay += edge_data.get('delay', 0)
            
            # Güvenilirlik [cite: 52]
            r_link = edge_data.get('reliability', 1.0)
            rel_cost_log += -math.log(r_link) if r_link > 0 else 100
            
            # Kaynak Kullanımı [cite: 57]
            res_cost += (1000.0 / bw)

        # KISIT KONTROLÜ: Eğer darboğaz < istenen bant genişliği ise cezalandır
        if requested_bw > 0 and min_path_bw < requested_bw:
            penalty = 1000000 # Çok büyük bir ceza

        # Ağırlıklı Toplam [cite: 66]
        # delay, reliability ve resource değerlerini normalize etmek gerekebilir 
        # ama proje basit toplama öneriyor.
        raw_cost = (w_d * total_delay) + (w_r * rel_cost_log) + (w_res * res_cost)
        total_cost = raw_cost + penalty
        
        metrics = {
            "delay": total_delay,
            "rel_prob": math.exp(-rel_cost_log), # Gerçek olasılık (0-1 arası)
            "rel_cost": rel_cost_log,            # Logaritmik maliyet
            "res_cost": res_cost,
            "min_bw": min_path_bw,
            "total_cost": total_cost,
            "is_feasible": penalty == 0
        }
        return total_cost, metrics