## 🔧 Projeye Katkı (Adım Adım Rehber)

Aşağıdaki adımlar, projeye kod eklemek/algoritma geliştirmek veya var olan kodu güncellemek isteyen ekip üyeleri için adım adım yönergedir. Her adımı takip edin — böylece çakışmalar ve karışıklıklar en aza iner.

> **Ön koşul:** Bilgisayarında Git yüklü olsun. (https://git-scm.com/downloads)

---

### 1️⃣ Reponun bilgisayara indirilmesi
```bash
git clone <https://github.com/asliaydin0/QoS-Routing-Project>
cd <QoS-Routing-Project>
```
### 2️⃣ Ana branch'i güncelleme (her çalışmaya başlamadan önce)
```bash
git checkout main
git pull origin main
```
### 3️⃣ Kendine özel branch oluşturma
Her kişi kendi görevi için ayrı bir branch açmalıdır. ( örn: git checkout -b asli-ga)
```bash
git checkout -b <isim>-<gorev>
```
### 4️⃣ Kod yazma / düzenleme
Değişiklik yaptıktan sonra:
```bash
git add .
git commit -m "kısa açıklama: aco temel yapısı eklendi"
```
### 5️⃣ Branch'i GitHub'a gönderme
```bash
git push origin <isim>-<gorev>
```


