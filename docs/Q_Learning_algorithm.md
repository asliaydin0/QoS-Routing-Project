## 🤖 2. Q-Learning (Pekiştirmeli Öğrenme)

### 📌 Nedir?
Q-Learning, makine öğrenmesinin "Pekiştirmeli Öğrenme" (Reinforcement Learning) alt dalına ait bir algoritmadır. Bir öğretmenin öğrenciye doğru yaptığı şeyler için ödül, yanlış yaptığı şeyler için ceza vermesi mantığına dayanır.

Ortamda dolaşan bir **"Ajan" (Agent)** vardır. Bu ajan deneme-yanılma yoluyla hangi hareketlerin ona en çok puanı (ödülü) kazandırdığını öğrenir ve bu tecrübelerini bir hafıza tablosuna (**Q-Table**) kaydeder.

### 🚀 Bu Projede Neden ve Nasıl Kullandık?
QoS Routing dinamik bir süreçtir. Ağ trafiği anlık değişebilir. Q-Learning, ağın içinde sürekli gezinen paketler (ajanlar) sayesinde hangi yolun tıkalı, hangi yolun hızlı olduğunu zamanla öğrenir.



### 🧠 Temel Terimler ve Projedeki Karşılıkları

| Terim | Projedeki (QoS Routing) Karşılığı | Açıklama |
| :--- | :--- | :--- |
| **Agent (Ajan)** | Veri Paketi / Yönlendirici Yazılımı | Ağ üzerinde yolunu bulmaya çalışan akıllı birim. |
| **State (Durum)** | Mevcut Router (Düğüm) | Ajanın o an bulunduğu konum (Örn: Router A). |
| **Action (Eylem)** | Bir sonraki Router'a geçiş | Komşu düğümlerden hangisine gidileceği kararı. |
| **Reward (Ödül)** | Bağlantı Kalitesi | Gidilen yol hızlıysa (+), yavaş veya kopuksa (-) puan verilir. |
| **Q-Table** | Yönlendirme Tablosu (Routing Table) | Hangi düğümden nereye gidilirse ne kadar ödül alınacağının tutulduğu hafıza matrisi. |

---

### ⚙️ Çalışma Mantığı

1.  **Keşif (Exploration):** Ajan başta çevreyi bilmediği için rastgele yollara girer.
2.  **Eylem ve Sonuç:** Ajan bir düğümden diğerine geçer (Örn: A -> B).
3.  **Ödül/Ceza:**
    * Eğer B düğümüne giden hat boş ve hızlıysa (Düşük Gecikme), Ajan **pozitif ödül** alır.
    * Eğer hat tıkalıysa, Ajan **negatif ödül (ceza)** alır.
4.  **Q-Tablosunu Güncelleme:** Ajan, "A'dan B'ye gitmek iyi bir fikir" veya "kötü bir fikir" bilgisini matematiksel olarak Q-Tablosuna yazar.
5.  **Sömürü (Exploitation):** İlerleyen turlarda Ajan artık rastgele gitmez, Q-Tablosuna bakıp en yüksek puanlı yolu seçer.


---

### 🧠 ALGORİTMA MİMARİSİ: Q-LEARNING


Algoritma, **Epsilon-Greedy** politikası ile çalışır. Bu sayede ajan:
1.  **Keşif (Exploration):** Bilmediği yeni yolları dener.
2.  **Sömürü (Exploitation):** Daha önce öğrendiği en iyi yolları kullanır.

### ⚙️ HİPER-PARAMETRELER
| PARAMETRE | DEĞER | AÇIKLAMA |
| :--- | :--- | :--- |
| **Öğrenme Oranı ($\alpha$)** | 0.1 | Yeni bilginin ne kadar baskın olacağını belirler. |
| **İndirim Faktörü ($\gamma$)** | 0.9 | Gelecekteki ödüllerin bugünkü değerini belirler. |
| **Epsilon ($\epsilon$)** | 1.0 | Başlangıçtaki rastgele hareket oranıdır. |
| **Epizot Sayısı** | 800 | Toplam eğitim deneme sayısıdır. |

---

## ⚖️ ÖDÜL VE CEZA SİSTEMİ (REWARD FUNCTION)

Ajanın doğru rotayı bulması için aşağıdaki puanlama mekanizması kurgulanmıştır:

* **HEDEFE ULAŞMA:** $+ (Maliyet \times 2)$ (En yüksek ödül).
* **DÖNGÜ CEZASI:** $-1000$ (Aynı düğüme tekrar girilirse).
* **BANT GENİŞLİĞİ İHLALİ:** $-500$ (Talep karşılanmazsa).
* **ADIM CEZASI:** $-1$ (Yolun gereksiz uzamasını engeller).

--- 

### 📊 Özet
* **✅ Avantajı:** Öğrenebilen bir yapıdır. Ağın durumu değiştikçe (bir hat koptuğunda), ajan ceza alacağı için o yolu kullanmayı bırakıp alternatif yolları kendi kendine öğrenir.
* **❌ Dezavantajı:** Başlangıçta "öğrenme süreci" olduğu için optimum yolu bulması zaman alır. Büyük ağlarda Q-Tablosu (hafıza) çok yer kaplayabilir.