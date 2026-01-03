# QoS Multiobjective Routing Project

Bu proje, Bilgisayar Ağları dersi kapsamında geliştirilen ve 250 düğümlü rastgele bir ağ üzerinde **en uygun rotayı** bulmayı amaçlayan bir çalışmadır. Projede, gecikme (delay), güvenilirlik (reliability) ve kaynak kullanımı (bandwidth cost) gibi QoS odaklı metrikler dikkate alınarak çok amaçlı bir optimizasyon yapılacaktır.


---

## 🎯 Amaç

- Rastgele bir ağ topolojisi oluşturmak    
- Ağ üzerindeki S → D arasındaki yolları değerlendirmek    
- QoS metriklerine göre en uygun yolu seçmek    
- Farklı algoritmaların performanslarını karşılaştırmak    
- Basit bir arayüz ile kullanıcının sonuçları görmesini sağlamak    

---

## 🧩 Projede Kullanılacak Temel Metrikler
Algoritmalar aşağıdaki QoS metriklerine göre değerlendirilmiştir:

- Total Delay (Toplam Gecikme)  
- Reliability (Güvenilirlik)  
- Resource Cost (Kaynak Maliyeti)  
- Total Cost (Ağırlıklı Amaç Fonksiyonu)  

## 🧠 Kullanılan Algoritmalar

Projede aşağıdaki algoritmalar uygulanmış ve karşılaştırılmıştır(Her algoritma aynı ağ senaryoları ve metrikler altında çalıştırılmıştır:

-Genetik Algoritma (GA)  
-Q-Learning  
-Yapay Arı Kolonisi (ABC)  
-Benzetimli Tavlama (Simulated Annealing – SA)  


## 🖥️ Arayüz (GUI)

=> PyQt5 tabanlı masaüstü arayüz   
=>NetworkX ve Matplotlib ile ağ görselleştirme  

Özellikler:

-Algoritma seçimi  
-Kaynak–hedef (S–D) seçimi  
-Çoklu algoritma kıyaslama  
-Grafiksel performans analizi  
-En iyi algoritmanın otomatik önerilmesi  


## ⚙️ Kullanılan Teknolojiler ve Kütüphaneler

-Python 3  
-PyQt5  
-NetworkX  
-Matplotlib  
-NumPy  
-Pandas  


## ▶️ Çalıştırma

pip install -r requirements.txt   
python GUI.py  

## 🧪 Test ve Analiz  

=> Algoritmalar çoklu çalıştırmalar ile test edilmiştir  
=>Tutarlılık ve kararlılık analizi yapılmıştır  

Performans karşılaştırmaları:  

-Maliyet  
-Hesaplama süresi  
-Gecikme  
-Güvenilirlik  

=>Sonuçlar CSV dosyaları ve grafikler ile raporlanmıştır  


---

## 🛠️ Planlanan Özellikler 

- [+] 250 düğümlü rastgele ağ oluşturma  
- [+] Düğüm ve bağlantı özelliklerinin atanması  
- [+] Gecikme, güvenilirlik ve kaynak maliyet fonksiyonlarının yazılması  
- [+] En az iki optimizasyon algoritmasının eklenmesi  
- [+] Basit bir arayüz ile grafiğin görüntülenmesi  
- [+] Algoritma sonuçlarının karşılaştırılması  
- [+] Rapor ve deney sonuçlarının eklenmesi  

---

## 👥 Proje Ekibi

Aslı AYDIN  
Senanur ŞAHİN  
Eylül EJDEROĞLU  
Mert Can AYDIN  
İbrahim USLU  
Hakan YAVUZ  
Husam ABDULRAHEEM    
Khofif Rohma Cahyani  
Mutia Apriani    


---


