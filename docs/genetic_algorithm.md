## 🧬 1. Genetik Algoritma (Genetic Algorithm - GA)

### 📌 Nedir? (Basit Tanım)
Genetik Algoritma, doğadaki **evrim sürecini** ve Charles Darwin'in **"Doğal Seçilim"** (güçlü olanın hayatta kalması) ilkesini taklit eden bir arama ve optimizasyon yöntemidir.

Karmaşık bir problemi çözmek için bilgisayar, tek bir çözüm üretmek yerine binlerce rastgele çözüm üretir. Bu çözümleri yarıştırır, iyi olanları seçer, birbirleriyle eşleştirir (çaprazlar) ve mutasyona uğratarak nesiller boyu daha mükemmel sonuca ulaşmaya çalışır.

### 🚀 Bu Projede Neden ve Nasıl Kullandık?
QoS (Hizmet Kalitesi) Yönlendirme probleminde, A noktasından B noktasına giden **milyarlarca farklı yol** olabilir. Tüm yolları tek tek hesaplamak (brute-force) işlemciyi kilitler. GA, tüm yolları denemek yerine "en iyi olma potansiyeli olan" yolları evrimleştirerek çok kısa sürede optimuma yakın bir rota bulmamızı sağlar.

### 🧠 Temel Terimler ve Projedeki Karşılıkları

Algoritmayı anlamak için biyolojik terimlerin projemizdeki (Routing) karşılığını bilmek gerekir:

| Biyolojik Terim | Projedeki (QoS Routing) Karşılığı | Açıklama |
| :--- | :--- | :--- |
| **Gen** | Düğüm (Node/Router) | Rotayı oluşturan her bir durak noktası. |
| **Kromozom (Birey)** | Rota (Path) | Kaynaktan hedefe giden tam bir yol (Örn: [A -> C -> D -> F]). |
| **Popülasyon** | Rotalar Grubu | Elimizdeki tüm alternatif yolların listesi. |
| **Fitness (Uygunluk)** | QoS Skoru | O rotanın kalitesi (Gecikme süresi, bant genişliği vb. ile hesaplanan puan). |
| **Jenerasyon** | Döngü (İterasyon) | Algoritmanın her bir çalışma turu. |

---

### ⚙️ Çalışma Mantığı (Adım Adım)

Kodun arka planında süreç şu 5 adımda işler:

#### 1. Başlangıç Popülasyonu (Initialization)
Algoritma başlarken, kaynaktan hedefe giden **tamamen rastgele** rotalar oluşturur. Bu ilk rotalar muhtemelen çok kötüdür (çok uzun veya yavaştır), ama bu bir başlangıçtır.

#### 2. Uygunluk Hesaplama (Fitness Calculation)
Her bir rotanın (kromozomun) başarısı ölçülür. Bizim projemizde başarı kriteri şunlardır:
* *Düşük Gecikme (Low Latency)*
* *Yüksek Bant Genişliği (High Bandwidth)*
* *Düşük Paket Kaybı*
**Sonuç:** Her rotaya bir puan verilir. Puanı yüksek olan "kaliteli", düşük olan "zayıf" rotadır.

#### 3. Seçilim (Selection)
Doğal seçilim devreye girer. Puanı yüksek olan rotalar, bir sonraki nesle aktarılmak üzere "anne ve baba" olarak seçilir. Puanı çok düşük olan rotalar elenir (soyları tükenir).

#### 4. Çaprazlama (Crossover) - *En Kritik Adım*
Seçilen iki iyi rota (Anne ve Baba) alınır ve genleri karıştırılarak yeni bir rota (Çocuk) oluşturulur.
* **Örnek:**
    * **Rota A (Baba):** [1 -> 3 -> **5 -> 8** -> 10]
    * **Rota B (Anne):** [1 -> 2 -> **5 -> 9** -> 10]
    * *Ortak nokta olan 5. düğümden kesilip birleştirilir:*
    * **Yeni Rota (Çocuk):** [1 -> 3 -> **5 -> 9** -> 10]
* *Amaç:* İki iyi yolun özelliklerini birleştirerek daha iyi bir yol bulmaktır.

#### 5. Mutasyon (Mutation)
Yeni oluşan rotada çeşitliliği sağlamak ve algoritmanın kör bir noktaya sıkışmasını engellemek için rota üzerinde rastgele küçük bir değişiklik yapılır.
* **Örnek:** Rotadaki "4. Düğüm" rastgele çıkarılıp yerine "7. Düğüm" konulur. Bu bazen yolu bozar, ama bazen de kimsenin aklına gelmeyen harika bir kısayol keşfedilmesini sağlar.

---

### 📊 Özet: Avantaj ve Dezavantajlar

* **✅ Avantajı:** Çok büyük ve karmaşık ağlarda (Topology) kesin sonucu aramak yerine, çok hızlı bir şekilde "yeterince iyi" sonucu bulur. Yerel tuzaklara (Local Optima) takılma ihtimali düşüktür.
* **❌ Dezavantajı:** Çalışması rastgeleliğe dayalı olduğu için, aynı problemde her çalıştırışta milimetrik olarak farklı sonuçlar verebilir. En mükemmel sonucu (Global Optimum) bulmayı %100 garanti etmez.