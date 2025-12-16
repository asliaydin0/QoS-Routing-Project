import sys
import time
import math
import random
import itertools
from pathlib import Path

# ==========================================================
# PyQt5 Kütüphaneleri
# ==========================================================
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QCursor

# ==========================================================
# Grafik Kütüphaneleri (Matplotlib + NetworkX)
# ==========================================================
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import networkx as nx

# Yüksek Çözünürlük (HiDPI) Ayarları
if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

# RENK PALETİ / TEMA

THEME = {
    "MAIN_BG": "#111828",       # Ana pencere arka planı
    "CARD_BG": "#1e293b",       # Kart arka planı
    "GRAPH_BG": "#111828",      # Grafik alanı arka planı
    "BORDER": "#3c4654",        # Çerçeve rengi
    "TEXT": "#f1f2f6",          # Yazı rengi
    "BUTTON": "#7b2cff",        # Buton rengi
    "BUTTON_HOVER": "#6300A5",  # Buton hover rengi
    "NODE_COLOR": "#00d0ff",    # Düğüm rengi
    "PATH_COLOR": "#921717"     # Seçilen yol rengi
}

# BACKEND IMPORT (comparison.py)
# DÜZELTME: Yol, proje kök dizinine işaret etmeli (frontend klasörü değil)

PROJE_KOKU = Path(__file__).resolve().parent.parent  # <-- DÜZELTME BURADA
if str(PROJE_KOKU) not in sys.path:
    sys.path.insert(0, str(PROJE_KOKU))

from comparison import run_single  # comparison.py proje kök dizininde olmalı



# Worker Thread:
# Backend'deki run_single() fonksiyonunu GUI'yi kilitlemeden çalıştırır

class RoutingWorker(QThread):
    finished = pyqtSignal(list, float, dict)
    error = pyqtSignal(str)

    def __init__(self, algo_key, G, src, dst, weights):
        super().__init__()
        self.algo_key = algo_key
        self.G = G
        self.src = src
        self.dst = dst
        self.weights = weights

    def run(self):
        try:
            path, cost, metrics = run_single(
                algo_key=self.algo_key,
                G=self.G,
                src=self.src,
                dst=self.dst,
                weights=self.weights
            )
            self.finished.emit(path or [], float(cost), metrics or {})
        except Exception as e:
            self.error.emit(str(e))


# FRONTEND (GUI)
# Matplotlib canvas: NetworkX grafını PyQt içinde çizer

class GraphCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = plt.subplots()
        super().__init__(self.fig)
        self.setParent(parent)

        self.fig.patch.set_facecolor(THEME["GRAPH_BG"])
        self.ax.set_facecolor(THEME["GRAPH_BG"])

        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.updateGeometry()
        self.pos = {}

    def draw_graph(self, G, path=None):
        self.ax.clear()
        self.ax.set_facecolor(THEME["GRAPH_BG"])

        # Yerleşim (layout) üretimi: spring_layout mümkünse, değilse random_layout
        try:
            self.pos = nx.spring_layout(G, seed=42, iterations=30)
        except:
            self.pos = nx.random_layout(G, seed=42)

        # Tüm kenarları çiz
        nx.draw_networkx_edges(
            G, self.pos,
            edge_color="#404855",
            width=0.1,
            alpha=0.5,
            ax=self.ax
        )

        # Tüm düğümleri çiz
        nx.draw_networkx_nodes(
            G, self.pos,
            node_size=30,
            node_color=THEME["NODE_COLOR"],
            ax=self.ax
        )

        # Eğer bir yol verilmişse, yolu vurgula
        if path is not None and len(path) > 1:
            path_edges = list(zip(path[:-1], path[1:]))

            nx.draw_networkx_edges(
                G, self.pos,
                edgelist=path_edges,
                width=2.5,
                edge_color=THEME["PATH_COLOR"],
                alpha=1.0,
                ax=self.ax
            )

            nx.draw_networkx_nodes(
                G, self.pos,
                nodelist=path,
                node_color=THEME["PATH_COLOR"],
                node_size=60,
                ax=self.ax
            )

            # Yoldaki düğümleri etiketle
            labels = {node: str(node) for node in path}
            nx.draw_networkx_labels(
                G, self.pos, labels,
                font_size=8,
                font_color="white",
                font_weight="bold",
                ax=self.ax
            )

        self.ax.set_axis_off()
        self.fig.tight_layout()
        self.draw()


# Kart üretici: Sağ panelde metrikleri göstermek için

def create_card(title, title_color="#ffffff", big=False):
    frame = QtWidgets.QFrame()
    frame.setObjectName("resultCard")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)

    lbl_title = QtWidgets.QLabel(title)
    lbl_title.setStyleSheet(f"font-size: 11px; color: {title_color}; font-weight: 600;")
    layout.addWidget(lbl_title)

    lbl_value = QtWidgets.QLabel("-")
    if big:
        lbl_value.setStyleSheet("font-size: 18px; font-weight: 700;")
    else:
        lbl_value.setStyleSheet("font-size: 15px; font-weight: 600;")
    layout.addWidget(lbl_value)

    layout.addStretch()
    return frame, lbl_value



# Ana Pencere

class Window(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QoS Yönlendirme Simülatörü")
        self.resize(1450, 850)

        self.generate_initial_graph()
        self.build_ui()

        # Son çalıştırmada kullanılan ağırlıkları sakla (log tutarlılığı için)
        self._last_weights = (0.4, 0.3, 0.3)

    # Başlangıçta rastgele bir ağ üretir
    def generate_initial_graph(self):
        print("250 Düğümlü Ağ Oluşturuluyor... Lütfen bekleyin.")
        self.N = 250
        self.G = nx.erdos_renyi_graph(self.N, 0.4, seed=42)

        # Kenar (edge) özellikleri
        for u, v in self.G.edges():
            bw = random.randint(100, 1000)
            self.G[u][v]["bandwidth"] = bw
            self.G[u][v]["capacity"] = bw
            self.G[u][v]["delay"] = random.randint(3, 15)
            self.G[u][v]["reliability"] = round(random.uniform(0.95, 0.999), 4)

        # Düğüm (node) özellikleri
        for n in self.G.nodes():
            self.G.nodes[n]["processing_delay"] = round(random.uniform(0.5, 2.0), 2)
            self.G.nodes[n]["reliability"] = round(random.uniform(0.95, 0.999), 4)

    # Algoritma anahtarı eşlemesi: combobox metninden backend anahtarına çevirir
    def _algo_key(self) -> str:
        t = self.algo_combo.currentText()
        if "(GA)" in t:
            return "GA"
        if "(RL)" in t:
            return "Q"
        if "(ABC)" in t:
            return "ABC"
        return "SA"

    
    # FRONTEND DÜZELTMESİ:
    # Slider ağırlıklarını normalize eder (toplam = 1.0)
    
    def _get_normalized_weights(self):
        w1 = float(self.delay_slider.value())
        w2 = float(self.rel_slider.value())
        w3 = float(self.res_slider.value())
        s = w1 + w2 + w3
        if s <= 1e-12:
            return (1.0, 0.0, 0.0)
        return (w1 / s, w2 / s, w3 / s)

    # Arayüzü oluşturur
    def build_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # ------------------------------------------------------
        # SOL PANEL
        # ------------------------------------------------------
        sidebar = QtWidgets.QVBoxLayout()
        sidebar.setSpacing(15)

        # Algoritma seçimi
        algo_group = QtWidgets.QGroupBox("Algoritma Seçimi")
        algo_layout = QtWidgets.QVBoxLayout()
        self.algo_combo = QtWidgets.QComboBox()

        # 4 algoritma
        self.algo_combo.addItems([
            "Genetik Algoritma (GA)",
            "Q-Öğrenme (RL)",
            "Yapay Arı Kolonisi (ABC)",
            "Benzetimli Tavlama (SA)",
        ])

        self.algo_combo.setMinimumHeight(35)
        algo_layout.addWidget(QtWidgets.QLabel("Yöntem:"))
        algo_layout.addWidget(self.algo_combo)
        algo_group.setLayout(algo_layout)
        sidebar.addWidget(algo_group)

        # Rota ayarları
        route_group = QtWidgets.QGroupBox("Rota Ayarları")
        route_layout = QtWidgets.QFormLayout()
        self.src_edit = QtWidgets.QLineEdit("0")
        self.dst_edit = QtWidgets.QLineEdit(str(self.N - 1))
        self.src_edit.setMinimumHeight(30)
        self.dst_edit.setMinimumHeight(30)
        route_layout.addRow("Kaynak (S):", self.src_edit)
        route_layout.addRow("Hedef (D):", self.dst_edit)
        route_group.setLayout(route_layout)
        sidebar.addWidget(route_group)

        # Optimizasyon ağırlıkları (slider)
        weight_group = QtWidgets.QGroupBox("Optimizasyon Ağırlıkları")
        w_layout = QtWidgets.QVBoxLayout()
        w_layout.setSpacing(12)

        # Slider oluşturucu yardımcı fonksiyon
        def add_slider(label, val):
            l = QtWidgets.QVBoxLayout()
            l.setSpacing(2)
            top_row = QtWidgets.QHBoxLayout()
            top_row.addWidget(QtWidgets.QLabel(label))
            v_lbl = QtWidgets.QLabel(str(val))
            v_lbl.setAlignment(QtCore.Qt.AlignRight)
            top_row.addWidget(v_lbl)
            s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            s.setRange(0, 100)
            s.setValue(val)
            s.valueChanged.connect(lambda v, lb=v_lbl: lb.setText(str(v)))
            l.addLayout(top_row)
            l.addWidget(s)
            w_layout.addLayout(l)
            return s

        self.delay_slider = add_slider("Gecikme (Delay)", 40)
        self.rel_slider = add_slider("Güvenilirlik (Reliability)", 30)
        self.res_slider = add_slider("Kaynak (Resource)", 30)
        weight_group.setLayout(w_layout)
        sidebar.addWidget(weight_group)

        # Çalıştır butonu
        self.run_button = QtWidgets.QPushButton("HESAPLA VE ÇİZ")
        self.run_button.setMinimumHeight(50)
        self.run_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.run_button.clicked.connect(self.run_routing)
        sidebar.addWidget(self.run_button)
        sidebar.addStretch()

        sidebar_widget = QtWidgets.QWidget()
        sidebar_widget.setLayout(sidebar)
        sidebar_widget.setFixedWidth(360)
        main_layout.addWidget(sidebar_widget)

        # ------------------------------------------------------
        # ORTA PANEL (Grafik)
        # ------------------------------------------------------
        center_layout = QtWidgets.QVBoxLayout()
        title_graph = QtWidgets.QLabel(f"Ağ Topolojisi ({self.N} Düğüm)")
        title_graph.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
        center_layout.addWidget(title_graph)

        self.canvas = GraphCanvas(self)
        self.canvas.setStyleSheet("background-color: transparent;")
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
        center_layout.addWidget(self.canvas)
        main_layout.addLayout(center_layout, 1)

        # ------------------------------------------------------
        # SAĞ PANEL (Sonuçlar)
        # ------------------------------------------------------
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        lbl_results = QtWidgets.QLabel("Sonuçlar")
        lbl_results.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(lbl_results)

        # Seçili algoritmayı gösteren küçük etiket (pill)
        self.algo_pill = QtWidgets.QLabel("—")
        self.algo_pill.setAlignment(QtCore.Qt.AlignCenter)
        self.algo_pill.setStyleSheet("""
            QLabel {
                background-color: #7b2cff;
                color: #ffffff;
                border-radius: 12px;
                padding: 4px 10px;
                font-weight: 600;
                font-size: 11px;
            }
        """)
        header_layout.addStretch()
        header_layout.addWidget(self.algo_pill)
        right_layout.addLayout(header_layout)

        # Bulunan yol kartı
        self.path_frame = QtWidgets.QFrame()
        self.path_frame.setObjectName("resultCard")
        pf_layout = QtWidgets.QVBoxLayout(self.path_frame)

        top_path_row = QtWidgets.QHBoxLayout()
        self.lbl_path_title = QtWidgets.QLabel("Bulunan Yol")
        self.lbl_path_title.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.lbl_hops = QtWidgets.QLabel("(0 sıçrama)")
        self.lbl_hops.setStyleSheet("font-size: 11px; color: #a5b1c2;")
        top_path_row.addWidget(self.lbl_path_title)
        top_path_row.addStretch()
        top_path_row.addWidget(self.lbl_hops)
        pf_layout.addLayout(top_path_row)

        self.lbl_path_nodes = QtWidgets.QLabel("-")
        self.lbl_path_nodes.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {THEME['PATH_COLOR']};")
        self.lbl_path_nodes.setWordWrap(True)
        pf_layout.addWidget(self.lbl_path_nodes)
        right_layout.addWidget(self.path_frame)

        # Metrik kartları (2x2)
        grid_w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(grid_w)
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        c1, self.val_delay = create_card("Toplam Gecikme", "#4da3ff", big=True)
        c2, self.val_rel = create_card("Güvenilirlik", "#55efc4", big=True)
        c3, self.val_res = create_card("Kaynak Maliyeti", "#ffeaa7", big=True)
        c4, self.val_total = create_card("Ağırlıklı Maliyet", "#a29bfe", big=True)

        grid.addWidget(c1, 0, 0)
        grid.addWidget(c2, 0, 1)
        grid.addWidget(c3, 1, 0)
        grid.addWidget(c4, 1, 1)
        right_layout.addWidget(grid_w)

        # Hesaplama süresi satırı
        time_row = QtWidgets.QHBoxLayout()
        lbl_time_title = QtWidgets.QLabel("Hesaplama Süresi")
        lbl_time_title.setStyleSheet("font-size: 11px; color: #a5b1c2;")
        self.lbl_time_val = QtWidgets.QLabel("- ms")
        self.lbl_time_val.setStyleSheet("font-size: 13px; font-weight: 600;")
        time_row.addWidget(lbl_time_title)
        time_row.addStretch()
        time_row.addWidget(self.lbl_time_val)
        right_layout.addLayout(time_row)

        # Log alanı
        self.path_box = QtWidgets.QPlainTextEdit()
        self.path_box.setReadOnly(True)
        self.path_box.setPlaceholderText("Log kayıtları...")
        right_layout.addWidget(self.path_box)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setFixedWidth(280)
        main_layout.addWidget(right_widget)

        # İlk graf çizimi
        self.canvas.draw_graph(self.G)

    # Kullanıcı seçimine göre rota hesaplamayı başlatır
    def run_routing(self):
        try:
            src = int(self.src_edit.text())
            dst = int(self.dst_edit.text())
        except ValueError:
            return

        # Kaynak ve hedef düğüm doğrulaması
        if src not in self.G.nodes or dst not in self.G.nodes:
            QtWidgets.QMessageBox.warning(self, "Hata", f"Düğüm 0 ile {self.N-1} arasında olmalı!")
            return

        # DÜZELTME: Normalize edilmiş ağırlıkları kullan ve bu çalıştırma için sabitle
        weights = self._get_normalized_weights()
        self._last_weights = weights

        # Buton ve durum göstergelerini güncelle
        self.run_button.setText("Hesaplanıyor...")
        self.run_button.setEnabled(False)
        self.algo_pill.setText("Hesaplanıyor...")

        algo_key = self._algo_key()

        # Doğru sıra: (algo_key, G, src, dst, weights)
        self.worker = RoutingWorker(algo_key, self.G, src, dst, weights)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    # Hesaplama tamamlandığında arayüzü günceller
    def on_finished(self, path, cost, metrics):
        self.run_button.setText("HESAPLA VE ÇİZ")
        self.run_button.setEnabled(True)

        # Grafiği ve yolu yeniden çiz
        self.canvas.draw_graph(self.G, path)

        # Metrikleri doldur
        self.val_delay.setText(f"{metrics.get('delay', 0):.2f} ms" if metrics.get("delay") is not None else "-")
        self.val_rel.setText(f"{metrics.get('rel_cost', 0):.2f}" if metrics.get("rel_cost") is not None else "-")
        self.val_res.setText(f"{metrics.get('res_cost', 0):.2f}" if metrics.get("res_cost") is not None else "-")
        self.val_total.setText(f"{metrics.get('total_cost', cost):.4f}" if cost != float("inf") else "inf")
        self.lbl_time_val.setText(f"{metrics.get('time_ms', 0):.2f} ms")

        # Yol metnini hazırla
        path_str = " -> ".join(map(str, path)) if path else "-"
        self.lbl_path_nodes.setText(path_str)
        self.lbl_hops.setText(f"({len(path)-1} sıçrama)" if path else "(0 sıçrama)")

        # Seçili algoritmayı göster
        algo_name = self.algo_combo.currentText()
        self.algo_pill.setText(algo_name)

        # Bu çalıştırmada kullanılan ağırlıkları loga yaz
        w1, w2, w3 = getattr(self, "_last_weights", (0.0, 0.0, 0.0))
        self.path_box.setPlainText(
            f"Algoritma: {algo_name}\n"
            f"Ağırlıklar (normalize): gecikme={w1:.2f}, güvenilirlik={w2:.2f}, kaynak={w3:.2f}\n"
            f"Toplam Maliyet: {metrics.get('total_cost', cost)}\n"
            f"Yol: {path_str}"
        )

    # Hata olduğunda kullanıcıya gösterir
    def on_error(self, msg):
        self.run_button.setText("HESAPLA VE ÇİZ")
        self.run_button.setEnabled(True)
        self.algo_pill.setText("Hata")
        QtWidgets.QMessageBox.critical(self, "Hata", msg)

    # Fare grafiğin üzerinde hareket ederken en yakın düğüm için tooltip gösterir
    def on_mouse_move(self, event):
        if event.inaxes != self.canvas.ax:
            return
        if event.xdata is None or event.ydata is None:
            return

        closest_node = None
        min_dist = float('inf')
        search_limit = 0.05

        # Fareye yakın düğümü bul
        for node, (x, y) in self.canvas.pos.items():
            dist = math.sqrt((event.xdata - x)**2 + (event.ydata - y)**2)
            if dist < search_limit and dist < min_dist:
                min_dist = dist
                closest_node = node

        # Düğüm bulunduysa tooltip göster
        if closest_node is not None:
            props = self.G.nodes[closest_node]
            info_text = (f"<b>DÜĞÜM ID: {closest_node}</b><hr>"
                         f"İşlem Süresi: {props.get('processing_delay','-')} ms<br>"
                         f"Güvenilirlik: {props.get('reliability','-')}")
            QtWidgets.QToolTip.showText(QCursor.pos(), info_text)
        else:
            QtWidgets.QToolTip.hideText()


# ==========================================================
# Uygulama Başlatma
# ==========================================================
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    # Uygulama genel stil ayarları (CSS benzeri)
    app.setStyleSheet(f"""
        QWidget {{ background-color: {THEME['MAIN_BG']}; color: {THEME['TEXT']}; font-family: 'Segoe UI', sans-serif; }}
        QGroupBox {{ border: 1px solid {THEME['BORDER']}; border-radius: 6px; margin-top: 10px; padding: 10px; font-weight: bold; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
        QPushButton {{ background-color: {THEME['BUTTON']}; border: none; border-radius: 5px; padding: 8px; font-weight: bold; color: white; }}
        QPushButton:hover {{ background-color: {THEME['BUTTON_HOVER']}; }}
        QPushButton:disabled {{ background-color: #555; color: #aaa; }}
        QLineEdit, QComboBox, QPlainTextEdit {{ background-color: #262c33; border: 1px solid {THEME['BORDER']}; border-radius: 4px; padding: 4px; color: white; }}
        QFrame#resultCard {{ background-color: {THEME['CARD_BG']}; border: 1px solid {THEME['BORDER']}; border-radius: 8px; }}
        QSlider::groove:horizontal {{ height: 4px; background: {THEME['BORDER']}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; border-radius: 7px; background: {THEME['BUTTON']}; }}
    """)

    win = Window()
    win.show()
    sys.exit(app.exec_())
