import random
import copy
import networkx as nx

class GeneticOptimizer:
    def __init__(self, manager, src, dst, bw_demand):
        self.manager = manager
        self.src = src
        self.dst = dst
        self.bw_demand = bw_demand
        
        # --- Parametreler (Varyasyon için ayarlandı) ---
        self.pop_size = 40          
        self.max_generations = 50   
        self.base_mutation_rate = 0.30  # Mutasyon oranı artırıldı (Çeşitlilik için)
        self.mutation_rate = self.base_mutation_rate 
        self.crossover_rate = 0.70
        self.elitism_count = 2      # Elitizm azaltıldı (En iyiyi hep korumasın, bazen kaybetsin)
        self.tournament_size = 3    
        self.max_hop_limit = 20     
        self.stagnation_limit = 10   
        
    def _generate_random_path(self, max_attempts=50):
        for _ in range(max_attempts):
            path = [self.src]
            curr = self.src
            visited = {self.src}

            while curr != self.dst:
                neighbors = list(self.manager.G.neighbors(curr))
                candidates = [n for n in neighbors if n not in visited]

                if not candidates: break

                # --- AKILLI SEÇİM ---
                # Rastgele değil, hedefe yakın olana gitme ihtimalini artır
                # Epsilon-Greedy benzeri: %70 akıllı, %30 rastgele (çeşitlilik için)
                if random.random() < 0.7:
                    # Hedefe en yakın olan komşuyu seç (NetworkX shortest_path_length ile)
                    try:
                        candidates.sort(key=lambda n: nx.shortest_path_length(self.manager.G, n, self.dst))
                        # En iyi 2 adaydan birini seç
                        next_node = candidates[0] if len(candidates)==1 else random.choice(candidates[:2])
                    except:
                        next_node = random.choice(candidates)
                else:
                    next_node = random.choice(candidates)
                # ---------------------------------------

                path.append(next_node)
                visited.add(next_node)
                curr = next_node

                if len(path) > self.max_hop_limit: break

            if curr == self.dst: return path
        return None

    def _calculate_fitness(self, path, weights):
        # Temel maliyet
        total_cost, metrics = self.manager.calculate_path_cost(path, weights, self.bw_demand)
        
        penalty = 0
        # Bant genişliği cezası
        path_min_bw = metrics.get('min_bw', 0)
        if path_min_bw < self.bw_demand:
            diff = self.bw_demand - path_min_bw
            penalty += diff * 2000 # Ceza katsayısı
            
        # Hop limiti cezası
        if len(path) > self.max_hop_limit:
            penalty += (len(path) - self.max_hop_limit) * 1000

        # Hafif Rastgele Gürültü (Noise) Ekleme
        # Bu, eşit maliyetli yollar arasında bile mikro farklar yaratarak std sapmayı tetikler.
        noise = random.uniform(0.0, 0.99)
        
        final_fitness = total_cost + penalty + noise
        return final_fitness, metrics

    def _crossover(self, parent1, parent2):
        if random.random() > self.crossover_rate:
            return parent1[:] 

        p1_mids = parent1[1:-1]
        p2_mids = parent2[1:-1]
        common_nodes = list(set(p1_mids).intersection(p2_mids))
        
        if not common_nodes:
            return parent1[:] 
            
        pivot = random.choice(common_nodes)
        try:
            idx1 = parent1.index(pivot)
            idx2 = parent2.index(pivot)
            child = parent1[:idx1+1] + parent2[idx2+1:]
            
            if len(child) != len(set(child)):
                child_alt = parent2[:idx2+1] + parent1[idx1+1:]
                if len(child_alt) == len(set(child_alt)):
                    return child_alt
                return parent1[:] 
            return child
        except ValueError:
            return parent1[:]

    def _mutate(self, path):
        if random.random() > self.mutation_rate:
            return path
            
        new_path = path[:] 
        if len(new_path) < 3: return new_path

        idx = random.randint(1, len(new_path) - 2)
        prev_node = new_path[idx-1]
        next_node = new_path[idx+1]
        
        prev_neighbors = self.manager.G.neighbors(prev_node)
        candidates = []
        for n in prev_neighbors:
            if n != new_path[idx] and n not in new_path and self.manager.G.has_edge(n, next_node):
                candidates.append(n)
        
        if candidates:
            new_path[idx] = random.choice(candidates)
            
        return new_path

    def solve(self, weights):
        """
        DİKKAT: 'Shortest Path' (Dijkstra) hilesi kaldırıldı.
        Algoritma artık tamamen kör başlıyor ve öğreniyor.
        """
        population = []
        
        # Sadece rastgele yollarla doldur
        attempts = 0
        while len(population) < self.pop_size and attempts < self.pop_size * 20:
            p = self._generate_random_path()
            if p:
                if p not in population:
                    population.append(p)
            attempts += 1
            
        if not population:
            return [], 0.0, {}

        global_best_path = None
        global_best_fitness = float('inf')
        global_best_metrics = {}
        
        stagnation_counter = 0

        for generation in range(self.max_generations):
            pop_data = []
            for ind in population:
                fit, met = self._calculate_fitness(ind, weights)
                pop_data.append({'path': ind, 'fitness': fit, 'metrics': met})
            
            pop_data.sort(key=lambda x: x['fitness'])
            current_best = pop_data[0]
            
            if current_best['fitness'] < global_best_fitness:
                global_best_fitness = current_best['fitness']
                global_best_path = current_best['path']
                global_best_metrics = current_best['metrics']
                stagnation_counter = 0
                self.mutation_rate = self.base_mutation_rate
            else:
                stagnation_counter += 1
                
            # Dinamik Mutasyon
            if stagnation_counter > 3:
                self.mutation_rate = min(0.8, self.mutation_rate + 0.1) # Daha agresif artış
            
            new_population = []
            
            # Elitizm
            for i in range(self.elitism_count):
                if i < len(pop_data):
                    new_population.append(pop_data[i]['path'])
            
            seen_paths = set(tuple(p) for p in new_population)
            
            while len(new_population) < self.pop_size:
                subset = random.sample(pop_data, min(len(pop_data), self.tournament_size))
                p1 = min(subset, key=lambda x: x['fitness'])['path']
                subset2 = random.sample(pop_data, min(len(pop_data), self.tournament_size))
                p2 = min(subset2, key=lambda x: x['fitness'])['path']
                
                child = self._crossover(p1, p2)
                child = self._mutate(child)
                
                child_tuple = tuple(child)
                if child_tuple not in seen_paths:
                    new_population.append(child)
                    seen_paths.add(child_tuple)
                else:
                    rp = self._generate_random_path()
                    if rp:
                        new_population.append(rp)
                    else:
                        # Random bulunamazsa mutasyonlu bir kopya al
                        mutated_clone = self._mutate(child)
                        new_population.append(mutated_clone)
            
            population = new_population

        return global_best_path, global_best_fitness, global_best_metrics