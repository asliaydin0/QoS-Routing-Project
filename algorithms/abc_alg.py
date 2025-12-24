import random
import math
import copy
import networkx as nx

class ABCOptimizer:
    """
    QoS Odaklı Rotalama için Artificial Bee Colony (ABC) Algoritması.
    
    Bu sınıf, sürü zekası (swarm intelligence) prensiplerini kullanarak optimum yolu arar.
    
    Temel Kavramlar:
    - Food Source (Besin Kaynağı): Kaynak (S) ve Hedef (D) arasında geçerli bir yol.
    - Nectar Amount (Nektar Miktarı): Yolun uygunluk değeri (Fitness = 1/Cost).
    - Employed Bees (İşçi Arılar): Mevcut çözümleri komşuluk araması ile iyileştirir.
    - Onlooker Bees (Gözcü Arılar): İyi çözümleri olasılıksal seçip iyileştirir.
    - Scout Bees (Kaşif Arılar): İyileşmeyen (limit aşan) çözümleri terk edip rastgele yeni yol arar.
    """

    def __init__(self, manager, src, dst, bw_demand):
        """
        ABC Algoritması Başlatıcı.
        
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

        # --- ABC Parametreleri ---
        self.colony_size = 40                 # Toplam arı sayısı
        self.n_employed = self.colony_size // 2
        self.n_onlooker = self.colony_size // 2
        self.max_cycles = 60                  # Maksimum iterasyon
        self.limit = 15                       # Bir çözümün terk edilme limiti (Trial limit)
        self.max_hop_limit = 15               # Maksimum sekme (hop) sayısı

        # Food Sources: [{'path': [], 'cost': float, 'metrics': {}, 'trial': 0}]
        self.population = [] 
        
        # Global Best takibi
        self.global_best_path = []
        self.global_best_cost = float('inf')
        self.global_best_metrics = {}

    def _generate_random_path(self, max_retries=10):
        """
        Rastgele (Random) geçerli bir yol üretir.
        DFS tabanlıdır, döngüleri engeller ve BW kısıtını gözetir.
        """
        for _ in range(max_retries):
            path = [self.src]
            visited = {self.src}
            curr = self.src
            
            while curr != self.dst:
                neighbors = list(self.manager.G.neighbors(curr))
                
                # BW kısıtını sağlayan ve ziyaret edilmemiş komşuları filtrele
                # (Strict constraint: calculate_path_cost cezalandırır ama burada baştan eliyoruz)
                valid_neighbors = [
                    n for n in neighbors 
                    if n not in visited and 
                    self.manager.G[curr][n].get('bandwidth', 0) >= self.bw_demand * 0.5 # Gevşek filtre
                ]
                
                # Eğer geçerli komşu yoksa, tüm ziyaret edilmemişlere bak (Scout mekanizması için esneklik)
                if not valid_neighbors:
                    valid_neighbors = [n for n in neighbors if n not in visited]

                if not valid_neighbors:
                    break # Çıkmaz sokak
                
                next_node = random.choice(valid_neighbors)
                path.append(next_node)
                visited.add(next_node)
                curr = next_node
                
                if len(path) > self.max_hop_limit:
                    break
            
            if curr == self.dst:
                return path
        return None

    def _generate_heuristic_population(self, count):
        """
        K-Shortest Paths algoritması ile kaliteli başlangıç çözümleri üretir.
        """
        paths = []
        try:
            # En kısa yolları bul (Topology-aware initialization)
            generator = nx.shortest_simple_paths(self.manager.G, self.src, self.dst)
            for _ in range(count * 3): # Fazla üretip seç
                try:
                    p = next(generator)
                    if len(p) <= self.max_hop_limit:
                        paths.append(p)
                except StopIteration:
                    break
            
            if len(paths) > count:
                return random.sample(paths, count)
            return paths
        except:
            return []

    def _evaluate(self, path, weights):
        """
        Bir yolun maliyetini hesaplar.
        """
        if not path:
            return float('inf'), {}
        return self.manager.calculate_path_cost(path, weights, self.bw_demand)

    def _mutate(self, current_path):
        """
        Lokal Arama (Neighbor Generation):
        Mevcut yolun bir parçasını değiştirerek komşu bir çözüm üretir.
        (Sub-path regeneration)
        """
        if len(current_path) < 3:
            return list(current_path) # Değiştirilemez kadar kısa

        new_path = list(current_path)
        
        # Yol üzerinde rastgele iki nokta seç (Başlangıç ve Bitiş korunabilir veya değişebilir)
        # Genelde rotalama problemlerinde bir ara segmenti değiştirmek mantıklıdır.
        idx_a = random.randint(0, len(new_path) - 2)
        idx_b = random.randint(idx_a + 1, len(new_path) - 1)
        
        node_a = new_path[idx_a]
        node_b = new_path[idx_b]
        
        # node_a'dan node_b'ye alternatif, kısa bir yol bulmaya çalış (DFS/Random Walk)
        # Orijinal segmenti atla
        segment_nodes = set(new_path[idx_a+1 : idx_b])
        
        temp_path = [node_a]
        curr = node_a
        found = False
        
        # Küçük bir lokal arama (max 5 adım)
        for _ in range(6):
            neighbors = list(self.manager.G.neighbors(curr))
            # Döngü oluşturmayacak komşular
            valid_n = [
                n for n in neighbors 
                if n not in temp_path and n not in new_path[:idx_a] and n not in new_path[idx_b+1:]
            ]
            
            # Hedef node_b komşulardaysa bağlan
            if node_b in neighbors:
                temp_path.append(node_b)
                found = True
                break
            
            if not valid_n: break
            
            curr = random.choice(valid_n)
            temp_path.append(curr)
        
        if found:
            # Yeni yolu birleştir: [Başlangıç...A] + [Yeni Segment] + [B...Bitiş]
            # temp_path [A, ..., B] içerir.
            candidate = new_path[:idx_a] + temp_path + new_path[idx_b+1:]
            
            # Son kontroller (Cycle ve Hop)
            if len(candidate) == len(set(candidate)) and len(candidate) <= self.max_hop_limit:
                return candidate

        return list(current_path) # Değişiklik yapılamadıysa eskisini döndür

    def solve(self, weights):
        """
        ABC Algoritması ana döngüsü.
        """
        # --- BAŞLANGIÇ POPÜLASYONU ---
        self.population = []
        
        # %50 Heuristic
        heuristic_paths = self._generate_heuristic_population(self.n_employed // 2)
        for p in heuristic_paths:
            cost, metrics = self._evaluate(p, weights)
            self.population.append({
                'path': p, 'cost': cost, 'metrics': metrics, 'trial': 0
            })
            
        # %50 Random
        attempts = 0
        while len(self.population) < self.n_employed and attempts < 100:
            p = self._generate_random_path()
            if p:
                cost, metrics = self._evaluate(p, weights)
                self.population.append({
                    'path': p, 'cost': cost, 'metrics': metrics, 'trial': 0
                })
            attempts += 1
            
        # Eğer hiç yol yoksa
        if not self.population:
            return [], 0.0, {}

        # Başlangıçtaki en iyiyi bul
        self.population.sort(key=lambda x: x['cost'])
        self.global_best_path = self.population[0]['path']
        self.global_best_cost = self.population[0]['cost']
        self.global_best_metrics = self.population[0]['metrics']

        # --- ANA DÖNGÜ (CYCLES) ---
        for cycle in range(self.max_cycles):
            
            # 1. EMPLOYED BEES PHASE (İşçi Arılar)
            for i in range(len(self.population)):
                bee = self.population[i]
                
                # Yeni çözüm üret (Mutation)
                new_path = self._mutate(bee['path'])
                new_cost, new_metrics = self._evaluate(new_path, weights)
                
                # Greedy Selection
                if new_cost < bee['cost']:
                    bee['path'] = new_path
                    bee['cost'] = new_cost
                    bee['metrics'] = new_metrics
                    bee['trial'] = 0 # İyileşme var, sayacı sıfırla
                else:
                    bee['trial'] += 1 # İyileşme yok, sayacı artır

            # 2. ONLOOKER BEES PHASE (Gözcü Arılar)
            # Seçim olasılıklarını hesapla (Fitness tabanlı: Düşük maliyet = Yüksek olasılık)
            # Fitness = 1 / (Cost + epsilon)
            total_fitness = sum(1.0 / (b['cost'] + 1e-9) for b in self.population)
            probs = [(1.0 / (b['cost'] + 1e-9)) / total_fitness for b in self.population]
            
            # Gözcü arıları dağıt
            for _ in range(self.n_onlooker):
                # Rulet tekerleği seçimi (Roulette Wheel Selection)
                r = random.random()
                cumulative = 0
                selected_idx = 0
                for idx, prob in enumerate(probs):
                    cumulative += prob
                    if r <= cumulative:
                        selected_idx = idx
                        break
                
                # Seçilen kaynak üzerinde çalış
                target_bee = self.population[selected_idx]
                new_path = self._mutate(target_bee['path'])
                new_cost, new_metrics = self._evaluate(new_path, weights)
                
                # Greedy Selection (Onlooker için)
                if new_cost < target_bee['cost']:
                    target_bee['path'] = new_path
                    target_bee['cost'] = new_cost
                    target_bee['metrics'] = new_metrics
                    target_bee['trial'] = 0
                else:
                    target_bee['trial'] += 1

            # 3. SCOUT BEES PHASE (Kaşif Arılar)
            # Limiti aşan kaynakları bul ve yenile
            for i in range(len(self.population)):
                if self.population[i]['trial'] > self.limit:
                    # Kaynağı terk et, rastgele yeni yol bul
                    random_path = self._generate_random_path()
                    if random_path:
                        cost, metrics = self._evaluate(random_path, weights)
                        self.population[i] = {
                            'path': random_path, 'cost': cost, 'metrics': metrics, 'trial': 0
                        }
                    else:
                        # Eğer rastgele yol bulunamazsa sadece trial'ı sıfırla (Soft reset)
                        self.population[i]['trial'] = 0

            # 4. MEMORIZE BEST SOLUTION
            current_cycle_best = min(self.population, key=lambda x: x['cost'])
            if current_cycle_best['cost'] < self.global_best_cost:
                self.global_best_cost = current_cycle_best['cost']
                self.global_best_path = list(current_cycle_best['path'])
                self.global_best_metrics = current_cycle_best['metrics']

        return self.global_best_path, self.global_best_cost, self.global_best_metrics