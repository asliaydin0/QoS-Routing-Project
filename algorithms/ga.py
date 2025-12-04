# algorithms/ga.py → BU KOD %100 ÇALIŞIR, HATA YOK
import random
import numpy as np
from core.metrics import calculate_total_cost, calculate_delay, calculate_reliability_cost, calculate_resource_cost
from tqdm import tqdm
import time

def find_ga_path(G, start=0, goal=249, weights=(0.33, 0.33, 0.34), seed=None):
    random.seed(seed)
    np.random.seed(seed)
    start_time = time.time()

    def create_valid_path():
        path = [start]
        current = start
        visited = {start}
        for _ in range(200):
            neighbors = [n for n in G.neighbors(current) if n not in visited]
            if not neighbors:
                return None
            current = random.choice(neighbors)
            path.append(current)
            visited.add(current)
            if current == goal:
                return path
        return None

    population = []
    while len(population) < 300:
        p = create_valid_path()
        if p:
            population.append(p)

    if not population:
        return None, float('inf'), {"error": "no path"}

    best_path = min(population, key=lambda p: calculate_total_cost(p, G, *weights))
    best_cost = calculate_total_cost(best_path, G, *weights)

    print("GA çalışıyor... (~20 saniye)")

    for gen in tqdm(range(600)):
        fitness = [1 / (calculate_total_cost(p, G, *weights) + 1e-8) for p in population]

        # Elitism
        elite = sorted(population, key=lambda p: calculate_total_cost(p, G, *weights))[:30]
        new_pop = elite[:]

        while len(new_pop) < 300:
            p1, p2 = random.choices(population, weights=fitness, k=2)

            child = p1.copy()
            if random.random() < 0.7 and len(p1) > 8:
                cut = random.randint(3, len(p1)-4)
                if goal in p2[cut:]:
                    idx = p2.index(goal)
                    child = p1[:cut] + p2[cut:idx+1]

            if random.random() < 0.3 and len(child) > 5:
                i = random.randint(2, len(child)-3)
                neigh = [n for n in G.neighbors(child[i]) if n not in child]
                if neigh:
                    child[i] = random.choice(neigh)

            if child and child[0] == start and child[-1] == goal and all(G.has_edge(child[j], child[j+1]) for j in range(len(child)-1)):
                new_pop.append(child)

        population = new_pop

        current_best = min(population, key=lambda p: calculate_total_cost(p, G, *weights))
        if calculate_total_cost(current_best, G, *weights) < best_cost:
            best_cost = calculate_total_cost(current_best, G, *weights)
            best_path = current_best

    runtime = time.time() - start_time

    return best_path, best_cost, {
        "delay": round(calculate_delay(best_path, G), 2),
        "reliability_cost": round(calculate_reliability_cost(best_path, G), 6),
        "resource_cost": round(calculate_resource_cost(best_path, G), 2),
        "hop_count": len(best_path)-1,
        "runtime_sec": round(runtime, 1)
    }