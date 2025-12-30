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

            # ============================================================
            # --- BAŞLANGIÇ: Çift Yönlü (Symmetric) Yol Yaması ---
            # ============================================================
            # Bu kısım, tek yönlü olan veri setini çift yönlüye çevirir.
            
            try:
                # 1. Mevcut verinin kopyasını al
                df_reverse = df_edges.copy()
                
                # 2. Sütun isimlerini tespit et (İlk sütun src, ikinci dst varsayılır)
                col_src = df_edges.columns[0]
                col_dst = df_edges.columns[1]
                
                # 3. Kaynak ve Hedef sütunlarının isimlerini değiştir (Swap)
                df_reverse = df_reverse.rename(columns={col_src: col_dst, col_dst: col_src})
                
                # 4. Orijinal tablo ile ters yolları birleştir
                df_edges = pd.concat([df_edges, df_reverse], ignore_index=True)
                
                # 5. Olası kopyaları temizle (Aynı yol iki kere eklenmesin)
                df_edges = df_edges.drop_duplicates(subset=[col_src, col_dst])
                
                print("Bilgi: Ağ topolojisi çift yönlü (simetrik) hale getirildi.")
                
            except Exception as e:
                print(f"Uyarı: Çift yönlü yama uygulanırken hata oluştu: {e}")
                # Hata olsa bile orijinal veriyle devam eder.

            # ============================================================
            # --- BİTİŞ: Yama Tamamlandı ---
            # ============================================================

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
        PDF Madde 3 ve 4'teki formüllere göre DÜZELTİLMİŞ maliyet hesabı.
        weights: (w_delay, w_reliability, w_resource)
        requested_bw: Talep edilen bant genişliği (Constraint)
        """
        if not path or len(path) < 2:
            return float('inf'), {}

        w_d, w_r, w_res = weights
        
        total_delay = 0       
        rel_cost_log = 0          
        res_cost = 0   
        penalty = 0

        # --- 1. Düğüm Gecikmesi (Processing Delay) ---
        # PDF Madde 3.1: "Kaynak S ve Hedef D hariç"
        # Bu yüzden sadece ara düğümleri (slice 1:-1) geziyoruz.
        for node in path[1:-1]: 
            node_data = self.G.nodes[node]
            total_delay += node_data.get('processing_delay', 0)

        # --- 2. Düğüm Güvenilirliği (Node Reliability) ---
        # PDF Madde 3.2: P yolundaki TÜM düğümler (k in P)
        # S ve D düğümleri de güvenilirlik hesabına katılmalıdır.
        for node in path:
            node_data = self.G.nodes[node]
            r = node_data.get('reliability', 1.0)
            # Logaritma alırken 0 hatasından kaçınmak için kontrol
            if r > 0:
                rel_cost_log += -math.log(r)
            else:
                rel_cost_log += 100 # Güvenilirlik 0 ise çok yüksek ceza

        # --- 3. Bağlantı (Link) Maliyetleri ---
        min_path_bw = float('inf') 

        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            
            # Hata kontrolü: Bağlantı yoksa
            if not self.G.has_edge(u, v):
                return float('inf'), {}

            edge_data = self.G[u][v]
            
            # Bant Genişliği
            bw = edge_data.get('bandwidth', 0.1) # 0'a bölme hatası olmasın
            if bw < min_path_bw: min_path_bw = bw
            
            # Link Gecikmesi (PDF 3.1: Tüm linkler dahildir)
            total_delay += edge_data.get('delay', 0)
            
            # Link Güvenilirliği (PDF 3.2: Tüm linkler dahildir)
            r_link = edge_data.get('reliability', 1.0)
            if r_link > 0:
                rel_cost_log += -math.log(r_link)
            else:
                rel_cost_log += 100
            
            # Kaynak Kullanımı (PDF 3.3)
            # Formül: 1 Gbps / Bandwidth
            # Varsayım: Veri setindeki BW 'Mbps' ise 1000/bw doğrudur.
            res_cost += (1000.0 / bw)

        # KISIT KONTROLÜ
        # Eğer yolun darboğazı (min_path_bw) talep edilen bant genişliğinden (requested_bw)
        # küçükse, bu yol geçersiz sayılır (Penalty).
        if requested_bw > 0 and min_path_bw < requested_bw:
            penalty = 1000000 

        # Ağırlıklı Toplam Hesaplama
        # PDF Madde 4: W_delay * Delay + W_rel * RelCost + W_res * ResCost
        raw_cost = (w_d * total_delay) + (w_r * rel_cost_log) + (w_res * res_cost)
        total_cost = raw_cost + penalty
        
        metrics = {
            "delay": total_delay,
            "rel_prob": math.exp(-rel_cost_log), # e^(-cost) gerçek güvenilirlik oranını verir
            "rel_cost": rel_cost_log,            # Minimizasyon için kullanılan logaritmik değer
            "res_cost": res_cost,
            "min_bw": min_path_bw,
            "total_cost": total_cost,
            "is_feasible": penalty == 0
        }
        return total_cost, metrics