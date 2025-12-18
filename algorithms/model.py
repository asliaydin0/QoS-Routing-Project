import pandas as pd
import networkx as nx
import random
import copy
import time
import numpy as np
import argparse
import sys
import os
import math

class NetworkManager:
    def __init__(self, node_file, edge_file):
        self.node_file = node_file
        self.edge_file = edge_file
        self.G = nx.DiGraph()
        self._load_data()

    def _clean_float(self, x):
        if isinstance(x, str):
            return float(x.replace(',', '.'))
        return x

    def _load_data(self):
        try:
            node_df = pd.read_csv(self.node_file, sep=';')
            edge_df = pd.read_csv(self.edge_file, sep=';')
        except Exception as e:
            print(f"Hata: Veri dosyaları okunamadı. {e}")
            sys.exit(1)

        for col in ['s_ms', 'r_node']:
            node_df[col] = node_df[col].apply(self._clean_float)
        
        for _, row in node_df.iterrows():
            self.G.add_node(int(row['node_id']), 
                            processing_delay=row['s_ms'], 
                            reliability=row['r_node'])

        for col in ['r_link']:
            edge_df[col] = edge_df[col].apply(self._clean_float)
            
        for _, row in edge_df.iterrows():
            self.G.add_edge(int(row['src']), int(row['dst']), 
                            capacity=row['capacity_mbps'], 
                            delay=row['delay_ms'], 
                            reliability=row['r_link'],
                            original_capacity=row['capacity_mbps'])

    def get_graph(self):
        return self.G

    def check_node_exists(self, node_id):
        return node_id in self.G.nodes

    def check_connectivity(self, src, dst):
        return nx.has_path(self.G, src, dst)

class ABC_Manager:
    def __init__(self, graph_manager):
        self.manager = graph_manager
        self.G = graph_manager.get_graph()
        
        self.params = {
            'pop_size': 20,
            'max_iter': 50,
            'limit': 5,
            'w_delay': 0.33,
            'w_rel': 0.33,
            'w_res': 0.34
        }

    def calculate_fitness(self, path):
        if not path:
            return float('inf'), 0, 0, 0

        total_delay = 0
        reliability_cost = 0.0
        resource_cost = 0.0
        real_reliability_product = 1.0
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            try:
                data = self.G[u][v]
                total_delay += data['delay']
                
                r_val = data['reliability']
                if r_val <= 0: r_val = 1e-9
                elif r_val > 1: r_val = 1.0
                
                reliability_cost += -math.log(r_val)
                real_reliability_product *= r_val
                
                bw = data['capacity']
                if bw <= 0: bw = 0.001
                resource_cost += (1000.0 / bw)
            except KeyError:
                return float('inf'), 0, 0, 0
            
        for node in path:
            data = self.G.nodes[node]
            
            if node != path[0] and node != path[-1]:
                total_delay += data['processing_delay']
            
            r_node = data['reliability']
            if r_node <= 0: r_node = 1e-9
            elif r_node > 1: r_node = 1.0
            
            reliability_cost += -math.log(r_node)
            real_reliability_product *= r_node

        score = (self.params['w_delay'] * total_delay) + \
                (self.params['w_rel'] * reliability_cost) + \
                (self.params['w_res'] * resource_cost)
        
        return score, total_delay, real_reliability_product, resource_cost

    def _random_path_weighted(self, src, dst, demand):
        valid_edges = [(u, v, d) for u, v, d in self.G.edges(data=True) if d['capacity'] >= demand]
        if not valid_edges: return None
        
        temp_G = nx.DiGraph()
        for u, v, d in valid_edges:
            temp_G.add_edge(u, v, weight=random.randint(1, 100))
            
        try:
            return nx.shortest_path(temp_G, source=src, target=dst, weight='weight')
        except nx.NetworkXNoPath:
            return None

    def _mutate(self, path, src, dst, demand):
        if len(path) <= 2: return path
        
        pivot_idx = random.randint(0, len(path) - 2)
        pivot_node = path[pivot_idx]
        
        new_tail = self._random_path_weighted(pivot_node, dst, demand)
        
        if new_tail:
            new_path = path[:pivot_idx] + new_tail
            if len(new_path) == len(set(new_path)):
                return new_path
        
        return path 

    def run_algorithm(self, src, dst, demand):
        if not self.manager.check_node_exists(src) or not self.manager.check_node_exists(dst):
            return None

        population = []
        for _ in range(self.params['pop_size']):
            p = self._random_path_weighted(src, dst, demand)
            if p:
                fit, d, r, res = self.calculate_fitness(p)
                population.append({'path': p, 'fit': fit, 'd': d, 'r': r, 'res': res, 'trial': 0})

        if not population:
            return None

        best_sol = min(population, key=lambda x: x['fit'])

        for iter_no in range(self.params['max_iter']):
            for i in range(len(population)):
                new_path = self._mutate(population[i]['path'], src, dst, demand)
                fit, d, r, res = self.calculate_fitness(new_path)
                if fit < population[i]['fit']:
                    population[i] = {'path': new_path, 'fit': fit, 'd': d, 'r': r, 'res': res, 'trial': 0}
                else:
                    population[i]['trial'] += 1

            fitness_values = [1.0 / (ind['fit'] + 1e-9) for ind in population]
            total_fit = sum(fitness_values)
            probs = [f / total_fit for f in fitness_values]
            
            for _ in range(self.params['pop_size']):
                idx = np.random.choice(range(len(population)), p=probs)
                new_path = self._mutate(population[idx]['path'], src, dst, demand)
                fit, d, r, res = self.calculate_fitness(new_path)
                if fit < population[idx]['fit']:
                    population[idx] = {'path': new_path, 'fit': fit, 'd': d, 'r': r, 'res': res, 'trial': 0}
                else:
                    population[idx]['trial'] += 1

            for i in range(len(population)):
                if population[i]['trial'] > self.params['limit']:
                    p = self._random_path_weighted(src, dst, demand)
                    if p:
                        fit, d, r, res = self.calculate_fitness(p)
                        population[i] = {'path': p, 'fit': fit, 'd': d, 'r': r, 'res': res, 'trial': 0}

            current_best = min(population, key=lambda x: x['fit'])
            if current_best['fit'] < best_sol['fit']:
                best_sol = copy.deepcopy(current_best)

        return {
            'path': best_sol['path'],
            'total_delay': round(best_sol['d'], 2),
            'total_reliability': round(best_sol['r'], 4),
            'resource_cost': round(best_sol['res'], 2),
            'fitness': round(best_sol['fit'], 2),
            'hop_count': len(best_sol['path']) - 1
        }

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, 'data')

    node_path = os.path.join(data_dir, "BSM307_317_Guz2025_TermProject_NodeData(in).csv")
    edge_path = os.path.join(data_dir, "BSM307_317_Guz2025_TermProject_EdgeData(in).csv")
    
    if not os.path.exists(node_path):
        if os.path.exists("BSM307_317_Guz2025_TermProject_NodeData(in).csv"):
            node_path = "BSM307_317_Guz2025_TermProject_NodeData(in).csv"
            edge_path = "BSM307_317_Guz2025_TermProject_EdgeData(in).csv"
        else:
            print("Veri dosyaları bulunamadı.")
            sys.exit(1)
        
    parser = argparse.ArgumentParser(description="ABC QoS Routing")
    parser.add_argument('--src', type=int, help="Source Node ID", default=8)
    parser.add_argument('--dst', type=int, help="Destination Node ID", default=44)
    parser.add_argument('--demand', type=float, help="Bandwidth Demand", default=200)
    
    args = parser.parse_args()

    print(f"ABC Algoritması Çalışıyor... Kaynak: {args.src}, Hedef: {args.dst}, Talep: {args.demand} Mbps")

    net_manager = NetworkManager(node_path, edge_path)
    abc_manager = ABC_Manager(net_manager)
    
    start_time = time.time()
    result = abc_manager.run_algorithm(args.src, args.dst, args.demand)
    total_time = time.time() - start_time

    if result:
        print("\nSONUÇ:")
        print(f"Rota: {result['path']}")
        print(f"Toplam Gecikme: {result['total_delay']} ms")
        print(f"Toplam Güvenilirlik: %{result['total_reliability']*100:.4f}")
        print(f"Kaynak Maliyeti: {result['resource_cost']:.2f}")
        print(f"Fitness: {result['fitness']:.4f}")
        print(f"Hop Sayısı: {result['hop_count']}")
        print(f"Süre: {total_time:.4f} sn")
    else:
        print("\nRota bulunamadı (Kapasite yetersiz veya bağlantı yok).")