import pytest
from core.network_generator import generate_network
from algorithms.ga import find_ga_path

def test_ga_basic_run():
    """GA algoritmasının temel olarak çalıştığını doğrular."""
    
    # Ağ üret
    G = generate_network(n_nodes=250, p=0.4, seed=12345)

    # GA çalıştır
    path, cost, metrics = find_ga_path(G, start=0, goal=249, seed=42)

    # --- TEST 1: path bulunmuş mu? ---
    assert path is not None, "GA path üretmedi!"
    assert len(path) > 1, "GA en az 2 düğümlü bir yol bulmalı!"

    # --- TEST 2: cost pozitif mi? ---
    assert cost > 0, "GA maliyeti pozitif olmalı!"

    # --- TEST 3: metrics çıktıları doğru mu? ---
    assert "delay" in metrics
    assert "reliability_cost" in metrics
    assert "resource_cost" in metrics
    assert "runtime_sec" in metrics

    # --- TEST 4: metrikler pozitif mi? ---
    assert metrics["delay"] > 0
    assert metrics["reliability_cost"] > 0
    assert metrics["resource_cost"] > 0
    assert metrics["runtime_sec"] >= 0  # runtime sıfır bile olabilir

def test_ga_different_seed():
    """Farklı seed ile GA çalışınca farklı/kararlı çıktılar üretiyor mu?"""

    G = generate_network(n_nodes=250, p=0.4, seed=54321)

    path1, cost1, _ = find_ga_path(G, 0, 249, seed=1)
    path2, cost2, _ = find_ga_path(G, 0, 249, seed=2)

    # Aynı yolu bulmak zorunda değil, ama çalışmış olmalı
    assert path1 is not None
    assert path2 is not None

    # En azından maliyetler float tipinde olmalı
    assert isinstance(cost1, float)
    assert isinstance(cost2, float)
