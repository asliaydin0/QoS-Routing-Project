from comparison import get_graph_and_demands, run_single

def test_frontend_backend_connected(capsys):
    G, df = get_graph_and_demands()
    assert G is not None and df is not None and len(df) > 0

    row = df.iloc[0]
    src = int(row["src"])
    dst = int(row["dst"])
    bw  = float(row["demand_mbps"])

    path, cost, metrics = run_single("GA", G, src, dst, bw)

    print("=== CONNECTED OK ===")
    print("nodes:", G.number_of_nodes())
    print("scenario:", src, "->", dst, "bw:", bw)
    print("path_len:", len(path) if path else 0)
    print("cost:", cost)
    print("time_ms:", metrics.get("time_ms") if metrics else None)

    out = capsys.readouterr().out
    assert "=== CONNECTED OK ===" in out
