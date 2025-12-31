import pandas as pd
import numpy as np
import random

def generate_network(n=250, p=0.4, seed=42):
    """
    Erdős-Rényi modeline göre rastgele ağ topolojisi oluşturur.
    N=250 düğüm, P=0.4 bağlantı olasılığı kısıtlarını uygular.
    """
    random.seed(seed)
    np.random.seed(seed)
    
    # 1. Düğüm Verilerini Oluştur (NodeData)
    # s_ms: 0.51 - 1.99 ms arası işlem gecikmesi
    # r_node: 0.95 - 0.999 arası güvenilirlik
    nodes = []
    for i in range(n):
        nodes.append({
            'node_id': i,
            's_ms': round(random.uniform(0.51, 1.99), 2),
            'r_node': round(random.uniform(0.95, 0.999), 4)
        })
    nodes_df = pd.DataFrame(nodes)
    
    # 2. Bağlantı Verilerini Oluştur (EdgeData)
    # p=0.4 olasılığıyla her düğüm çifti arasına kenar ekle
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if random.random() < p:
                # capacity_mbps: 100 - 1000 Mbps arası
                # delay_ms: 3 - 15 ms arası
                # r_link: 0.95 - 0.999 arası
                edges.append({
                    'src': i,
                    'dst': j,
                    'capacity_mbps': random.randint(100, 1000),
                    'delay_ms': round(random.uniform(3.0, 15.0), 2),
                    'r_link': round(random.uniform(0.95, 0.999), 4)
                })
                # Çift yönlü ağ olduğu için tersini de ekle
                edges.append({
                    'src': j, 'dst': i,
                    'capacity_mbps': edges[-1]['capacity_mbps'],
                    'delay_ms': edges[-1]['delay_ms'],
                    'r_link': edges[-1]['r_link']
                })
    
    edges_df = pd.DataFrame(edges)
    
    # Dosyaları Kaydet (network_manager.py'nin okuduğu isimler)
    nodes_df.to_csv('BSM307_317_Guz2025_TermProject_NodeData(in).csv', index=False, sep=';')
    edges_df.to_csv('BSM307_317_Guz2025_TermProject_EdgeData(in).csv', index=False, sep=';')
    print(f"Ağ başarıyla oluşturuldu: {n} düğüm, {len(edges_df)//2} bağlantı.")

if __name__ == "__main__":
    generate_network()