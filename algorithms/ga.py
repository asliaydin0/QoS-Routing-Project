import random
import networkx as nx

class GeneticAlgorithm:
    def __init__(self, G, src, dst, weights):
        self.G = G
        self.src = src
        self.dst = dst
        self.weights = weights # (w_delay, w_rel, w_cost)

    def calculate_fitness(self, path):
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

        # Skor (Minimize edilmeli)
        score = (total_delay * self.weights[0]) + \
                ((1 - total_rel) * 1000 * self.weights[1]) + \
                (total_bw_cost * self.weights[2])
        return score

    def solve(self, pop_size=30, generations=20):
        population = []
        try:
            # Farklı yollar bulmaya çalış
            raw_paths = list(nx.shortest_simple_paths(self.G, self.src, self.dst, weight=None))
            population = raw_paths[:pop_size]
        except:
            return [] 

        if not population: return []

        best_path = population[0]
        best_score = self.calculate_fitness(best_path)

        for _ in range(generations):
            population.sort(key=self.calculate_fitness)
            
            if self.calculate_fitness(population[0]) < best_score:
                best_path = population[0]
                best_score = self.calculate_fitness(best_path)
            
            survivors = population[:len(population)//2]
            if len(survivors) > 1:
                random.shuffle(survivors)
            population = survivors
            
        return best_path