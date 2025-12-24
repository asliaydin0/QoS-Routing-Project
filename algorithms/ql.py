import random
import math
import networkx as nx

class QLearningOptimizer:
    """
    QoS Odaklı Rotalama için Q-Learning (Pekiştirmeli Öğrenme) Implementasyonu.
    
    Özellikler:
    - Model: Model-Free, Off-Policy (Q-Learning).
    - Durum (State): Mevcut düğüm (Node ID).
    - Aksiyon (Action): Komşu düğüme geçiş.
    - Politika: Epsilon-Greedy (Keşfet/Sömür dengesi).
    - Ödül Yapısı: QoS maliyet fonksiyonunun negatifi ve kısıt ihlali cezaları.
    """

    def __init__(self, manager, src, dst, bw_demand):
        """
        Q-Learning Optimizer Başlatıcı.
        
        Args:
            manager (NetworkManager): Ağ topolojisi ve maliyet hesaplayıcı.
            src (int): Kaynak düğüm ID.
            dst (int): Hedef düğüm ID.
            bw_demand (float): Talep edilen bant genişliği (Mbps).
        """
        self.manager = manager
        self.src = src
        self.dst = dst
        self.bw_demand = bw_demand

        # Q-Table: {state: {action: q_value}}
        self.Q = {}

        # Hiper-parametreler
        self.alpha = 0.1          # Öğrenme oranı (Learning Rate)
        self.gamma = 0.9          # İndirim faktörü (Discount Factor)
        self.epsilon = 1.0        # Başlangıç keşfetme oranı
        self.epsilon_decay = 0.99 # Her epizot sonrası azalma oranı
        self.epsilon_min = 0.05   # Minimum keşfetme oranı
        
        self.episodes = 800       # Toplam epizot sayısı
        self.max_hops = 20        # Maksimum adım (sonsuz döngü koruması)

        # Ceza ve Ödül Sabitleri
        self.PENALTY_CYCLE = -1000.0
        self.PENALTY_BW = -500.0
        self.PENALTY_DEAD_END = -200.0
        self.REWARD_STEP = -1.0
        
        # En iyi yolu saklamak için
        self.best_path = []
        self.best_cost = float('inf')
        self.best_metrics = {}

    def _get_q(self, state, action):
        """Q tablosundan değer okur, yoksa 0.0 döndürür."""
        if state not in self.Q:
            self.Q[state] = {}
        return self.Q[state].get(action, 0.0)

    def _set_q(self, state, action, value):
        """Q tablosunu günceller."""
        if state not in self.Q:
            self.Q[state] = {}
        self.Q[state][action] = value

    def _get_max_q(self, state):
        """Bir durumdaki en yüksek Q değerini döndürür."""
        if state not in self.Q or not self.Q[state]:
            return 0.0
        return max(self.Q[state].values())

    def _choose_action(self, state, valid_neighbors):
        """Epsilon-Greedy politikasına göre aksiyon seçer."""
        if not valid_neighbors:
            return None

        # Keşfet (Explore)
        if random.random() < self.epsilon:
            return random.choice(valid_neighbors)
        
        # Sömür (Exploit)
        # Mevcut komşular içinden en yüksek Q değerine sahip olanı seç
        q_values = [self._get_q(state, n) for n in valid_neighbors]
        max_q = max(q_values)
        
        # Eşitlik durumunda rastgele seçim (tie-breaking)
        candidates = [n for n, q in zip(valid_neighbors, q_values) if q == max_q]
        return random.choice(candidates) if candidates else random.choice(valid_neighbors)

    def solve(self, weights):
        """
        Q-Learning eğitim döngüsü.
        
        Args:
            weights (tuple): (w_delay, w_reliability, w_resource)
            
        Returns:
            best_path, best_cost, metrics
        """
        # Eğitim Döngüsü
        for episode in range(self.episodes):
            curr_state = self.src
            path = [curr_state]
            visited = {curr_state}
            
            for _ in range(self.max_hops):
                # 1. Aksiyon Seçimi
                # Graf üzerindeki komşuları al
                neighbors = list(self.manager.G.neighbors(curr_state))
                
                # Çıkmaz sokak kontrolü
                if not neighbors:
                    # Q güncelle (Dead End Cezası)
                    # Geriye dönük güncelleme yapılamadığı için sadece o anki durumu cezalandırıyoruz
                    # Bir önceki adımı bilmediğimizden burada Q güncellemesi yapmıyoruz, loop kırılıyor.
                    break 

                next_node = self._choose_action(curr_state, neighbors)
                
                # 2. Kısıt Kontrolleri ve Ödül Hesaplama
                reward = 0
                done = False
                valid_step = True
                
                # A. Döngü Kontrolü
                if next_node in visited:
                    reward = self.PENALTY_CYCLE
                    done = True # Epizot biter
                    valid_step = False
                
                # B. Bant Genişliği Kontrolü
                elif self.manager.G[curr_state][next_node].get('bandwidth', 0) < self.bw_demand:
                    reward = self.PENALTY_BW
                    done = True # Epizot biter (veya çok büyük ceza ile devam etmeyiz)
                    valid_step = False
                
                # C. Hedefe Ulaşma
                elif next_node == self.dst:
                    path.append(next_node)
                    
                    # Gerçek QoS Maliyetini Hesapla
                    total_cost, metrics = self.manager.calculate_path_cost(path, weights, self.bw_demand)
                    
                    # En iyi yolu güncelle
                    if metrics['is_feasible'] and total_cost < self.best_cost:
                        self.best_cost = total_cost
                        self.best_path = list(path)
                        self.best_metrics = metrics
                    
                    # Ödül: Maliyet ne kadar düşükse ödül o kadar yüksek (sıfıra yakın) olmalı.
                    # Q-Learning maksimizasyon yaptığı için maliyetin negatifini ödül olarak veriyoruz.
                    # Ölçekleme katsayısı (örn. 10) eğitimin stabilitesini artırabilir.
                    reward = -total_cost * 2.0 
                    done = True
                
                # D. Ara Adım
                else:
                    reward = self.REWARD_STEP
                    path.append(next_node)
                    visited.add(next_node)
                
                # 3. Q-Table Güncelleme (Bellman Denklemi)
                # Q(s,a) = Q(s,a) + alpha * [R + gamma * max Q(s',a') - Q(s,a)]
                current_q = self._get_q(curr_state, next_node)
                max_next_q = self._get_max_q(next_node) if not done else 0.0
                
                new_q = current_q + self.alpha * (reward + (self.gamma * max_next_q) - current_q)
                self._set_q(curr_state, next_node, new_q)
                
                # Sonraki duruma geç
                if valid_step:
                    curr_state = next_node
                
                if done:
                    break
            
            # Epsilon Decay
            if self.epsilon > self.epsilon_min:
                self.epsilon *= self.epsilon_decay

        # Eğitim Bitti
        
        # Eğer hiç yol bulunamadıysa Shortest Path Fallback (Sistem çökmemesi için)
        if not self.best_path:
            try:
                # Fallback: Sadece BW kısıtını sağlayan en kısa yolu bulmaya çalış
                valid_edges = [
                    (u, v) for u, v, d in self.manager.G.edges(data=True)
                    if d.get('bandwidth', 0) >= self.bw_demand
                ]
                temp_G = self.manager.G.edge_subgraph(valid_edges)
                if nx.has_path(temp_G, self.src, self.dst):
                    self.best_path = nx.shortest_path(temp_G, self.src, self.dst)
                    self.best_cost, self.best_metrics = self.manager.calculate_path_cost(
                        self.best_path, weights, self.bw_demand
                    )
                else:
                    # Hiçbir çare yok
                    return [], 0.0, {}
            except:
                return [], 0.0, {}

        return self.best_path, self.best_cost, self.best_metrics