import networkx as nx
from core.network_generator import generate_network
from core.metrics import (
    calculate_delay,
    calculate_reliability_cost,
    calculate_resource_cost,
    calculate_total_cost
)

def test_generate_network():
    G = generate_network(n_nodes=250, p=0.4, seed=12345)
    
    # Test 1: node sayısı doğru mu?
    assert G.number_of_nodes() == 250, "Node sayısı yanlış!"

    # Test 2: en az bir edge olmalı
    assert G.number_of_edges() > 0, "Graf tamamen boş!"

def test_shortest_path_metrics():
    G = generate_network(n_nodes=250, p=0.4, seed=12345)

    start, goal = 0, 249
    path = nx.shortest_path(G, source=start, target=goal)

    # Test 3: path bulunmalı
    assert len(path) > 1, "Shortest path bulunamadı!"

    delay = calculate_delay(path, G)
    reliability = calculate_reliability_cost(path, G)
    resource = calculate_resource_cost(path, G)
    total = calculate_total_cost(path, G, 0.5, 0.3, 0.2)

    # Test 4: metrikler pozitif olmalı
    assert delay > 0
    assert reliability > 0
    assert resource > 0
    assert total > 0
