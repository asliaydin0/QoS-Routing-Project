#  Yapay Arı Kolonisi (Artificial Bee Colony - ABC) Algoritması ile QoS Rotalama

Bu doküman, **BSM307 Güz 2025 Dönem Projesi** kapsamında, 250 düğümlük karmaşık ağ topolojilerinde Çok Amaçlı Rotalama (Multi-Objective Routing) problemini çözmek için geliştirilen ABC algoritmasının detaylarını içermektedir[cite: 1, 13].

---

## 1. Teorik Altyapı ve Algoritma Mantığı

Yapay Arı Kolonisi (ABC) algoritması, doğadaki arıların verimli besin kaynağı arama davranışını simüle eden bir sürü zekası optimizasyon yöntemidir[cite: 89, 90]. Proje kapsamında, her bir "besin kaynağı" ağ üzerindeki bir Kaynak (S) ve Hedef (D) rotasını temsil eder[cite: 7].



###  Koloni Yapısı ve Görev Dağılımı:
* **Görevli Arılar (Employed Bees):** Mevcut rotaları korur ve yerel aramalarla (mutasyon/komşuluk değişimi) daha iyi bir yol olup olmadığını araştırırlar[cite: 81, 82].
* **Gözcü Arılar (Onlooker Bees):** Görevli arıların paylaştığı "fitness" (uygunluk) bilgilerini analiz ederek, kaliteli (düşük maliyetli) rotaların çevresinde aramayı derinleştirirler[cite: 90].
* **Kaşif Arılar (Scout Bees):** Belirli bir süre (limit) boyunca geliştirilemeyen rotaları terk eder ve yeni, rastgele rotalar keşfederek algoritmanın yerel optimuma takılmasını önlerler[cite: 90].

---

## 2. Optimizasyon Metrikleri ve Uygunluk (Fitness) Fonksiyonu

ABC algoritması, aşağıdaki üç metriği **Ağırlıklı Toplam Yöntemi (Weighted Sum Method)** ile eş zamanlı olarak optimize eder[cite: 65]:

###  A. Toplam Gecikme (Delay) - Minimizasyon
Tüm bağlantı gecikmeleri ve ara düğüm işlem sürelerinin toplamıdır[cite: 39, 41, 42].


$$Total Delay(P) = \sum_{(i,j) \in P} LinkDelay_{ij} + \sum_{k \in P \setminus \{S,D\}} ProcessingDelay_k$$


###  B. Toplam Güvenilirlik (Reliability) - Maksimizasyon
Güvenilirliği maksimize etmek için, toplamsal hesaplamaya uygun **Güvenilirlik Maliyeti** minimize edilir[cite: 47, 51]:


$$ReliabilityCost(P) = \sum_{(i,j) \in P} [-\log(LinkReliability_{ij})] + \sum_{k \in P} [-\log(NodeReliability_k)]$$ [cite: 52]


###  C. Ağ Kaynak Kullanımı (Resource Usage) - Minimizasyon
Düşük bant genişliğine sahip yollara yüksek maliyet atanarak yüksek kapasiteli bağlantılar teşvik edilir[cite: 55, 56]:


$$ResourceCost(P) = \sum_{(i,j) \in P} \left(\frac{1 \text{ Gbps}}{Bandwidth_{ij}}\right)$$ [cite: 57]


###  Çok Amaçlı Fitness Fonksiyonu
$$TotalCost(P) = W_{delay} \cdot Delay(P) + W_{reliability} \cdot RelCost(P) + W_{resource} \cdot ResCost(P)$$ [cite: 66, 67, 68]


*(Burada $W_{delay} + W_{reliability} + W_{resource} = 1$ şartı sağlanır[cite: 69].)*


---

## 3. Uygulama Detayları ve Yazılım Mimarisi

ABC algoritması `ABC_Optimizer` sınıfı altında modüler bir yapıda kurgulanmıştır:

* **`find_initial_paths()`:** 250 düğümlük ağ üzerinde geçerli başlangıç rotaları üretir[cite: 22, 24].
* **`evaluate_fitness()`:** Belirlenen ağırlıklara göre yolun toplam maliyetini hesaplar[cite: 66].
* **`neighborhood_search()`:** Rota üzerindeki düğümleri mutasyona uğratarak alternatif yollar türetir[cite: 82].
* **`roulette_wheel_selection()`:** Gözcü arıların kaliteli yollara yönelmesini sağlar[cite: 90].

---

## 4. Kullanıcı Arayüzü (GUI) Entegrasyonu

Projenin görsel uygulama gereksinimlerini karşılamak adına ABC algoritması arayüz ile dinamik olarak bağlanmıştır[cite: 71, 72]:

* **Parametre Yönetimi:** Kullanıcı, GUI üzerinden S-D düğümlerini seçer ve ağırlık ($W$) değerlerini slider/giriş alanları vasıtasıyla anlık olarak belirler[cite: 73, 74].
* **Anlık Görselleştirme:** "Hesapla" butonuna basıldığında ABC algoritması çalışır ve bulduğu en iyi yolu grafik üzerinde renkli olarak gösterir[cite: 75].
* **Veri Raporlama:** Bulunan yolun metrikleri (Toplam Gecikme, Toplam Güvenilirlik, Kaynak Maliyeti) GUI üzerindeki sonuç panelinde sunulur[cite: 76].

---

## 5. Kullanılan Teknolojiler

* **Python:** Temel algoritma mantığının kodlanması.
* **NetworkX:** Erdős-Rényi ($G(n,p)$) modeline göre 250 düğümlü bağlı graf yapısının oluşturulması[cite: 25, 26].
* **NumPy:** Logaritmik maliyet dönüşümleri ve karmaşık metrik hesaplamaları[cite: 52].
* **Matplotlib:** Ağ topolojisinin ve optimize edilen rotaların görselleştirilmesi[cite: 72].

---
