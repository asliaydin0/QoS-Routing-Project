import random
import networkx as nx

class QLearning:
    def __init__(self, G, src, dst, weights):
        self.G = G
        self.src = src
        self.dst = dst
        self.weights = weights

    def get_reward(self, u, v):
        data = self.G[u][v]
        d = data.get('delay', 0)
        r = data.get('reliability', 1.0)
        bw = data.get('bandwidth', 100)
        c = (1000 / bw) if bw > 0 else 100
        
        # QoS Maliyeti
        cost = (d * self.weights[0]) + ((1 - r) * 1000 * self.weights[1]) + (c * self.weights[2])
        
        # Q-Learning ödülü (Maliyet ne kadar azsa ödül o kadar büyük)
        return 10000 / (cost + 1)

    def solve(self, episodes=100, alpha=0.1, gamma=0.9, epsilon=0.2):
        # Q-Tablosu: {node: {neighbor: val}}
        q_table = {n: {nbr: 0.0 for nbr in self.G.neighbors(n)} for n in self.G.nodes()}
        
        for _ in range(episodes):
            curr = self.src
            
            # Hedefe varana kadar veya sıkışana kadar gez
            for _ in range(50): # Max adım
                if curr == self.dst: break
                
                neighbors = list(self.G.neighbors(curr))
                if not neighbors: break
                
                # Epsilon-Greedy
                if random.random() < epsilon:
                    next_node = random.choice(neighbors)
                else:
                    # En iyi Q değerine sahip komşuyu seç
                    next_node = max(neighbors, key=lambda n: q_table[curr].get(n, 0))
                
                reward = self.get_reward(curr, next_node)
                
                # Gelecekteki max Q
                max_future_q = 0
                if next_node != self.dst:
                    nbrs_next = list(self.G.neighbors(next_node))
                    if nbrs_next:
                        max_future_q = max([q_table[next_node][n] for n in nbrs_next])
                
                # Bellman Denklemi
                old_q = q_table[curr][next_node]
                new_q = (1 - alpha) * old_q + alpha * (reward + gamma * max_future_q)
                q_table[curr][next_node] = new_q
                
                curr = next_node

        # Öğrenilen tablo ile yol bul
        path = [self.src]
        curr = self.src
        visited = {self.src}
        
        while curr != self.dst:
            neighbors = list(self.G.neighbors(curr))
            valid_neighbors = [n for n in neighbors if n not in visited]
            
            if not valid_neighbors: return [] # Çıkmaz sokak
            
            next_node = max(valid_neighbors, key=lambda n: q_table[curr].get(n, 0))
            path.append(next_node)
            visited.add(next_node)
            curr = next_node
            
            if len(path) > len(self.G.nodes): return [] # Döngü

        return path