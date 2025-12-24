import random
import math
import networkx as nx

class SimulatedAnnealing:
    def __init__(self, G, src, dst, weights):
        self.G = G
        self.src = src
        self.dst = dst
        self.weights = weights

    def calculate_cost(self, path):
        total_delay = 0
        total_rel = 1.0
        total_bw_cost = 0
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            data = self.G[u][v]
            total_delay += data.get('delay', 0)
            total_rel *= data.get('reliability', 1.0)
            bw = data.get('bandwidth', 100)
            total_bw_cost += (1000 / bw) if bw > 0 else 100

        return (total_delay * self.weights[0]) + \
               ((1 - total_rel) * 1000 * self.weights[1]) + \
               (total_bw_cost * self.weights[2])

    def solve(self, initial_temp=1000, cooling_rate=0.9):
        # Başlangıç Çözümü (Hızlıca bir yol bul - Dijkstra ağırlıksız)
        try:
            current_path = nx.shortest_path(self.G, self.src, self.dst)
        except:
            return []

        current_cost = self.calculate_cost(current_path)
        best_path = current_path
        best_cost = current_cost
        
        temp = initial_temp
        
        for _ in range(50): # İterasyon
            if temp < 1: break
            
            # KOMŞU ÜRETİMİ: Yolun ortasından rastgele bir yeri değiştir
            if len(current_path) > 2:
                try:
                    # Yolun bir kısmını kesip alternatifle birleştir
                    idx = random.randint(0, len(current_path)-2)
                    sub_src = current_path[idx]
                    
                    # O noktadan hedefe yeni bir basit yol dene
                    alt_path = nx.shortest_path(self.G, sub_src, self.dst, weight='delay') 
                    
                    new_path = current_path[:idx] + alt_path
                    new_cost = self.calculate_cost(new_path)
                    
                    # Kabul Kriteri
                    if new_cost < current_cost:
                        current_path = new_path
                        current_cost = new_cost
                    else:
                        prob = math.exp((current_cost - new_cost) / temp)
                        if random.random() < prob:
                            current_path = new_path
                            current_cost = new_cost
                    
                    if current_cost < best_cost:
                        best_cost = current_cost
                        best_path = current_path
                except:
                    pass
            
            temp *= cooling_rate
            
        return best_path