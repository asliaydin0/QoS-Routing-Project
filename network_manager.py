import pandas as pd
import networkx as nx
import math
import random

class NetworkManager:
    def __init__(self):
        self.G = nx.DiGraph()
        self.demands = []

    def safe_float(self, value):
        """Virgüllü sayıları (0,85) noktalı sayıya (0.85) çevirip float yapar."""
        if pd.isna(value): return None
        try:
            # Eğer değer string ise ve virgül içeriyorsa noktaya çevir
            if isinstance(value, str):
                value = value.replace(',', '.')
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def load_data(self, node_file, edge_file, demand_file):
        """CSV dosyalarından verileri okur ve Grafı oluşturur."""
        try:
            # 1. NODE (Düğüm) Verilerini Yükle
            df_nodes = pd.read_csv(node_file, sep=None, engine='python') 
            df_nodes.columns = [c.strip().lower() for c in df_nodes.columns]
            
            for _, row in df_nodes.iterrows():
                node_id = int(row.iloc[0]) 
                
                # Virgül kontrolü yaparak değerleri al
                p_delay_val = row.get('s_ms', row.get('processing_delay', row.get('delay', random.uniform(0.5, 2.0))))
                proc_delay = self.safe_float(p_delay_val)
                
                rel_val = row.get('r_node', row.get('reliability', random.uniform(0.95, 0.99)))
                rel = self.safe_float(rel_val)
                
                self.G.add_node(node_id, processing_delay=proc_delay, reliability=rel)

            # 2. EDGE (Bağlantı) Verilerini Yükle
            df_edges = pd.read_csv(edge_file, sep=None, engine='python')
            df_edges.columns = [c.strip().lower() for c in df_edges.columns]

            # --- Çift Yönlü Yol Yaması ---
            try:
                df_reverse = df_edges.copy()
                col_src = df_edges.columns[0]
                col_dst = df_edges.columns[1]
                df_reverse = df_reverse.rename(columns={col_src: col_dst, col_dst: col_src})
                df_edges = pd.concat([df_edges, df_reverse], ignore_index=True)
                df_edges = df_edges.drop_duplicates(subset=[col_src, col_dst])
            except Exception as e:
                print(f"Uyarı: Çift yönlü yama hatası: {e}")

            for _, row in df_edges.iterrows():
                u = int(row.iloc[0]) 
                v = int(row.iloc[1]) 
                
                # Virgül kontrolü yaparak değerleri al
                delay_val = row.get('delay_ms', row.get('delay', row.get('link_delay', random.uniform(2.0, 10.0))))
                delay = self.safe_float(delay_val)
                
                bw_val = row.get('capacity_mbps', row.get('bandwidth', row.get('bw', random.randint(100, 1000))))
                bw = self.safe_float(bw_val)
                
                rel_val = row.get('r_link', row.get('reliability', random.uniform(0.95, 0.999)))
                rel = self.safe_float(rel_val)
                
                self.G.add_edge(u, v, delay=delay, bandwidth=bw, reliability=rel)

            # 3. DEMAND (Talep) Verilerini Yükle
            if demand_file:
                df_demand = pd.read_csv(demand_file, sep=None, engine='python')
                df_demand.columns = [c.strip().lower() for c in df_demand.columns]
                
                for _, row in df_demand.iterrows():
                    s = int(row.iloc[0])
                    d = int(row.iloc[1])
                    bw_req = self.safe_float(row.iloc[2])
                    self.demands.append({'src': s, 'dst': d, 'bw': bw_req})

            print(f"Veri Yüklendi: {len(self.G.nodes)} Düğüm, {len(self.G.edges)} Bağlantı.")
            return True

        except Exception as e:
            print(f"Veri Yükleme Hatası: {e}")
            return False

    def calculate_path_cost(self, path, weights, requested_bw=0):
        if not path or len(path) < 2:
            return float('inf'), {}

        w_d, w_r, w_res = weights
        total_delay = 0       
        rel_cost_log = 0          
        res_cost = 0   
        penalty = 0

        for node in path[1:-1]: 
            node_data = self.G.nodes[node]
            total_delay += node_data.get('processing_delay', 0)

        for node in path:
            node_data = self.G.nodes[node]
            r = node_data.get('reliability', 1.0)
            if r > 0: rel_cost_log += -math.log(r)
            else: rel_cost_log += 100 

        min_path_bw = float('inf') 
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            if not self.G.has_edge(u, v): return float('inf'), {}
            edge_data = self.G[u][v]
            bw = edge_data.get('bandwidth', 0.1) 
            if bw < min_path_bw: min_path_bw = bw
            total_delay += edge_data.get('delay', 0)
            r_link = edge_data.get('reliability', 1.0)
            if r_link > 0: rel_cost_log += -math.log(r_link)
            else: rel_cost_log += 100
            res_cost += (1000.0 / bw)

        if requested_bw > 0 and min_path_bw < requested_bw:
            penalty = 1000000 

        raw_cost = (w_d * total_delay) + (w_r * rel_cost_log) + (w_res * res_cost)
        total_cost = raw_cost + penalty
        
        metrics = {
            "delay": round(total_delay, 2),
            "rel_prob": round(math.exp(-rel_cost_log), 4),
            "res_cost": round(res_cost, 2),
            "min_bw": min_path_bw,
            "total_cost": round(total_cost, 4),
            "is_feasible": penalty == 0
        }
        return total_cost, metrics