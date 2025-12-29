## 🔥 3. Benzetimli Tavlama (Simulated Annealing - SA)

### 📌 Nedir?
Adını metalurjiden (metal işleme sanatı) alır. Bir demirci, metali önce çok yüksek sıcaklığa kadar ısıtır (moleküller serbestleşir), sonra yavaş yavaş soğutarak (moleküller kristalleşir) en sağlam şekli almasını sağlar.

Bilgisayar biliminde bu; başlangıçta "kötü kararlar almaya" izin verip, zamanla sadece "iyi kararları" kabul ederek en iyi sonucu (Global Optimum) bulma yöntemidir.

### 🚀 Bu Projede Neden ve Nasıl Kullandık?
Diğer algoritmalar bazen buldukları "ilk iyi yola" yapışıp kalırlar (Yerel Optimum Tuzağı). Halbuki belki biraz daha ileride çok daha iyi bir yol vardır. SA, başlangıçta "kötü yollara" sapmaya izin vererek, algoritmanın tüm haritayı keşfetmesini ve tuzağa düşmemesini sağlar.

### 🧠 Temel Terimler ve Projedeki Karşılıkları

| Terim | Projedeki (QoS Routing) Karşılığı | Açıklama |
| :--- | :--- | :--- |
| **Sıcaklık (Temperature)** | Hata Yapma Toleransı | Algoritma başındayken yüksektir (risk alır), sonlara doğru düşer (garantici olur). |
| **Enerji** | Rota Maliyeti (Cost) | Hedefimiz enerjiyi (gecikme, kayıp vb.) minimuma indirmektir. |
| **Soğutma** | İterasyon İlerlemesi | Adım adım risk alma ihtimalinin düşürülmesi. |

---

### ⚙️ Çalışma Mantığı

1.  **Yüksek Sıcaklık (Başlangıç):** Rastgele bir rota seçilir. Komşu bir rota ile kıyaslanır. Yeni rota daha kötüyse bile, yüksek sıcaklık nedeniyle **kabul edilme ihtimali** vardır.
    * *Neden?* Belki bu kötü yol, ileride mükemmel bir yola bağlanıyordur.
2.  **Soğutma Süreci:** Algoritma ilerledikçe "Sıcaklık" düşürülür.
3.  **Düşük Sıcaklık (Bitiş):** Artık sistem soğumuştur. Algoritma sadece daha iyi sonuçları kabul eder, kötü sonuçları reddeder.
4.  **Sonuç:** Metalin kristalleşmesi gibi, rota da en stabil ve en düşük maliyetli (en kaliteli) hale gelir.



### 📊 Özet
* **✅ Avantajı:** "Yerel Optimum" (Local Optima) denilen, yalancı en iyi çözümlere takılıp kalmaz. Büyük resimdeki en iyi sonucu bulma şansı yüksektir.
* **❌ Dezavantajı:** Doğru soğutma planı (parametre ayarı) yapılmazsa çalışması çok uzun sürebilir veya rastgele sonuçlar verebilir.