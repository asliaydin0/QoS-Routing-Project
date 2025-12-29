import random
import copy
import networkx as nx

class GeneticOptimizer:
    def __init__(self, manager, src, dst, bw_demand):
        self.manager = manager
        self.src = src
        self.dst = dst
        self.bw_demand = bw_demand
        
        # --- Parametreler ---
        self.pop_size = 40          
        self.max_generations = 50   
        self.mutation_rate = 0.30 
        self.crossover_rate = 0.70
        self.elitism_count = 2      
        self.tournament_size = 3    
        self.max_hop_limit = 20     
        self.stagnation_limit = 12   

        # --- GÜVENLİ OPTİMİZASYON ---
        self.dist_map = {}
        try:
            # Hedefe olan uzaklıkları hesapla (İpucu olarak)
            self.dist_map = dict(nx.single_source_shortest_path_length(self.manager.G, self.dst))
        except:
            self.dist_map = {}

    def _generate_random_path(self, max_attempts=50):
        for _ in range(max_attempts):
            path = [self.src]
            curr = self.src
            visited = {self.src}

            while curr != self.dst:
                try:
                    neighbors = list(self.manager.G.neighbors(curr))
                except:
                    break 
                
                candidates = [n for n in neighbors if n not in visited]

                if not candidates: break

                # --- AKILLI SEÇİM ---
                if self.dist_map and random.random() < 0.7:
                    # Hedefe yakın olanları öne al
                    candidates.sort(key=lambda n: self.dist_map.get(n, float('inf')))
                    
                    if len(candidates) >= 2:
                        next_node = candidates[0] if random.random() < 0.8 else candidates[1]
                    else:
                        next_node = candidates[0]
                else:
                    next_node = random.choice(candidates)

                path.append(next_node)
                visited.add(next_node)
                curr = next_node

                if len(path) > self.max_hop_limit: break

            if curr == self.dst: return path
        return None

    def _calculate_fitness(self, path, weights):
        total_cost, metrics = self.manager.calculate_path_cost(path, weights, self.bw_demand)
        
        penalty = 0
        path_min_bw = metrics.get('min_bw', 0)
        
        if path_min_bw < self.bw_demand:
            penalty += (self.bw_demand - path_min_bw) * 2000
        if len(path) > self.max_hop_limit:
            penalty += (len(path) - self.max_hop_limit) * 1000

        noise = random.uniform(0.0, 0.99)
        return total_cost + penalty + noise, metrics

    def _crossover(self, parent1, parent2):
        if random.random() > self.crossover_rate: return parent1[:]
        
        p1_mids = parent1[1:-1]
        p2_mids = set(parent2[1:-1])
        common = [n for n in p1_mids if n in p2_mids]
        
        if not common: return parent1[:]
        
        pivot = random.choice(common)
        try:
            idx1 = parent1.index(pivot)
            idx2 = parent2.index(pivot)
            child = parent1[:idx1+1] + parent2[idx2+1:]
            
            if len(child) != len(set(child)):
                return parent1[:]
            return child
        except:
            return parent1[:]

    def _mutate(self, path):
        if random.random() > self.mutation_rate or len(path) < 3:
            return path
            
        new_path = path[:]
        try:
            idx = random.randint(1, len(new_path) - 2)
            prev_node = new_path[idx-1]
            next_node = new_path[idx+1]
            
            candidates = [n for n in self.manager.G[prev_node] 
                          if n != new_path[idx] and n not in new_path and self.manager.G.has_edge(n, next_node)]
            
            if candidates:
                new_path[idx] = random.choice(candidates)
        except:
            pass
            
        return new_path

    def solve(self, weights):
        population = []
        attempts = 0
        
        # Başlangıç popülasyonunu oluştur
        while len(population) < self.pop_size and attempts < self.pop_size * 20:
            p = self._generate_random_path()
            if p: 
                # Aynı yolu tekrar ekleme
                if not any(p == existing for existing in population):
                    population.append(p)
            attempts += 1
            
        if not population: return [], 0.0, {}

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
            else:
                stagnation_counter += 1

            if stagnation_counter >= 15:
                break
            
            # --- YENİ NESİL OLUŞTURMA (HATA DÜZELTME BURADA) ---
            new_population = [d['path'] for d in pop_data[:self.elitism_count]]
            
            while len(new_population) < self.pop_size:
                # EĞER YETERLİ POPÜLASYON YOKSA CROSSOVER YAPMA
                if len(pop_data) < 2:
                    # Yeterli ebeveyn yok, rastgele yeni yol üretmeye çalış
                    p = self._generate_random_path()
                    if p: new_population.append(p)
                    else: 
                        # Rastgele de bulamazsan eldekini mutasyona uğratıp ekle
                        new_population.append(self._mutate(pop_data[0]['path']))
                    continue

                # Yeterli eleman varsa Turnuva yap
                sample_size = min(len(pop_data), 5)
                # Garanti kontrol: sample_size en az 2 olmalı
                if sample_size < 2: sample_size = 2
                
                try:
                    parents = random.sample(pop_data, sample_size)
                    parents.sort(key=lambda x: x['fitness'])
                    
                    # Artık parents[0] ve parents[1] garantili
                    child = self._crossover(parents[0]['path'], parents[1]['path'])
                    child = self._mutate(child)
                    new_population.append(child)
                except ValueError:
                    # Çok nadir durumda sample alınamazsa
                    new_population.append(self._mutate(pop_data[0]['path']))
            
            population = new_population

        return global_best_path, global_best_fitness, global_best_metrics