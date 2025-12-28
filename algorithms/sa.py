import random
import math
import copy
import networkx as nx

class SAOptimizer:
    """
    QoS Odaklı Rotalama için Simulated Annealing (Benzetimli Tavlama) Algoritması.
    Bu algoritma, metalurjideki tavlama işleminden esinlenerek karmaşık ağlarda 
    en uygun (minimum maliyetli) yolu bulmaya çalışır.
    """

    def __init__(self, manager, src, dst, bw_demand):
        """
        Algoritmanın temel değişkenlerini ve ağ parametrelerini hazırlar.
        """
        self.manager = manager      # Ağ topolojisini yöneten nesne (G grafını içerir)
        self.src = src              # Kaynak düğüm (başlangıç)
        self.dst = dst              # Hedef düğüm (bitiş)
        self.bw_demand = bw_demand  # Talep edilen minimum bant genişliği

        # --- SA Parametreleri (Soğutma Çizelgesi) ---
        self.initial_temp = 500.0     # T0: Başlangıç sıcaklığı (Yüksek olması daha fazla rastgeleliğe izin verir)
        self.final_temp = 0.1         # Tmin: Durma sıcaklığı (Sistem bu dereceye kadar soğutulur)
        self.alpha = 0.95             # Soğuma katsayısı (Sıcaklık her adımda %5 oranında düşer)
        self.max_iterations = 800     # Toplamda yapılacak maksimum deneme sayısı
        self.stagnation_limit = 50    # İyileşme olmazsa algoritmayı erken sonlandırmak için limit
        self.max_hop_limit = 15       # Yolun çok uzamasını engellemek için maksimum sekme sınırı

    def _evaluate(self, path, weights):
        """
        Bir yolun kalitesini (enerjisini) ölçer. 
        Maliyet ne kadar düşükse yol o kadar iyidir.
        """
        if not path:
            return float('inf'), {} # Yol yoksa sonsuz maliyet döndür
        # NetworkManager aracılığıyla gecikme, jitter ve kayıp bazlı maliyeti hesapla
        return self.manager.calculate_path_cost(path, weights, self.bw_demand)

    def _generate_initial_solution(self):
        """
        Arama işlemine başlamak için ilk geçerli yolu bulur (Hibrit Yaklaşım).
        """
        # 1. Aşama: Sezgisel (Heuristic) yaklaşım denemesi
        try:
            # Sadece bant genişliği yeterli olan kenarları filtrele
            valid_edges = [
                (u, v) for u, v, d in self.manager.G.edges(data=True)
                if d.get('bandwidth', 0) >= self.bw_demand
            ]
            # Filtrelenmiş kenarlarla geçici bir alt grafik oluştur
            temp_G = self.manager.G.edge_subgraph(valid_edges)
            
            # Eğer kaynak ve hedef arasında bir yol varsa en kısa olanı al
            if nx.has_path(temp_G, self.src, self.dst):
                path = nx.shortest_path(temp_G, self.src, self.dst)
                # Hop limiti içindeyse bu yolu başlangıç çözümü kabul et
                if len(path) <= self.max_hop_limit:
                    return path
        except:
            pass # Heuristic bulunamazsa rastgele yürüyüşe geç

        # 2. Aşama: Rastgele Yürüyüş (Random Walk) - 20 kez dene
        for _ in range(20):
            path = [self.src]
            visited = {self.src}
            curr = self.src
            
            while curr != self.dst:
                neighbors = list(self.manager.G.neighbors(curr))
                # Bant genişliği uyan ve döngü (cycle) oluşturmayan komşuları bul
                valid_neighbors = [
                    n for n in neighbors 
                    if n not in visited and 
                    self.manager.G[curr][n].get('bandwidth', 0) >= self.bw_demand
                ]
                
                # Sıkı kısıtla komşu bulunamazsa, en azından ziyaret edilmemiş olanlara bak
                if not valid_neighbors:
                    valid_neighbors = [n for n in neighbors if n not in visited]
                
                if not valid_neighbors: break # Çıkmaz sokak
                
                # Rastgele bir komşu seç ve ilerle
                next_node = random.choice(valid_neighbors)
                path.append(next_node)
                visited.add(next_node)
                curr = next_node
                
                if len(path) > self.max_hop_limit: break # Limit aşılırsa iptal et
            
            if curr == self.dst: # Hedefe ulaşıldıysa yolu döndür
                return path
        
        return None # Hiçbir şekilde yol bulunamadı

    def _generate_neighbor(self, current_path):
        """
        Mevcut yolda küçük değişiklikler yaparak yeni bir 'komşu' yol türetir.
        """
        if len(current_path) < 3:
            return list(current_path) # Değiştirilecek orta düğüm yoksa aynı yolu dön

        new_path = list(current_path)
        strategy = random.choice(['swap', 'rebuild']) # Değiştirme mi yoksa yeniden inşa mı?

        if strategy == 'swap':
            # --- Yöntem 1: Düğüm Değiştirme (Swap) ---
            idx = random.randint(1, len(new_path) - 2) # Baş ve son hariç bir nokta seç
            prev_node = new_path[idx-1]
            next_node = new_path[idx+1]
            
            # Önceki ve sonraki düğümlerin ortak komşularını bul (yol kopmasın diye)
            common = list(
                set(self.manager.G.neighbors(prev_node)) & 
                set(self.manager.G.neighbors(next_node))
            )
            # Mevcut yolda zaten bulunmayan adayları filtrele
            candidates = [n for n in common if n not in new_path]
            
            if candidates:
                new_path[idx] = random.choice(candidates) # Rastgele biriyle değiştir
                return new_path

        # --- Yöntem 2: Alt Yol İnşası (Rebuild) ---
        cut_idx = random.randint(1, len(new_path) - 2) # Yolu ortadan bir yerden kes
        prefix = new_path[:cut_idx+1] # Kesilen yere kadar olan kısmı koru
        curr = prefix[-1]
        
        # Kesilen noktadan hedefe BFS (Genişlik Öncelikli Arama) ile kısa bir yol ara
        queue = [(curr, [curr])]
        visited_local = {curr}
        temp_visited = set(prefix)
        depth_limit = 5 # Çok uzağa sapmadan lokal bir değişim yap
        path_found = None
        
        iterations = 0
        while queue and iterations < 50:
            node, p = queue.pop(0)
            iterations += 1
            if len(p) > depth_limit: continue
            
            if node == self.dst: # Hedef bulunursa prefix ile birleştir
                path_found = prefix + p[1:]
                break
            
            neighbors = list(self.manager.G.neighbors(node))
            random.shuffle(neighbors) # Çeşitlilik için komşuları karıştır
            for n in neighbors:
                if n not in temp_visited and n not in visited_local:
                    visited_local.add(n)
                    queue.append((n, p + [n]))
        
        if path_found and len(path_found) <= self.max_hop_limit:
            return path_found

        return list(current_path) # Yeni yol üretilemezse orijinali dön

    def solve(self, weights):
        """
        Simulated Annealing algoritmasını çalıştıran ana motor.
        """
        # 1. Başlangıç çözümünü oluştur
        current_path = self._generate_initial_solution()
        if not current_path:
            return [], 0.0, {} # Yol bulunamazsa boş dön

        # İlk çözümün maliyetini hesapla
        current_cost, current_metrics = self._evaluate(current_path, weights)
        
        # En iyi çözümü takip etmek için değişkenleri ilklendir
        best_path = list(current_path)
        best_cost = current_cost
        best_metrics = current_metrics
        
        # 2. Tavlama (Döngü) Başlangıcı
        T = self.initial_temp
        iteration = 0
        stagnation_counter = 0

        # Sistem soğuyana veya max iterasyona ulaşana kadar dön
        while T > self.final_temp and iteration < self.max_iterations:
            # A. Mevcut yola komşu yeni bir yol üret
            neighbor_path = self._generate_neighbor(current_path)
            
            # B. Yeni yolun maliyetini hesapla
            neighbor_cost, neighbor_metrics = self._evaluate(neighbor_path, weights)
            
            # C. Enerji farkını (maliyet farkını) hesapla
            delta_E = neighbor_cost - current_cost
            
            # D. Kabul Kriteri (Metropolis Algoritması)
            accepted = False
            if delta_E < 0:
                # Yeni yol daha iyiyse doğrudan kabul et
                accepted = True
            else:
                # Yeni yol daha kötüyse, sıcaklığa bağlı bir olasılıkla kabul et
                # Bu adım 'yerel minimum' tuzaklarından kurtulmayı sağlar.
                try:
                    prob = math.exp(-delta_E / T) # Kabul olasılığı formülü
                except OverflowError:
                    prob = 0
                
                if random.random() < prob:
                    accepted = True
            
            # E. Eğer yeni çözüm kabul edildiyse güncelle
            if accepted:
                current_path = neighbor_path
                current_cost = neighbor_cost
                current_metrics = neighbor_metrics
                
                # Eğer bu yeni yol şimdiye kadar bulunan en iyi yolsa kaydet
                if current_cost < best_cost:
                    best_path = list(current_path)
                    best_cost = current_cost
                    best_metrics = current_metrics
                    stagnation_counter = 0 # İyileşme olduğu için sayacı sıfırla
                else:
                    stagnation_counter += 1
            else:
                stagnation_counter += 1
            
            # F. Sıcaklığı düşür (Sistem soğuyor)
            T *= self.alpha
            iteration += 1
            
            # G. Erken Durdurma (Stagnation)
            # Sıcaklık iyice düştüyse ve uzun süredir iyileşme yoksa aramayı bitir
            if stagnation_counter > self.stagnation_limit and T < (self.initial_temp * 0.1):
                break

        # Bulunan en iyi yolu, maliyeti ve metrikleri döndür
        return best_path, best_cost, best_metrics