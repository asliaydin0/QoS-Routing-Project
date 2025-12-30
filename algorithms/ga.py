import random
import copy
import networkx as nx

class GeneticOptimizer:
    """
    QoS Odaklı Rotalama için Genetik Algoritma (GA) Sınıfı.
    Bu sınıf, bir kaynak (src) ve hedef (dst) arasındaki en iyi yolu bulmak için evrimsel bir süreç işletir.
    """
    def __init__(self, manager, src, dst, bw_demand):
        # --- Temel Ayarlar ---
        self.manager = manager      # Ağ topolojisini ve maliyet hesaplamalarını yapan yönetici
        self.src = src              # Başlangıç düğümü (Kaynak)
        self.dst = dst              # Bitiş düğümü (Hedef)
        self.bw_demand = bw_demand  # Talep edilen bant genişliği (Constraint)
        
        # --- GA Hiper-Parametreleri ---
        self.pop_size = 40          # Popülasyon Büyüklüğü: Her nesilde kaç farklı yol (birey) yaşayacak?
        self.max_generations = 50   # Maksimum Nesil Sayısı: Algoritma kaç döngü çalışacak?
        self.mutation_rate = 0.30   # Mutasyon Oranı: Bir bireyin genlerinin değişme olasılığı (%30)
        self.crossover_rate = 0.70  # Çaprazlama Oranı: İki bireyin çiftleşme olasılığı (%70)
        self.elitism_count = 2      # Elitizm: En iyi 2 birey bozulmadan bir sonraki nesle aktarılır.
        self.tournament_size = 3    # Turnuva Seçimi: Ebeveyn seçilirken kaç aday rastgele karşılaştırılacak?
        self.max_hop_limit = 20     # Yol Uzunluğu Sınırı: Bir yol en fazla 20 düğümden oluşabilir.
        self.stagnation_limit = 12  # Erken Durdurma: Eğer 12 nesil boyunca iyileşme olmazsa dur.

        # --- GÜVENLİ OPTİMİZASYON (Akıllı Başlangıç) ---
        # 250 düğümlük büyük bir ağda tamamen rastgele gezinmek zordur.
        # Bu yüzden, her düğümün hedefe olan kuş uçuşu (hop) mesafesini önceden hesaplıyoruz.
        # Bu 'dist_map', algoritmanın körlemesine değil, hedefe doğru yönelmesini sağlar (Heuristic Bias).
        self.dist_map = {}
        try:
            # NetworkX ile tüm düğümlerden hedefe olan en kısa mesafeyi hesapla
            self.dist_map = dict(nx.single_source_shortest_path_length(self.manager.G, self.dst))
        except:
            self.dist_map = {} # Eğer graf parçalıysa veya hata olursa boş bırak

    def _generate_random_path(self, max_attempts=50):
        """
        Rastgele (ama akıllı) bir başlangıç yolu (Birey/Kromozom) üretir.
        Random Walk algoritmasını kullanır ancak hedefe yönelimli (Biased) seçim yapar.
        """
        for _ in range(max_attempts): # Başarılı bir yol bulana kadar 50 kere dene
            path = [self.src]         # Yola kaynaktan başla
            curr = self.src           # Şu anki konum
            visited = {self.src}      # Ziyaret edilenler (Döngüye girmemek için)

            while curr != self.dst:   # Hedefe varana kadar ilerle
                try:
                    # Mevcut düğümün komşularını al
                    neighbors = list(self.manager.G.neighbors(curr))
                except:
                    break # Çıkmaz sokak
                
                # Ziyaret edilmemiş komşuları filtrele (Cycle Prevention)
                candidates = [n for n in neighbors if n not in visited]

                if not candidates: break # Gidecek yer yoksa döngüyü kır

                # --- AKILLI SEÇİM (HEURISTIC) ---
                # %70 ihtimalle hedefe fiziksel olarak daha yakın olan komşuyu seç
                if self.dist_map and random.random() < 0.7:
                    # Adayları hedefe olan mesafelerine göre sırala (Küçükten büyüğe)
                    candidates.sort(key=lambda n: self.dist_map.get(n, float('inf')))
                    
                    # En iyi adayı veya (çeşitlilik için) ikinci en iyi adayı seç
                    if len(candidates) >= 2:
                        next_node = candidates[0] if random.random() < 0.8 else candidates[1]
                    else:
                        next_node = candidates[0]
                else:
                    # %30 ihtimalle tamamen rastgele bir komşu seç (Keşif/Exploration)
                    next_node = random.choice(candidates)

                # Yolu güncelle
                path.append(next_node)
                visited.add(next_node)
                curr = next_node

                # Eğer yol çok uzadıysa (limit aşıldıysa) iptal et
                if len(path) > self.max_hop_limit: break

            # Döngü bittiğinde hedefe ulaştıysak yolu döndür
            if curr == self.dst: return path
        
        return None # Hiç yol bulunamazsa None dön

    def _calculate_fitness(self, path, weights):
        """
        Bir bireyin (yolun) kalitesini ölçer.
        Düşük Maliyet = Yüksek Fitness (Uygunluk) demektir.
        """
        # NetworkManager'dan normalize edilmiş maliyeti al
        total_cost, metrics = self.manager.calculate_path_cost(path, weights, self.bw_demand)
        
        penalty = 0
        path_min_bw = metrics.get('min_bw', 0)
        
        # --- CEZA MEKANİZMASI (Soft Constraint) ---
        # Eğer yolun bant genişliği yetersizse, çok büyük ceza puanı ekle.
        # Bu, algoritmanın bu yolları elemesini sağlar.
        if path_min_bw < self.bw_demand:
            penalty += (self.bw_demand - path_min_bw) * 2000
        
        # Yol çok uzunsa da ceza ver
        if len(path) > self.max_hop_limit:
            penalty += (len(path) - self.max_hop_limit) * 1000

        # Hafif bir gürültü (noise) ekleyerek eşit maliyetli yollar arasında
        # rastgele bir sıralama farkı yarat (Çeşitliliği korumak için).
        noise = random.uniform(0.0, 0.99)
        
        return total_cost + penalty + noise, metrics

    def _crossover(self, parent1, parent2):
        """
        Çaprazlama Operatörü: İki ebeveyn yoldan yeni bir çocuk üretir.
        Tek Noktalı Çaprazlama (Single-Point Crossover) mantığı kullanılır.
        """
        # Belirli bir olasılıkla (%70) çaprazlama yap, yoksa ebeveyni kopyala
        if random.random() > self.crossover_rate: return parent1[:]
        
        # Ortak düğümleri (Kesişim noktalarını) bul
        p1_mids = parent1[1:-1] # Başlangıç ve bitiş hariç ara düğümler
        p2_mids = set(parent2[1:-1])
        common = [n for n in p1_mids if n in p2_mids]
        
        # Ortak nokta yoksa birleştirme yapılamaz
        if not common: return parent1[:]
        
        # Rastgele bir ortak nokta (pivot) seç
        pivot = random.choice(common)
        try:
            idx1 = parent1.index(pivot)
            idx2 = parent2.index(pivot)
            
            # 1. Ebeveynin başı + 2. Ebeveynin sonu = Çocuk
            child = parent1[:idx1+1] + parent2[idx2+1:]
            
            # Geçerlilik Kontrolü: Çocukta döngü (cycle) var mı?
            # Bir düğüm iki kere geçiyorsa geçersizdir.
            if len(child) != len(set(child)):
                return parent1[:] # Geçersizse ebeveyni döndür
            return child
        except:
            return parent1[:]

    def _mutate(self, path):
        """
        Mutasyon Operatörü: Bir yolu rastgele değiştirerek çeşitlilik sağlar.
        Yerel minimuma (Local Optima) takılmayı önler.
        """
        # Belirli bir olasılıkla (%30) mutasyon yap
        if random.random() > self.mutation_rate or len(path) < 3:
            return path
            
        new_path = path[:]
        try:
            # Yolun ortasından rastgele bir düğüm seç (idx)
            idx = random.randint(1, len(new_path) - 2)
            prev_node = new_path[idx-1]
            next_node = new_path[idx+1]
            
            # Önceki düğümden Sonraki düğüme giden ALTERNATİF bir yol var mı?
            # Yani: A -> B -> C yerine A -> X -> C yapabilir miyiz?
            candidates = [n for n in self.manager.G[prev_node] 
                          if n != new_path[idx] and n not in new_path and self.manager.G.has_edge(n, next_node)]
            
            # Eğer alternatif varsa değiştir
            if candidates:
                new_path[idx] = random.choice(candidates)
        except:
            pass
            
        return new_path

    def solve(self, weights):
        """
        Genetik Algoritma Ana Döngüsü.
        """
        population = []
        attempts = 0
        
        # 1. ADIM: Başlangıç Popülasyonunu Oluştur
        # Belirlenen popülasyon büyüklüğüne (40) ulaşana kadar rastgele yollar üret
        while len(population) < self.pop_size and attempts < self.pop_size * 20:
            p = self._generate_random_path()
            if p: 
                # Aynı yolu tekrar ekleme (Unique Population)
                if not any(p == existing for existing in population):
                    population.append(p)
            attempts += 1
            
        # Eğer hiç yol bulunamazsa boş dön
        if not population: return [], 0.0, {}

        global_best_path = None
        global_best_fitness = float('inf')
        global_best_metrics = {}
        stagnation_counter = 0 # İyileşme olmayan nesil sayacı

        # 2. ADIM: Nesiller Boyunca Evrim (Main Loop)
        for generation in range(self.max_generations):
            pop_data = []
            
            # Her bireyin uygunluğunu (fitness) hesapla
            for ind in population:
                fit, met = self._calculate_fitness(ind, weights)
                pop_data.append({'path': ind, 'fitness': fit, 'metrics': met})
            
            # Bireyleri maliyetlerine göre sırala (En iyi en üstte)
            pop_data.sort(key=lambda x: x['fitness'])
            current_best = pop_data[0]
            
            # Global en iyiyi güncelle
            if current_best['fitness'] < global_best_fitness:
                global_best_fitness = current_best['fitness']
                global_best_path = current_best['path']
                global_best_metrics = current_best['metrics']
                stagnation_counter = 0 # İyileşme oldu, sayacı sıfırla
            else:
                stagnation_counter += 1 # İyileşme yok

            # Erken Durdurma: Uzun süre gelişme olmazsa döngüyü bitir
            if stagnation_counter >= self.stagnation_limit:
                break
            
            # --- YENİ NESİL OLUŞTURMA ---
            
            # A. Elitizm: En iyi 2 bireyi doğrudan yeni nesle taşı
            new_population = [d['path'] for d in pop_data[:self.elitism_count]]
            
            # B. Yeni Bireyler Üret (Çaprazlama ve Mutasyon)
            while len(new_population) < self.pop_size:
                
                # EĞER YETERLİ POPÜLASYON YOKSA (Kritik Kontrol)
                if len(pop_data) < 2:
                    # Yeterli ebeveyn yoksa rastgele yeni yol üretip ekle
                    p = self._generate_random_path()
                    if p: new_population.append(p)
                    else: 
                        # Rastgele de bulamazsan eldekini mutasyona uğrat
                        new_population.append(self._mutate(pop_data[0]['path']))
                    continue

                # Turnuva Seçimi: Rastgele 5 birey al, en iyilerini seç
                sample_size = min(len(pop_data), 5)
                if sample_size < 2: sample_size = 2
                
                try:
                    # Rastgele adaylar seç
                    parents = random.sample(pop_data, sample_size)
                    # Adayları kendi içinde yarıştır (en düşük maliyetli kazanır)
                    parents.sort(key=lambda x: x['fitness'])
                    
                    # En iyi iki ebeveyni çiftleştir
                    child = self._crossover(parents[0]['path'], parents[1]['path'])
                    # Çocuğu mutasyona uğrat
                    child = self._mutate(child)
                    
                    # Yeni nüfusa ekle
                    new_population.append(child)
                except ValueError:
                    # Hata durumunda (örneğin liste boşsa) yedek plan
                    new_population.append(self._mutate(pop_data[0]['path']))
            
            # Popülasyonu güncelle
            population = new_population

        # En iyi sonucu döndür
        return global_best_path, global_best_fitness, global_best_metrics