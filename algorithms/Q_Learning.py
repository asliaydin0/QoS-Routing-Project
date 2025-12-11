import networkx as nx
import random
import math
import numpy as np

# --- 1. AĞ VE METRİK PARAMETRELERİ (Sayfa 3) ---

NODE_COUNT = 250
LINK_PROBABILITY = 0.4
MAX_BANDWIDTH = 1000  # Mbps (1 Gbps)

def create_network():
    """Erdos-Rényi G(n,p) modeli ile ağ oluşturur ve özellik atar."""
    G = nx.fast_gnp_random_graph(NODE_COUNT, LINK_PROBABILITY)

    for i in G.nodes:
        G.nodes[i]['processing_delay'] = random.uniform(0.5, 2.0)  # ms
        G.nodes[i]['node_reliability'] = random.uniform(0.95, 0.999)

    for u, v in G.edges:
        G.edges[u, v]['bandwidth'] = random.uniform(100, 1000)
        G.edges[u, v]['link_delay'] = random.uniform(3, 15)
        G.edges[u, v]['link_reliability'] = random.uniform(0.95, 0.999)

    if not nx.is_connected(G):
        print("Uyarı: Ağ bağlı değil. S-D çiftleri arasında yol varlığı kontrol edilmeli.")

    return G


# --- 2. MALİYET VE ÖDÜL FONKSİYONLARI ---

def calculate_path_metrics(G, path, S, D):
    total_delay = 0
    reliability_cost = 0
    resource_cost = 0

    for node in path:
        if node != S and node != D:
            total_delay += G.nodes[node]['processing_delay']
        reliability_cost += -math.log(G.nodes[node]['node_reliability'])

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        total_delay += G.edges[u, v]['link_delay']
        reliability_cost += -math.log(G.edges[u, v]['link_reliability'])
        resource_cost += (MAX_BANDWIDTH / G.edges[u, v]['bandwidth'])

    return total_delay, reliability_cost, resource_cost


def calculate_total_cost(delay, reliability_cost, resource_cost, W):
    return (W[0] * delay) + (W[1] * reliability_cost) + (W[2] * resource_cost)


def get_reward(total_cost, C=1000):
    if total_cost == float('inf') or total_cost <= 0:
        return -100
    return C / total_cost


# --- 3. Q-LEARNING ALGORİTMASI ---

def q_learning_routing(G, S, D, W, episodes=5000, alpha=0.5, gamma=0.9, epsilon=0.1):

    q_table = np.zeros((NODE_COUNT, NODE_COUNT))

    best_path = []
    min_cost = float('inf')

    for episode in range(episodes):
        current_node = S
        path = [S]
        is_stuck = False

        while current_node != D and not is_stuck:

            reward = 0          # <-- DAİMA TANIMLI
            max_future_q = 0    # <-- DAİMA TANIMLI

            neighbors = list(G.neighbors(current_node))

            if random.random() < epsilon:
                action_node = random.choice(neighbors)
            else:
                q_values = q_table[current_node, neighbors]
                action_node = neighbors[np.argmax(q_values)]

            next_node = action_node

            # --- 1) Sonsuz döngü kontrolü ---
            if next_node in path:
                is_stuck = True
                reward = -100
                total_cost = float('inf')
            else:
                path.append(next_node)

            # --- 2) Max Q geleceği hesapla ---
            if not is_stuck and next_node != D:
                next_neighbors = list(G.neighbors(next_node))
                if next_neighbors:
                    max_future_q = np.max(q_table[next_node, next_neighbors])

            # --- 3) Ödül Hesabı ---
            if next_node == D:
                delay, rel_cost, res_cost = calculate_path_metrics(G, path, S, D)
                total_cost = calculate_total_cost(delay, rel_cost, res_cost, W)
                reward = get_reward(total_cost)
                max_future_q = 0

                if total_cost < min_cost:
                    min_cost = total_cost
                    best_path = list(path)

            # --- 4) Q tablosu güncelleme ---
            old_q = q_table[current_node, action_node]
            new_q = old_q + alpha * (reward + gamma * max_future_q - old_q)
            q_table[current_node, action_node] = new_q

            current_node = next_node

    # --- Deterministik yol çıkarma ---
    final_path = [S]
    current_node = S
    while current_node != D and len(final_path) < NODE_COUNT + 1:
        neighbors = list(G.neighbors(current_node))
        if not neighbors:
            break

        q_values = q_table[current_node, neighbors]
        next_node = neighbors[np.argmax(q_values)]

        if next_node in final_path:
            break

        final_path.append(next_node)
        current_node = next_node

    if final_path[-1] == D:
        delay, rel_cost, res_cost = calculate_path_metrics(G, final_path, S, D)
        final_cost = calculate_total_cost(delay, rel_cost, res_cost, W)
        return final_path, final_cost, delay, 1 / math.exp(rel_cost), res_cost

    return None, float('inf'), 0, 0, 0


# --- 4. ÇALIŞTIRMA ---

if __name__ == '__main__':
    G = create_network()
    S = 0
    D = 249
    W_DELAY_FOCUS = (0.7, 0.2, 0.1)

    print(f"--- Q-Learning Rotalama Başladı (S={S} -> D={D}) ---")
    print(f"Ağırlıklar: Gecikme={W_DELAY_FOCUS[0]}, Güvenilirlik={W_DELAY_FOCUS[1]}, Kaynak={W_DELAY_FOCUS[2]}")

    path, cost, delay, reliability, resource_cost = q_learning_routing(
        G, S, D, W_DELAY_FOCUS,
        episodes=10000, alpha=0.5, gamma=0.9, epsilon=0.1
    )

    if path:
        print("\n✅ Algoritma Tarafından Bulunan En İyi Yol:")
        print(f"Yol: {path}")
        print(f"Toplam Maliyet: {cost:.4f}")
        print(f"Gecikme: {delay:.4f} ms")
        print(f"Güvenilirlik: {reliability:.4f}")
        print(f"Kaynak Maliyeti: {resource_cost:.4f}")
    else:
        print("\n❌ Geçerli bir yol bulunamadı.")
