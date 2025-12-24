import random
import math
import copy
import networkx as nx

class GeneticOptimizer:
    """
    QoS Odaklı Rotalama için Genetik Algoritma (GA) Implementasyonu.
    
    Özellikler:
    - Yol tabanlı kromozom yapısı (Path-based representation).
    - Topoloji farkındalıklı başlatma (Topology-aware initialization).
    - Tek noktalı topolojik çaprazlama (Topological Crossover).
    - İki aşamalı mutasyon (Node swap & Path rebuild).
    """

    def __init__(self, manager, src, dst, bw_demand):
        """
        GA Optimizer Başlatıcı.
        
        Args:
            manager (NetworkManager): Ağ topolojisi ve maliyet hesaplamaları için yönetici.
            src (int): Kaynak düğüm ID.
            dst (int): Hedef düğüm ID.
            bw_demand (float): Talep edilen bant genişliği (Mbps).
        """
        self.manager = manager
        self.src = src
        self.dst = dst
        self.bw_demand = bw_demand
        
        # GA Hiper-parametreleri
        self.pop_size = 50          # Popülasyon boyutu
        self.max_generations = 60   # Maksimum jenerasyon
        self.mutation_rate = 0.15   # Mutasyon oranı
        self.crossover_rate = 0.85  # Çaprazlama oranı
        self.elitism_count = int(self.pop_size * 0.1) # %10 Elitizm
        self.tournament_size = 3    # Turnuva seçimi boyutu
        self.max_hop_limit = 15     # Maksimum düğüm sayısı (uzun yolları engellemek için)
        self.stagnation_limit = 10  # Erken durdurma için iyileşmeme limiti

    def _generate_random_path(self, max_attempts=10):
        """
        DFS tabanlı rastgele ve geçerli bir yol üretir.
        Döngü (Cycle) kontrolü içerir.
        """
        for _ in range(max_attempts):
            path = [self.src]
            visited = {self.src}
            curr = self.src
            
            while curr != self.dst:
                # Komşuları al
                neighbors = list(self.manager.G.neighbors(curr))
                # Ziyaret edilmemiş ve bant genişliği potansiyel olarak uygun komşuları filtrele
                # (Detaylı maliyet hesabı manager.calculate_path_cost'ta yapılacak ama
                # burada bariz darboğazlara girmemek algoritmayı hızlandırır)
                valid_neighbors = [
                    n for n in neighbors 
                    if n not in visited and 
                    self.manager.G[curr][n].get('bandwidth', 0) >= self.bw_demand * 0.8 # Biraz esneklik
                ]

                # Eğer gidecek yer yoksa, daha geniş (BW kısıtı olmadan) bak
                if not valid_neighbors:
                    valid_neighbors = [n for n in neighbors if n not in visited]
                
                if not valid_neighbors:
                    break # Çıkmaz sokak (Dead end)
                
                # Rastgele bir sonraki düğümü seç
                next_node = random.choice(valid_neighbors)
                path.append(next_node)
                visited.add(next_node)
                curr = next_node
                
                # Hop limiti kontrolü
                if len(path) > self.max_hop_limit:
                    break
            
            if curr == self.dst:
                return path
        return None

    def _generate_heuristic_population(self, count):
        """
        K-Shortest Paths veya varyasyonlarını kullanarak 'akıllı' bireyler üretir.
        Bu, algoritmanın yakınsamasını hızlandırır.
        """
        paths = []
        try:
            # NetworkX'in shortest_simple_paths jeneratörünü kullan
            # Performans için sadece ilk (count * 2) yolu alıp arasından seçiyoruz
            generator = nx.shortest_simple_paths(self.manager.G, self.src, self.dst)
            for _ in range(count * 3):
                try:
                    p = next(generator)
                    if len(p) <= self.max_hop_limit:
                        paths.append(p)
                except StopIteration:
                    break
            
            # Bulunanlardan rastgele seç
            if len(paths) > count:
                return random.sample(paths, count)
            return paths
        except:
            return []

    def _calculate_fitness(self, path, weights):
        """
        Bireyin uygunluk değerini (fitness) hesaplar.
        Minimizasyon problemidir (Düşük maliyet = İyi fitness).
        """
        # Manager üzerinden merkezi hesaplama (GEREKSİNİM)
        total_cost, metrics = self.manager.calculate_path_cost(path, weights, self.bw_demand)
        return total_cost, metrics

    def _crossover(self, parent1, parent2):
        """
        Path-Aware Crossover (Yol Farkındalıklı Çaprazlama).
        İki ebeveynin ortak bir düğümü varsa, o noktadan yolları birleştirir.
        """
        if random.random() > self.crossover_rate:
            return copy.deepcopy(parent1)

        # Başlangıç ve bitiş hariç ortak düğümleri bul
        p1_nodes = set(parent1[1:-1])
        p2_nodes = set(parent2[1:-1])
        common_nodes = list(p1_nodes.intersection(p2_nodes))

        if not common_nodes:
            # Ortak nokta yoksa ebeveyni aynen döndür
            return copy.deepcopy(parent1)
        
        # Rastgele bir kesişim noktası seç
        pivot = random.choice(common_nodes)
        
        try:
            # Parent 1'in başından pivot'a kadar + Parent 2'nin pivot'tan sonuna kadar
            idx1 = parent1.index(pivot)
            idx2 = parent2.index(pivot)
            
            child = parent1[:idx1+1] + parent2[idx2+1:]
            
            # Döngü kontrolü (Cycle check)
            if len(child) != len(set(child)):
                return copy.deepcopy(parent1) # Döngü oluştu, işlemi iptal et
            
            # Hop limit kontrolü
            if len(child) > self.max_hop_limit:
                return copy.deepcopy(parent1)

            return child
        except ValueError:
            return copy.deepcopy(parent1)

    def _mutate(self, path):
        """
        İki tür mutasyon uygular:
        1. Node Replacement: Bir düğümü alternatifiyle değiştir.
        2. Subpath Rebuild: Yolun bir parçasını silip yeniden bağla.
        """
        if random.random() > self.mutation_rate:
            return path
        
        # Çok kısa yollar için mutasyon yapılamaz
        if len(path) < 4: 
            return path

        new_path = copy.deepcopy(path)
        mutation_type = random.choice(['rebuild', 'replacement'])

        if mutation_type == 'replacement':
            # Rastgele bir ara düğüm seç (start/end hariç)
            idx = random.randint(1, len(new_path) - 2)
            prev_node = new_path[idx-1]
            next_node = new_path[idx+1]
            
            # Önceki ve sonraki düğümün ortak komşularını bul (mevcut düğüm hariç)
            common_neighbors = list(
                set(self.manager.G.neighbors(prev_node)) & 
                set(self.manager.G.neighbors(next_node))
            )
            candidates = [n for n in common_neighbors if n not in new_path]
            
            if candidates:
                new_path[idx] = random.choice(candidates)

        elif mutation_type == 'rebuild':
            # İki nokta seç ve arasını kopar
            idx1 = random.randint(0, len(new_path) - 3)
            idx2 = random.randint(idx1 + 2, len(new_path) - 1)
            
            start_segment = new_path[:idx1+1]
            end_target = new_path[idx2]
            
            # Aradaki boşluğu rastgele DFS ile doldurmaya çalış
            # Geçici sub-path bulucu
            temp_path = [start_segment[-1]]
            curr = start_segment[-1]
            found = False
            
            # Küçük bir lokal arama (maksimum 5 adım)
            for _ in range(5):
                neighbors = list(self.manager.G.neighbors(curr))
                valid_n = [n for n in neighbors if n not in start_segment and n not in temp_path]
                
                if end_target in neighbors:
                    temp_path.append(end_target)
                    found = True
                    break
                
                if not valid_n: break
                
                curr = random.choice(valid_n)
                temp_path.append(curr)
            
            if found:
                # Başarılı onarım: Başlangıç + Yeni Segment (hedef dahil) + Hedef sonrası kısım
                # Dikkat: temp_path[1:] çünkü start_segment'in son elemanı zaten var
                final_segment = new_path[idx2+1:]
                
                # Cycle check for final assembly
                candidate = start_segment + temp_path[1:] + final_segment
                if len(candidate) == len(set(candidate)) and len(candidate) <= self.max_hop_limit:
                    new_path = candidate

        return new_path

    def _tournament_selection(self, population, costs):
        """
        Turnuva Seçimi: Rastgele k birey seç, en iyisini döndür.
        """
        indices = random.sample(range(len(population)), self.tournament_size)
        best_idx = indices[0]
        for idx in indices[1:]:
            if costs[idx] < costs[best_idx]:
                best_idx = idx
        return population[best_idx]

    def solve(self, weights):
        """
        Algoritmanın ana döngüsü.
        
        Returns:
            best_path (list): Bulunan en iyi yol.
            best_cost (float): En iyi yolun toplam maliyeti.
            metrics (dict): Detaylı metrikler (delay, reliability, vb.)
        """
        # 1. Başlangıç Popülasyonu Oluşturma (%40 Heuristic, %60 Random)
        population = []
        heuristic_count = int(self.pop_size * 0.4)
        
        # A. Heuristic Bireyler
        heuristic_paths = self._generate_heuristic_population(heuristic_count)
        population.extend(heuristic_paths)
        
        # B. Random Bireyler
        attempts = 0
        while len(population) < self.pop_size and attempts < self.pop_size * 5:
            p = self._generate_random_path()
            if p: population.append(p)
            attempts += 1
            
        # Eğer hiç yol bulunamadıysa erken çıkış
        if not population:
            return [], 0.0, {}

        # En iyi çözümü takip et
        global_best_path = None
        global_best_cost = float('inf')
        global_best_metrics = {}
        
        stagnation_counter = 0

        # 2. Jenerasyon Döngüsü
        for generation in range(self.max_generations):
            # Maliyetleri hesapla
            pop_costs = []
            pop_metrics = []
            
            # Her birey için fitness hesapla
            current_pop_data = []
            for ind in population:
                cost, metrics = self._calculate_fitness(ind, weights)
                current_pop_data.append((cost, ind, metrics))
            
            # Sırala (Maliyet artan sırada)
            current_pop_data.sort(key=lambda x: x[0])
            
            # En iyiyi güncelle
            best_gen_cost = current_pop_data[0][0]
            if best_gen_cost < global_best_cost:
                global_best_cost = best_gen_cost
                global_best_path = current_pop_data[0][1]
                global_best_metrics = current_pop_data[0][2]
                stagnation_counter = 0 # İyileşme var, sayacı sıfırla
            else:
                stagnation_counter += 1
            
            # Erken durdurma (Stagnation)
            if stagnation_counter >= self.stagnation_limit:
                # print(f"GA: {generation}. jenerasyonda yakınsama sağlandı.")
                break

            # 3. Yeni Jenerasyon Üretimi
            new_population = []
            
            # A. Elitizm (%10 en iyiyi aynen aktar)
            elites = [x[1] for x in current_pop_data[:self.elitism_count]]
            new_population.extend(elites)
            
            # B. Crossover ve Mutasyon ile geri kalanları üret
            costs_only = [x[0] for x in current_pop_data]
            paths_only = [x[1] for x in current_pop_data]
            
            while len(new_population) < self.pop_size:
                # Ebeveyn Seçimi
                p1 = self._tournament_selection(paths_only, costs_only)
                p2 = self._tournament_selection(paths_only, costs_only)
                
                # Çaprazlama
                child = self._crossover(p1, p2)
                
                # Mutasyon
                child = self._mutate(child)
                
                new_population.append(child)
            
            population = new_population

        return global_best_path, global_best_cost, global_best_metrics