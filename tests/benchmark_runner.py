import pandas as pd
import numpy as np
import time
import sys
import os

# Add project root to sys.path to allow imports from 'algorithms' and 'network_manager'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from network_manager import NetworkManager
from algorithms.ga import GeneticOptimizer
from algorithms.ql import QLearningOptimizer
from algorithms.sa import SAOptimizer
from algorithms.abc_alg import ABCOptimizer

if __name__ == "__main__":
    # 1. Setup Network Manager and Load Data
    manager = NetworkManager()
    
    # Construct absolute paths to data files
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    
    node_file = os.path.join(data_dir, 'BSM307_317_Guz2025_TermProject_NodeData(in).csv')
    edge_file = os.path.join(data_dir, 'BSM307_317_Guz2025_TermProject_EdgeData(in).csv')
    demand_file = os.path.join(data_dir, 'BSM307_317_Guz2025_TermProject_DemandData(in).csv')

    print("Loading data...")
    if not manager.load_data(node_file, edge_file, demand_file):
        print("Failed to load data. Exiting.")
        sys.exit(1)

    # 2. Define Weight Scenarios
    weight_scenarios = [
        ("Balanced", [0.33, 0.33, 0.34]),       # Dengeli senaryo
        ("Speed_Focus", [1.0, 0.0, 0.0]),       # Sadece Hıza Odaklı
        ("Reliability_Focus", [0.0, 1.0, 0.0])  # Sadece Güvenilirliğe Odaklı
    ]

    # 3. Define Algorithms to Test
    algorithms = [
        ("GeneticAlgo", GeneticOptimizer),
        ("QLearning", QLearningOptimizer),
        ("SimulatedAnnealing", SAOptimizer),
        ("ArtBeeColony", ABCOptimizer)
    ]

    # Test cases: First 20 demands
    # manager.demands is a list of dicts: [{'src': s, 'dst': d, 'bw': bw}, ...]
    test_cases = manager.demands[:20] 

    experiment_results = []
    REPETITIONS = 5

    print("\n" + "="*80)
    print(f"STARTING BENCHMARK: {len(algorithms)} Algorithms x {len(weight_scenarios)} Weight Profiles x {len(test_cases)} Cases")
    print("="*80 + "\n")

    # --- Main Loop ---
    for w_name, w_vals in weight_scenarios:
        print(f"\n>>> Testing Weight Profile: {w_name} {w_vals}")
        
        for algo_name, AlgoClass in algorithms:
            print(f"  > Algorithm: {algo_name}")
            
            for idx, demand_data in enumerate(test_cases):
                src = demand_data['src']
                dst = demand_data['dst']
                bw_demand = demand_data['bw']
                
                scenario_costs = []
                scenario_delays = []
                scenario_reliabilities = []
                scenario_res_costs = []
                scenario_times = []
                
                print(f"    - Case {idx + 1}/{len(test_cases)} (Src: {src} -> Dst: {dst})")
                
                for rep in range(REPETITIONS):
                    print(f"      .. Rep {rep + 1}/{REPETITIONS}", end="\r", flush=True) 
                    start_time = time.time()
                    
                    # Instantiate optimizer
                    optimizer = AlgoClass(manager, src, dst, bw_demand)
                    
                    # Execute algorithm
                    path, cost, metrics = optimizer.solve(weights=w_vals)
                    
                    duration = time.time() - start_time
                    
                    if path:
                        # Consistency with GUI: Clean the cost (remove penalty) for statistics
                        clean_cost = cost
                        if cost > 1000000:
                            clean_cost -= 1000000
                        scenario_costs.append(clean_cost)
                        
                        scenario_delays.append(metrics.get('delay', float('inf')))
                        scenario_reliabilities.append(metrics.get('rel_prob', 0.0))
                        scenario_res_costs.append(metrics.get('res_cost', float('inf')))
                    else:
                        scenario_costs.append(float('inf'))
                        scenario_delays.append(float('inf'))
                        scenario_reliabilities.append(0.0)
                        scenario_res_costs.append(float('inf'))
                    
                    scenario_times.append(duration)

                # Calculate statistics
                valid_costs = [c for c in scenario_costs if c != float('inf')]
                valid_delays = [d for d in scenario_delays if d != float('inf')]
                valid_reliabilities = [r for r in scenario_reliabilities if r > 0.0] # Keeping it simple, strict > 0
                valid_res_costs = [rc for rc in scenario_res_costs if rc != float('inf')]
                
                if valid_costs:
                    mean_val = np.mean(valid_costs)
                    std_val = np.std(valid_costs)
                    best_val = np.min(valid_costs)
                    
                    mean_delay = np.mean(valid_delays) if valid_delays else 0
                    mean_rel = np.mean(valid_reliabilities) if valid_reliabilities else 0
                    mean_res = np.mean(valid_res_costs) if valid_res_costs else 0

                    avg_time = np.mean(scenario_times)
                    success_rate = (len(valid_costs) / REPETITIONS) * 100
                else:
                    mean_val = std_val = best_val = avg_time = 0
                    mean_delay = mean_rel = mean_res = 0
                    success_rate = 0

                experiment_results.append({
                    "Algorithm": algo_name,
                    "Weight_Profile": w_name,
                    "Case_ID": idx + 1,
                    "Source": src,
                    "Destination": dst,
                    "Success_Rate": success_rate,
                    "Mean_Cost": round(mean_val, 4),
                    "Mean_Delay": round(mean_delay, 4),
                    "Mean_Reliability": round(mean_rel, 4),
                    "Mean_Resource_Cost": round(mean_res, 4),
                    "Std_Dev": round(std_val, 4),
                    "Best_Cost": round(best_val, 4),
                    "Avg_Time": round(avg_time, 4)
                })

    # 4. Save Results
    df_final = pd.DataFrame(experiment_results)
    output_file = "Final_Project_Benchmark_Results.csv"
    df_final.to_csv(output_file, sep=';', index=False)
    
    print("\n" + "="*80)
    print(f"DONE! All results saved to '{output_file}'")