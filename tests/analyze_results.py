import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# 1. Veriyi Yükle (Load Data)
file_path = "Final_Project_Benchmark_Results.csv"

if not os.path.exists(file_path):
    print(f"Hata: '{file_path}' dosyası bulunamadı. Lütfen benchmark kodunu çalıştırın.")
    exit()

df = pd.read_csv(file_path, sep=';')

# Stil ayarları (Görsellik için)
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 12})

# Çıktı klasörü oluştur
output_dir = "analysis_plots"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def save_plot(filename):
    path = os.path.join(output_dir, filename)
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    print(f"Grafik kaydedildi: {path}")
    plt.close()

# --- GRAFİK 1: Ortalama Maliyet Karşılaştırması (Mean Cost Comparison) ---
# DÜZELTME: Logaritmik ölçek (Log Scale) kullanıldı çünkü GeneticAlgo değerleri çok yüksek.
plt.figure(figsize=(12, 6))
sns.barplot(data=df, x="Weight_Profile", y="Mean_Cost", hue="Algorithm", palette="viridis")
plt.title("Ağırlık Senaryolarına Göre Ortalama Maliyet (Mean Cost)", fontsize=16)
plt.ylabel("Ortalama Maliyet (Log Scale)") # Etiketi güncelledik
plt.yscale('log') # <-- Logaritmik ölçek eklendi
plt.xlabel("Senaryo")
plt.legend(title="Algoritma")
save_plot("comparison_mean_cost.png")

# --- GRAFİK 2: Çalışma Süresi Karşılaştırması (Execution Time Comparison) ---
plt.figure(figsize=(12, 6))
sns.barplot(data=df, x="Weight_Profile", y="Avg_Time", hue="Algorithm", palette="rocket")
plt.title("Algoritmaların Çalışma Süresi Karşılaştırması (Saniye)", fontsize=16)
plt.ylabel("Ortalama Süre (sn)")
plt.xlabel("Senaryo")
plt.legend(title="Algoritma")
save_plot("comparison_execution_time.png")

# --- GRAFİK 3: Başarı Oranı (Success Rate) ---
plt.figure(figsize=(10, 6))
success_df = df.groupby(['Algorithm', 'Weight_Profile'])['Success_Rate'].mean().reset_index()
sns.barplot(data=success_df, x="Algorithm", y="Success_Rate", hue="Weight_Profile", palette="Blues_d")
plt.title("Algoritmaların Başarı Oranları (%)", fontsize=16)
plt.ylabel("Başarı Oranı (%)")
plt.ylim(0, 110) 
save_plot("comparison_success_rate.png")

# --- GRAFİK 4: Gecikme vs Maliyet (Scatter Plot) ---
valid_df = df[df['Mean_Cost'] < float('inf')]
plt.figure(figsize=(12, 7))
sns.scatterplot(data=valid_df, x="Mean_Delay", y="Mean_Cost", hue="Algorithm", style="Weight_Profile", s=100)
plt.title("Maliyet ve Gecikme İlişkisi (Cost vs Delay)", fontsize=16)
plt.xlabel("Ortalama Gecikme (Mean Delay)")
plt.ylabel("Ortalama Maliyet (Mean Cost)")
# İstersen buraya da log scale ekleyebilirsin ama scatter plot'ta genelde orjinal halini görmek daha iyidir.
save_plot("scatter_cost_vs_delay.png")

# --- GRAFİK 5: Ortalama Güvenilirlik Karşılaştırması (Mean Reliability Comparison) ---
plt.figure(figsize=(12, 6))
sns.barplot(data=df, x="Weight_Profile", y="Mean_Reliability", hue="Algorithm", palette="magma")
plt.title("Ağırlık Senaryolarına Göre Ortalama Güvenilirlik", fontsize=16)
plt.ylabel("Ortalama Güvenilirlik")
plt.xlabel("Senaryo")
plt.legend(title="Algoritma")
save_plot("comparison_reliability.png")

# --- GRAFİK 6: Ortalama Kaynak Maliyeti Karşılaştırması (Mean Resource Cost Comparison) ---
plt.figure(figsize=(12, 6))
sns.barplot(data=df, x="Weight_Profile", y="Mean_Resource_Cost", hue="Algorithm", palette="coolwarm")
plt.title("Ağırlık Senaryolarına Göre Ortalama Kaynak Maliyeti", fontsize=16)
plt.ylabel("Ortalama Kaynak Maliyeti")
plt.xlabel("Senaryo")
plt.legend(title="Algoritma")
save_plot("comparison_resource_cost.png")

print("\n--- Analiz Tamamlandı ---")
print(f"Tüm grafikler '{output_dir}' klasörüne kaydedildi.")