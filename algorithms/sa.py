import random
import math
import copy
import networkx as nx

class SAOptimizer:
    """
    QoS Odaklı Rotalama için Simulated Annealing (Benzetimli Tavlama) Algoritması.
    
    Bu sınıf, termodinamikteki tavlama işleminden esinlenerek, arama uzayında 
    global minimumu bulmaya çalışır. Yüksek sıcaklıklarda kötü çözümleri kabul etme 
    olasılığı (Metropolis kriteri) sayesinde yerel tuzaklardan kurtulur.
    
    Temel Bileşenler:
    - Energy (Enerji): Yolun maliyeti (Cost).
    - Temperature (Sıcaklık): Kabul olasılığını kontrol eden parametre.
    - Cooling Schedule (Soğutma): Sıcaklığın zamanla düşürülmesi.
    """

    def __init__(self, manager, src, dst, bw_demand):
        """
        SA Optimizer Başlatıcı.
        
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

        # --- SA Parametreleri (Cooling Schedule) ---
        self.initial_temp = 500.0     # Başlangıç sıcaklığı (T0)
        self.final_temp = 0.1         # Minimum sıcaklık (Tmin)
        self.alpha = 0.95             # Soğuma katsayısı (Geometric cooling)
        self.max_iterations = 800     # Maksimum iterasyon sayısı
        self.stagnation_limit = 50    # İyileşme olmazsa durma limiti
        self.max_hop_limit = 15       # Maksimum hop (sekme) sayısı

    def _evaluate(self, path, weights):
        """
        Bir yolun enerjisini (maliyetini) hesaplar.
        """
        if not path:
            return float('inf'), {}
        # NetworkManager üzerinden merkezi maliyet hesabı
        return self.manager.calculate_path_cost(path, weights, self.bw_demand)

    def _generate_initial_solution(self):
        """
        Başlangıç çözümü üretir (Hybrid Approach).
        Önce heuristic (Shortest Path) dener, başarısız olursa Random Walk yapar.
        """
        # 1. Deneme: Heuristic (En kısa yol - Hop bazlı)
        try:
            # Bant genişliği kısıtını sağlayan kenarları içeren bir alt grafikte ara
            valid_edges = [
                (u, v) for u, v, d in self.manager.G.edges(data=True)
                if d.get('bandwidth', 0) >= self.bw_demand
            ]
            temp_G = self.manager.G.edge_subgraph(valid_edges)
            
            if nx.has_path(temp_G, self.src, self.dst):
                path = nx.shortest_path(temp_G, self.src, self.dst)
                if len(path) <= self.max_hop_limit:
                    return path
        except:
            pass # Heuristic başarısız, random dene

        # 2. Deneme: Random Walk (DFS-based with constraints)
        for _ in range(20): # 20 kez dene
            path = [self.src]
            visited = {self.src}
            curr = self.src
            
            while curr != self.dst:
                neighbors = list(self.manager.G.neighbors(curr))
                # Cycle yaratmayan ve tercihen BW uygun komşular
                valid_neighbors = [
                    n for n in neighbors 
                    if n not in visited and 
                    self.manager.G[curr][n].get('bandwidth', 0) >= self.bw_demand
                ]
                
                # Eğer sıkı kısıtla bulunamazsa, sadece visited kontrolü yap (Cost fonksiyonu cezayı halleder)
                if not valid_neighbors:
                    valid_neighbors = [n for n in neighbors if n not in visited]
                
                if not valid_neighbors: break # Dead end
                
                next_node = random.choice(valid_neighbors)
                path.append(next_node)
                visited.add(next_node)
                curr = next_node
                
                if len(path) > self.max_hop_limit: break
            
            if curr == self.dst:
                return path
        
        return None # Geçerli yol üretilemedi

    def _generate_neighbor(self, current_path):
        """
        Mevcut çözümden bir komşu çözüm türetir.
        İki strateji kullanır:
        1. Node Replacement: Yolun ortasındaki bir düğümü değiştir.
        2. Subpath Reconstruction: Yolu kes ve yeniden bağla.
        """
        if len(current_path) < 3:
            return list(current_path) # Değiştirilemez

        new_path = list(current_path)
        strategy = random.choice(['swap', 'rebuild'])

        if strategy == 'swap':
            # --- Yöntem 1: Node Replacement ---
            # Başlangıç ve bitiş hariç bir düğüm seç
            idx = random.randint(1, len(new_path) - 2)
            prev_node = new_path[idx-1]
            next_node = new_path[idx+1]
            
            # prev ve next'in ortak komşularını bul (mevcut düğüm hariç)
            # Bu, yolun kopmamasını garanti eder.
            common = list(
                set(self.manager.G.neighbors(prev_node)) & 
                set(self.manager.G.neighbors(next_node))
            )
            # Cycle oluşturmayacak adayları filtrele
            candidates = [n for n in common if n not in new_path]
            
            if candidates:
                new_path[idx] = random.choice(candidates)
                return new_path

        # --- Yöntem 2: Subpath Reconstruction (veya Swap başarısızsa) ---
        # Yolun bir noktasından kopar ve hedefe tekrar gitmeye çalış
        cut_idx = random.randint(1, len(new_path) - 2)
        prefix = new_path[:cut_idx+1] # Kesilen noktaya kadar al
        curr = prefix[-1]
        
        # Basit bir Greedy/Random DFS ile tamamla
        temp_visited = set(prefix)
        remaining_hops = self.max_hop_limit - len(prefix)
        
        segment = []
        found = False
        
        # Küçük bir arama yap
        search_queue = [[curr]]
        # Basit BFS mantığı ile kısa bir tamamlama yolu ara
        # (BFS, SA'nın lokal arama doğasına uygundur)
        
        depth_limit = 5 # Çok uzağa gitme, lokal değişim olsun
        
        path_found = None
        
        # BFS ile reconstruction denemesi
        queue = [(curr, [curr])]
        visited_local = {curr}
        
        iterations = 0
        while queue and iterations < 50: # Sonsuz döngü koruması
            node, p = queue.pop(0)
            iterations += 1
            
            if len(p) > depth_limit: continue
            
            if node == self.dst:
                # Orijinal prefix ile birleştir (p[1:] çünkü curr zaten prefixte var)
                path_found = prefix + p[1:]
                break
            
            neighbors = list(self.manager.G.neighbors(node))
            random.shuffle(neighbors) # Stokastik yapı
            
            for n in neighbors:
                if n not in temp_visited and n not in visited_local:
                    visited_local.add(n)
                    queue.append((n, p + [n]))
        
        if path_found and len(path_found) <= self.max_hop_limit:
            return path_found

        # Eğer değişiklik yapılamadıysa veya geçersizse eski yolu döndür
        return list(current_path)

    def solve(self, weights):
        """
        Simulated Annealing ana döngüsü.
        
        Returns:
            best_path, best_cost, metrics
        """
        # 1. Başlangıç Çözümü
        current_path = self._generate_initial_solution()
        
        # Eğer hiç yol yoksa
        if not current_path:
            return [], 0.0, {}

        current_cost, current_metrics = self._evaluate(current_path, weights)
        
        # Global Best Takibi
        best_path = list(current_path)
        best_cost = current_cost
        best_metrics = current_metrics
        
        # 2. Tavlama Döngüsü
        T = self.initial_temp
        iteration = 0
        stagnation_counter = 0

        while T > self.final_temp and iteration < self.max_iterations:
            # A. Komşu Üretimi
            neighbor_path = self._generate_neighbor(current_path)
            
            # B. Enerji (Maliyet) Hesabı
            neighbor_cost, neighbor_metrics = self._evaluate(neighbor_path, weights)
            
            # C. Delta Enerji
            delta_E = neighbor_cost - current_cost
            
            # D. Kabul Kriteri (Metropolis)
            accepted = False
            if delta_E < 0:
                # İyileşme varsa her zaman kabul et
                accepted = True
            else:
                # Kötüleşme varsa olasılıksal kabul et: P = exp(-delta / T)
                # T yüksekken kabul ihtimali yüksek, T düştükçe azalır.
                try:
                    prob = math.exp(-delta_E / T)
                except OverflowError:
                    prob = 0
                
                if random.random() < prob:
                    accepted = True
            
            # E. Güncelleme
            if accepted:
                current_path = neighbor_path
                current_cost = neighbor_cost
                current_metrics = neighbor_metrics
                
                # Global Best Kontrolü
                if current_cost < best_cost:
                    best_path = list(current_path)
                    best_cost = current_cost
                    best_metrics = current_metrics
                    stagnation_counter = 0 # İyileşme var
                else:
                    stagnation_counter += 1
            else:
                stagnation_counter += 1
            
            # F. Soğutma (Cooling Schedule)
            T *= self.alpha
            iteration += 1
            
            # G. Erken Durdurma (Stagnation)
            # Eğer uzun süre (örn. 50 iterasyon) iyileşme olmadıysa ve sıcaklık zaten düşükse dur.
            if stagnation_counter > self.stagnation_limit and T < (self.initial_temp * 0.1):
                break

        return best_path, best_cost, best_metrics