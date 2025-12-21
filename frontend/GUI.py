import sys
import time
import math
import random
import itertools
import os
from pathlib import Path

import PyQt5

# PyQt5'in yüklü olduğu klasörü buluyoruz
dirname = os.path.dirname(PyQt5.__file__)
plugin_path = os.path.join(dirname, 'Qt5', 'plugins')

# Windows'a pluginlerin nerede olduğunu söylüyoruz
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

# Pandas Kontrolü
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# PyQt5 Kütüphaneleri
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QCursor

def create_card(title, color, big=False):
    card = QtWidgets.QFrame()
    card.setObjectName("metricCard")

    v = QtWidgets.QVBoxLayout(card)
    v.setContentsMargins(12, 10, 12, 10)
    v.setSpacing(6)

    lbl_title = QtWidgets.QLabel(title)
    lbl_title.setStyleSheet("color:#9fb3c8; font-size:11px;")

    lbl_val = QtWidgets.QLabel("--")
    lbl_val.setStyleSheet(
        f"color:{color}; font-size:{'22px' if big else '18px'}; font-weight:700;"
    )

    v.addWidget(lbl_title)
    v.addWidget(lbl_val)

    return card, lbl_val

# Grafik Kütüphaneleri
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D


# Yüksek Çözünürlük Ayarı
if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

# --- RENK PALETİ ---
THEME = {
    "MAIN_BG": "#111828",       
    "CARD_BG": "#1e293b",       
    "GRAPH_BG": "#111828",      
    "BORDER": "#3c4654",        
    "TEXT": "#f1f2f6",          
    "BUTTON": "#7b2cff",        
    "BUTTON_HOVER": "#6300A5",
    "BTN_COMPARE": "#10b981",   
    "NODE_COLOR": "#00d0ff",    
    "PATH_COLOR": "#ef4444"     
}

# Dosya Yolları
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
DEMAND_FILE = os.path.join(DATA_DIR, "BSM307_317_Guz2025_TermProject_DemandData(in).csv")

# ==========================================================
#  BACKEND SİMÜLASYONU
# ==========================================================
def run_simulation(algo_key, G, src, dst, weights):
    """Kıyaslama için sahte veri üretir (Gerçek backend yoksa)"""
    time.sleep(0.05) 
    try:
        path = nx.shortest_path(G, src, dst)
        base_cost = sum(G[u][v].get('delay', 5) for u, v in zip(path[:-1], path[1:]))
        
        # Algoritmalar arası karakteristik farklar
        var = 1.0
        time_base = 20
        
        if algo_key == "GA": 
            var = 1.0; time_base = 28
        elif algo_key == "RL": 
            var = 1.3; time_base = 18 # Hızlı ama maliyetli
        elif algo_key == "ABC": 
            var = 0.95; time_base = 40 # Yavaş ama iyi
        elif algo_key == "SA": 
            var = 1.1; time_base = 12

        # Biraz rastgelelik ekle
        final_delay = base_cost * var * random.uniform(0.95, 1.05)
        final_rel = random.uniform(0.85, 0.99)
        final_res = random.uniform(10, 30)
        
        metrics = {
            "delay": final_delay,
            "rel_cost": final_rel,
            "res_cost": final_res,
            "total_cost": (final_delay * weights[0]) + (100 * (1-final_rel) * weights[1]) + (final_res * weights[2]),
            "time_ms": time_base * random.uniform(0.9, 1.1)
        }
        return path, metrics["total_cost"], metrics
    except:
        return [], 0, {}

# ==========================================================
#  WORKER THREAD
# ==========================================================
class RoutingWorker(QThread):
    finished_single = pyqtSignal(list, float, dict)
    finished_batch = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, mode, algo_key, G, src, dst, weights):
        super().__init__()
        self.mode = mode 
        self.algo_key = algo_key
        self.G = G; self.src = src; self.dst = dst; self.weights = weights

    def run(self):
        try:
            if self.mode == "SINGLE":
                path, cost, metrics = run_simulation(self.algo_key, self.G, self.src, self.dst, self.weights)
                self.finished_single.emit(path or [], float(cost), metrics or {})
            
            elif self.mode == "COMPARE":
                results = {}
                for alg in ["GA", "RL", "ABC", "SA"]:
                    _, _, metrics = run_simulation(alg, self.G, self.src, self.dst, self.weights)
                    results[alg] = metrics
                self.finished_batch.emit(results)
        except Exception as e:
            self.error.emit(str(e))

# ==========================================================
#  GRAFİK 1: AĞ TOPOLOJİSİ (ZOOM + PAN)
# ==========================================================
class GraphCanvas(FigureCanvas):
    
    def __init__(self, parent=None):
        
        self.fig, self.ax = plt.subplots()
        super().__init__(self.fig)
        self.setParent(parent)

        self.fig.patch.set_facecolor(THEME["GRAPH_BG"])
        self.ax.set_facecolor(THEME["GRAPH_BG"])
        self.G = None  # Başlangıçta boş

        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.updateGeometry()
        self.pos = {}

        # --- EVENT BAĞLANTILARI ---
        self.mpl_connect("scroll_event", self.on_scroll)          # Zoom
        self.mpl_connect("button_press_event", self.on_press)     # Pan Başlangıç
        self.mpl_connect("button_release_event", self.on_release) # Pan Bitiş
        self.mpl_connect("motion_notify_event", self.on_mouse_move) # Pan Hareket + Tooltip

        # Pan değişkenleri
        self.panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0

    def on_press(self, event):
        """Fare tuşuna basıldığında (Sol tık = Pan Başlat)"""
        if event.button == 1 and event.inaxes == self.ax:
            self.panning = True
            self.pan_start_x = event.xdata
            self.pan_start_y = event.ydata
            self.setCursor(QtCore.Qt.ClosedHandCursor) # İmleci değiştir

    def on_release(self, event):
        """Fare tuşu bırakıldığında"""
        self.panning = False
        self.setCursor(QtCore.Qt.ArrowCursor) # İmleci normale döndür

    def on_mouse_move(self, event):
        """Fare hareket ettiğinde: Ya Pan yap ya da Tooltip göster"""
        if event.inaxes != self.ax: 
            return

        # 1. DURUM: SÜRÜKLEME (PAN) YAPILIYOR
        if self.panning and event.xdata is not None:
            dx = event.xdata - self.pan_start_x
            dy = event.ydata - self.pan_start_y
            
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
            
            self.draw()
            return # Sürüklerken tooltip gösterme

        # 2. DURUM: TOOLTIP (MOUSE OVER)
        if not event.xdata: return
        closest, min_d = None, float('inf')
        
        # Eğer self.pos boşsa tooltip hesaplama
        if not self.pos: return

        for n, (x, y) in self.pos.items():
            d = math.hypot(event.xdata - x, event.ydata - y)
            if d < 0.05 and d < min_d: min_d, closest = d, n
        
        # self.G var mı kontrol et 
        if closest is not None and self.G is not None:
            if closest in self.G.nodes:
                p = self.G.nodes[closest]
                txt = f"<b>DÜĞÜM {closest}</b><hr>İşlem: {p.get('processing_delay')}ms<br>Güven: {p.get('reliability')}"
                QtWidgets.QToolTip.showText(QCursor.pos(), txt)
        else:
            QtWidgets.QToolTip.hideText()

    def on_scroll(self, event):
        """Fare tekerleği ile zoom yapma (İmleç konumuna göre)"""
        if event.inaxes != self.ax: return
        
        base_scale = 1.2
        if event.button == 'up':
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            scale_factor = base_scale
        else:
            scale_factor = 1

        self.zoom_view(scale_factor, anchor_x=event.xdata, anchor_y=event.ydata)

    def zoom_view(self, scale_factor, anchor_x=None, anchor_y=None):
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()

        x_range = cur_xlim[1] - cur_xlim[0]
        y_range = cur_ylim[1] - cur_ylim[0]

        new_x_range = x_range * scale_factor
        new_y_range = y_range * scale_factor

        if anchor_x is not None and anchor_y is not None:
            # İmlece göre
            x_ratio = (anchor_x - cur_xlim[0]) / x_range
            y_ratio = (anchor_y - cur_ylim[0]) / y_range

            new_x_min = anchor_x - (new_x_range * x_ratio)
            new_y_min = anchor_y - (new_y_range * y_ratio)
        else:
            # Merkeze göre
            center_x = cur_xlim[0] + x_range / 2
            center_y = cur_ylim[0] + y_range / 2
            
            new_x_min = center_x - new_x_range / 2
            new_y_min = center_y - new_y_range / 2

        self.ax.set_xlim([new_x_min, new_x_min + new_x_range])
        self.ax.set_ylim([new_y_min, new_y_min + new_y_range])

        self.draw()

    def reset_view(self):
        self.ax.autoscale()
        self.draw()

    def draw_graph(self, G, path=None, src=None, dst=None):
        # BURADA G NESNESİNİ KAYDEDİYORUZ
        self.G = G  
        
        self.ax.clear()
        self.ax.set_facecolor(THEME["GRAPH_BG"])

        # Layout
        try:
            if not self.pos or set(self.pos.keys()) != set(G.nodes()):
                self.pos = nx.spring_layout(G, seed=42, iterations=30)
        except Exception:
            self.pos = nx.random_layout(G, seed=42)

        # Kenarlar
        nx.draw_networkx_edges(
            G, self.pos,
            edge_color="#404855",
            width=0.1,
            alpha=0.5,
            ax=self.ax
        )

        all_nodes = list(G.nodes())

        # Kaynak & hedef ayır
        special_nodes = set()
        if src is not None:
            special_nodes.add(src)
        if dst is not None:
            special_nodes.add(dst)

        normal_nodes = [n for n in all_nodes if n not in special_nodes]

        # Normal düğümler
        nx.draw_networkx_nodes(
            G, self.pos,
            nodelist=normal_nodes,
            node_size=30,
            node_color=THEME["NODE_COLOR"],
            alpha=0.9,
            ax=self.ax
        )

        # Kaynak (S)
        if src is not None:
            nx.draw_networkx_nodes(
                G, self.pos,
                nodelist=[src],
                node_color="#22c55e",
                node_size=100,
                ax=self.ax
            )

        # Hedef (D)
        if dst is not None:
            nx.draw_networkx_nodes(
                G, self.pos,
                nodelist=[dst],
                node_color="#ef4444",
                node_size=100,
                ax=self.ax
            )

        # Yol varsa
        if path is not None and len(path) > 1:
            path_edges = list(zip(path[:-1], path[1:]))

            nx.draw_networkx_edges(
                G, self.pos,
                edgelist=path_edges,
                width=2.8,
                edge_color=THEME["PATH_COLOR"],
                alpha=1.0,
                ax=self.ax
            )

            path_nodes = [
                n for n in path
                if n not in (src, dst)
            ]

            nx.draw_networkx_nodes(
                G, self.pos,
                nodelist=path_nodes,
                node_color=THEME["PATH_COLOR"],
                node_size=70,
                ax=self.ax
                            )
            
        # 🔁 Kaynak & hedefi EN SON tekrar çiz
        if src is not None:
            nx.draw_networkx_nodes(
                G, self.pos,
                nodelist=[src],
                node_color="#22c55e",
                node_size=100,
                ax=self.ax
            )

        if dst is not None:
            nx.draw_networkx_nodes(
                G, self.pos,
                nodelist=[dst],
                node_color="#ef4444",
                node_size=100,
                ax=self.ax
            )
        
            legend_elements = [
        Line2D([0], [0], marker='o', color='none',
            markerfacecolor="#22c55e", markersize=8, label="Kaynak"),

        Line2D([0], [0], marker='o', color='none',
            markerfacecolor="#ef4444", markersize=8, label="Hedef"),

        Line2D([0], [0], marker='o', color='none',
            markerfacecolor=THEME["PATH_COLOR"], markersize=8, label="Yol"),

        Line2D([0], [0], marker='o', color='none',
            markerfacecolor=THEME["NODE_COLOR"], markersize=8, label="Diğer"),
                            ]
            self.ax.legend(
        handles=legend_elements,
        loc="upper left",
        frameon=True,
        facecolor=THEME["GRAPH_BG"],
        edgecolor="#374151",
        labelcolor="white",
        fontsize=9
                   )

        self.ax.set_axis_off()
        self.fig.tight_layout()
        self.draw()

# ==========================================================
#  GRAFİK 2: PERFORMANS KIYASLAMA
# ==========================================================
class ComparisonCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.axs = plt.subplots(2, 2)
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.fig.patch.set_facecolor(THEME["GRAPH_BG"])
        self.fig.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.1, hspace=0.4, wspace=0.3)

    def update_charts(self, results):
        algos = ["GA", "RL", "ABC", "SA"]
        bar_colors = ["#22d3ee", "#818cf8", "#34d399", "#f472b6"]

        costs = [results.get(a, {}).get('total_cost', 0) for a in algos]
        times = [results.get(a, {}).get('time_ms', 0) for a in algos]
        delays = [results.get(a, {}).get('delay', 0) for a in algos]
        rels = [results.get(a, {}).get('rel_cost', 0) for a in algos]

        self._plot_bar(self.axs[0, 0], algos, costs, bar_colors, "Amaç Fonksiyonu (Maliyet)", "Düşük İyi")
        self._plot_bar(self.axs[0, 1], algos, times, bar_colors, "Hesaplama Süresi (ms)", "ms")
        self._plot_bar(self.axs[1, 0], algos, delays, bar_colors, "Toplam Gecikme", "ms")
        self._plot_bar(self.axs[1, 1], algos, rels, bar_colors, "Toplam Güvenilirlik", "Oran (0-1)")

        self.draw()

    def _plot_bar(self, ax, x, y, c, title, ylabel):
        ax.clear()
        ax.set_facecolor(THEME["GRAPH_BG"])
        ax.bar(x, y, color=c, width=0.6, zorder=3)
        ax.set_title(title, color='white', fontsize=10, fontweight='bold', pad=10)
        ax.set_ylabel(ylabel, color='#9ca3af', fontsize=8)
        ax.tick_params(axis='x', colors='white', labelsize=9)
        ax.tick_params(axis='y', colors='#9ca3af', labelsize=8)
        ax.grid(axis='y', linestyle='--', alpha=0.3, color='white', zorder=0)
        
        for spine in ax.spines.values():
            spine.set_edgecolor('#374151')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

# ==========================================================
#  ANA PENCERE
# ==========================================================
class Window(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QoS Yönlendirme Simülatörü")
        self.resize(1450, 850)
        
        self.df_demand = None
        if PANDAS_AVAILABLE and os.path.exists(DEMAND_FILE):
            try:
                self.df_demand = pd.read_csv(DEMAND_FILE, sep=";", encoding="utf-8")
                self.df_demand.columns = [c.strip().lower() for c in self.df_demand.columns]
            except: pass

        self.generate_initial_graph()
        self.build_ui()

    def generate_initial_graph(self):
        self.N = 250
        self.G = nx.erdos_renyi_graph(self.N, 0.4, seed=42)

        for u, v in self.G.edges():
            self.G[u][v]['bandwidth'] = random.randint(100, 1000)
            self.G[u][v]['delay'] = random.randint(3, 15)
            self.G[u][v]['reliability'] = round(random.uniform(0.95, 0.999), 4)

        for n in self.G.nodes():
            self.G.nodes[n]['processing_delay'] = round(random.uniform(0.5, 2.0), 2)
            self.G.nodes[n]['reliability'] = round(random.uniform(0.95, 0.999), 4)

    def on_scenario_changed(self, idx):
        data = self.scenario_combo.itemData(idx)
        if data:
            self.src_edit.setText(str(data[0]))
            self.dst_edit.setText(str(data[1]))

    def build_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # SOL PANEL
        sidebar = QtWidgets.QVBoxLayout()
        sidebar.setSpacing(15)

        # Algoritma
        gb_algo = QtWidgets.QGroupBox("Algoritma Seçimi")
        l_algo = QtWidgets.QVBoxLayout()
        self.algo_combo = QtWidgets.QComboBox()
        self.algo_combo.addItems(["Genetik Algoritma (GA)", "Q-Learning (RL)", "Yapay Arı (ABC)", "Benzetimli Tavlama (SA)"])
        l_algo.addWidget(self.algo_combo)
        gb_algo.setLayout(l_algo)
        sidebar.addWidget(gb_algo)

        # Rota
        gb_route = QtWidgets.QGroupBox("Rota Ayarları")
        l_route = QtWidgets.QFormLayout()
        
        self.scenario_combo = QtWidgets.QComboBox()
        loaded = False
        if self.df_demand is not None:
            try:
                cols = self.df_demand.columns
                src_c = next((c for c in cols if c in ['kaynak', 'src', 'source']), None)
                dst_c = next((c for c in cols if c in ['hedef', 'dst', 'destination']), None)
                bw_c  = next((c for c in cols if c in ['mbps', 'demand', 'bw']), None)
                if src_c and dst_c:
                    if not bw_c and len(cols) >= 3:
                        rem = [c for c in cols if c!=src_c and c!=dst_c]
                        if rem: bw_c = rem[0]
                    for _, row in self.df_demand.iterrows():
                        s, d = int(row[src_c]), int(row[dst_c])
                        m = int(row[bw_c]) if bw_c else 0
                        self.scenario_combo.addItem(f"S:{s} -> D:{d} | {m} Mbps", (s, d, m))
                    loaded = True
            except: pass
        if not loaded:
            self.scenario_combo.addItem("Örnek: S:0 -> D:249 | 100 Mbps", (0, 249, 100))

        self.scenario_combo.currentIndexChanged.connect(self.on_scenario_changed)
        l_route.addRow("Senaryo:", self.scenario_combo)
        self.src_edit = QtWidgets.QLineEdit("0"); self.dst_edit = QtWidgets.QLineEdit(str(self.N-1))
        l_route.addRow("Kaynak:", self.src_edit); l_route.addRow("Hedef:", self.dst_edit)
        gb_route.setLayout(l_route)
        sidebar.addWidget(gb_route)

        # Sliderlar
        gb_opt = QtWidgets.QGroupBox("Optimizasyon Ağırlıkları")
        l_opt = QtWidgets.QVBoxLayout()
        self.sliders = []
        for t, v in [("Gecikme", 40), ("Güvenilirlik", 30), ("Kaynak", 30)]:
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(str(v)); lbl.setFixedWidth(25)
            s = QtWidgets.QSlider(QtCore.Qt.Horizontal); s.setValue(v); s.setRange(0, 100)
            s.valueChanged.connect(lambda val, l=lbl: l.setText(str(val)))
            row.addWidget(QtWidgets.QLabel(t)); row.addWidget(s); row.addWidget(lbl)
            l_opt.addLayout(row); self.sliders.append(s)
        gb_opt.setLayout(l_opt)
        sidebar.addWidget(gb_opt)

        # Butonlar
        self.btn_run = QtWidgets.QPushButton("HESAPLA VE ÇİZ")
        self.btn_run.setMinimumHeight(45)
        self.btn_run.clicked.connect(self.run_single)
        sidebar.addWidget(self.btn_run)

        self.btn_compare = QtWidgets.QPushButton("TÜMÜNÜ KIYASLA")
        self.btn_compare.setMinimumHeight(45)
        self.btn_compare.setObjectName("compareBtn")
        self.btn_compare.clicked.connect(self.run_compare)
        sidebar.addWidget(self.btn_compare)

        sidebar.addStretch()
        w_side = QtWidgets.QWidget(); w_side.setLayout(sidebar); w_side.setFixedWidth(320)
        main_layout.addWidget(w_side)

        # ORTA PANEL (SEKMELER)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 0; }
            QTabBar::tab { background: #1e293b; color: #94a3b8; padding: 12px; margin-right: 4px; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: bold; }
            QTabBar::tab:selected { background: #7b2cff; color: white; }
        """)
        
        # --- TAB 1: Ağ Topolojisi + Zoom Kontrolleri ---
        tab1_widget = QtWidgets.QWidget()
        tab1_layout = QtWidgets.QVBoxLayout(tab1_widget)
        tab1_layout.setContentsMargins(0, 5, 0, 0)

        # Zoom Araç Çubuğu
        zoom_toolbar = QtWidgets.QHBoxLayout()
        zoom_toolbar.addStretch() 

        # BUTONLARI VE FONTU BÜYÜTTÜK
        btn_zoom_in = QtWidgets.QPushButton("+")
        btn_zoom_in.setFixedSize(40, 40) # 30->40
        btn_zoom_in.setToolTip("Yakınlaştır")
        btn_zoom_in.setStyleSheet("background-color: #374151; border-radius: 4px; font-size: 24px; font-weight: bold;")

        btn_zoom_out = QtWidgets.QPushButton("-")
        btn_zoom_out.setFixedSize(40, 40) # 30->40
        btn_zoom_out.setToolTip("Uzaklaştır")
        btn_zoom_out.setStyleSheet("background-color: #374151; border-radius: 4px; font-size: 24px; font-weight: bold;")
        
        btn_reset = QtWidgets.QPushButton("⟲")
        btn_reset.setFixedSize(40, 40) # 30->40
        btn_reset.setToolTip("Görünümü Sıfırla")
        btn_reset.setStyleSheet("background-color: #374151; border-radius: 4px; font-size: 20px; font-weight: bold;")

        zoom_toolbar.addWidget(btn_zoom_in)
        zoom_toolbar.addWidget(btn_zoom_out)
        zoom_toolbar.addWidget(btn_reset)

        self.canvas_net = GraphCanvas(self)
        
        # Buton olayları
        btn_zoom_in.clicked.connect(lambda: self.canvas_net.zoom_view(0.8))  
        btn_zoom_out.clicked.connect(lambda: self.canvas_net.zoom_view(1.25)) 
        btn_reset.clicked.connect(self.canvas_net.reset_view)

        tab1_layout.addLayout(zoom_toolbar)
        tab1_layout.addWidget(self.canvas_net)

        self.tabs.addTab(tab1_widget, "📍 AĞ TOPOLOJİSİ")

        # --- TAB 2: Performans ---
        self.canvas_perf = ComparisonCanvas(self)
        self.tabs.addTab(self.canvas_perf, "📊 ALGORİTMA PERFORMANS")

        main_layout.addWidget(self.tabs, 1)

        # SAĞ PANEL
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        lbl_results = QtWidgets.QLabel("Sonuçlar")
        lbl_results.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(lbl_results)

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

        grid_w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(grid_w)
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        c1, self.val_delay = create_card("Toplam Gecikme", "#c4c4c4", big=True)
        c2, self.val_rel = create_card("Güvenilirlik", "#c4c4c4", big=True)
        c3, self.val_res = create_card("Kaynak Maliyeti", "#c4c4c4", big=True)
        c4, self.val_total = create_card("Ağırlıklı Maliyet", "#c4c4c4", big=True)

        grid.addWidget(c1, 0, 0); grid.addWidget(c2, 0, 1)
        grid.addWidget(c3, 1, 0); grid.addWidget(c4, 1, 1)
        right_layout.addWidget(grid_w)

        time_row = QtWidgets.QHBoxLayout()
        lbl_time_title = QtWidgets.QLabel("Hesaplama Süresi")
        lbl_time_title.setStyleSheet("font-size: 11px; color: #a5b1c2;")
        self.lbl_time_val = QtWidgets.QLabel("- ms")
        self.lbl_time_val.setStyleSheet("font-size: 13px; font-weight: 600;")
        time_row.addWidget(lbl_time_title)
        time_row.addStretch()
        time_row.addWidget(self.lbl_time_val)
        right_layout.addLayout(time_row)

        self.path_box = QtWidgets.QTextEdit()
        self.path_box.setReadOnly(True)
        self.path_box.setStyleSheet("""
        QTextEdit{
            background:#1f2937;
            color:#e5e7eb;
            border-radius:10px;
            padding:10px;
            font-size:14px;
            font-family: Consolas, 'Courier New', monospace;
            }
            """)

        self.path_box.setReadOnly(True)
        self.path_box.setPlaceholderText("Log kayıtları...")
        right_layout.addWidget(self.path_box)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setFixedWidth(280)
        main_layout.addWidget(right_widget)

        self.canvas_net.draw_graph(self.G)

    # İŞLEVLER
    def run_single(self):
        try: s, d = int(self.src_edit.text()), int(self.dst_edit.text())
        except: return
        w = tuple(sl.value()/100 for sl in self.sliders)
        key = ["GA", "RL", "ABC", "SA"][self.algo_combo.currentIndex()]
        
        self.tabs.setCurrentIndex(0)
        self.btn_run.setText("Hesaplanıyor..."); self.btn_run.setEnabled(False)
        self.worker = RoutingWorker("SINGLE", key, self.G, s, d, w)
        self.worker.finished_single.connect(self.on_single_done)
        self.worker.start()

    def on_single_done(self, path, cost, metrics):
        self.btn_run.setText("HESAPLA VE ÇİZ"); self.btn_run.setEnabled(True)
        try: s, d = int(self.src_edit.text()), int(self.dst_edit.text())
        except: s, d = None, None
        self.canvas_net.draw_graph(self.G, path, s, d)
        
        self.algo_pill.setText(self.algo_combo.currentText())

        path_str = " -> ".join(map(str, path)) if path else "-"
        self.lbl_path_nodes.setText(path_str)
        self.lbl_hops.setText(f"({len(path)-1} sıçrama)" if path else "(0 sıçrama)")

        self.val_delay.setText(f"{metrics.get('delay',0):.2f} ms")
        self.val_rel.setText(f"{metrics.get('rel_cost',0):.2f}")
        self.val_res.setText(f"{metrics.get('res_cost',0):.2f}")
        self.val_total.setText(f"{metrics.get('total_cost', cost):.4f}")

        self.lbl_time_val.setText(f"{metrics.get('time_ms',0):.2f} ms")

        self.path_box.setPlainText(
            f"Algoritma: {self.algo_combo.currentText()}\n"
            f"Toplam Maliyet: {metrics.get('total_cost', cost)}\n"
            f"Yol: {path_str}"
)

    def run_compare(self):
        try: s, d = int(self.src_edit.text()), int(self.dst_edit.text())
        except: return
        w = tuple(sl.value()/100 for sl in self.sliders)
        
        self.tabs.setCurrentIndex(1)
        self.btn_compare.setText("Kıyaslanıyor..."); self.btn_compare.setEnabled(False)
        self.worker = RoutingWorker("COMPARE", "ALL", self.G, s, d, w)
        self.worker.finished_batch.connect(self.on_batch_done)
        self.worker.start()

    def on_batch_done(self, results):
        # BUTONU SIFIRLA VE AKTİF ET
        self.btn_compare.setText("TÜMÜNÜ KIYASLA")
        self.btn_compare.setEnabled(True)

        best_algo = None
        best_cost = float("inf")

        for algo, m in results.items():
            cost = float(m.get("total_cost", float("inf")))
            if cost < best_cost:
                best_cost = cost
                best_algo = algo

        def block(algo, m):
            return f"""
            <div style="margin-top:10px;">
            <b style="color:#93c5fd;">▶ {algo}</b><br>
            <span style="color:#cbd5f5;">Gecikme</span> : {m.get('delay',0):.2f} ms<br>
            <span style="color:#cbd5f5;">Güvenilirlik</span> : {m.get('rel_cost',0):.4f}<br>
            <span style="color:#cbd5f5;">Kaynak</span> : {m.get('res_cost',0):.4f}<br>
            <span style="color:#cbd5f5;">Toplam</span> : <b>{m.get('total_cost',0):.4f}</b><br>
            <span style="color:#cbd5f5;">Süre</span> : {m.get('time_ms',0):.2f} ms
            </div>
            """

        html = f"""
        <div>
        <h2 style="color:#60a5fa; margin-bottom:5px;">KIYASLAMA BİTTİ</h2>

        <p style="margin-top:10px;">
            <b>Önerilen Algoritma:</b><br>
            <span style="
                font-size:20px;
                font-weight:800;
                color:#22c55e;
            ">
            {best_algo}
            </span>
        </p>

        <p style="color:#a5b4fc;">
            En düşük <b>ağırlıklı maliyet</b> skoruna sahip.
        </p>

        <h3 style="margin-top:15px; color:#93c5fd;">DETAYLAR</h3>
        """

        ordered = sorted(results.items(), key=lambda kv: kv[1].get("total_cost", float("inf")))
        for algo, m in ordered:
            html += block(algo, m)

        html += "</div>"

        self.path_box.setHtml(html)

        try:
            self.canvas_perf.update_charts(results)
        except:
            pass

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(f"""
        QWidget {{ background-color: {THEME['MAIN_BG']}; color: {THEME['TEXT']}; font-family: 'Segoe UI'; }}
        QGroupBox {{ border: 1px solid {THEME['BORDER']}; border-radius: 6px; margin-top: 10px; padding: 10px; font-weight: bold; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {THEME['BUTTON']}; }}
        QPushButton {{ background-color: {THEME['BUTTON']}; border: none; border-radius: 5px; padding: 8px; font-weight: bold; color: white; }}
        QPushButton:hover {{ background-color: {THEME['BUTTON_HOVER']}; }}
        QPushButton#compareBtn {{ background-color: {THEME['BTN_COMPARE']}; }}
        QPushButton#compareBtn:hover {{ background-color: #059669; }}
        QLineEdit, QComboBox, QPlainTextEdit {{ background-color: #262c33; border: 1px solid {THEME['BORDER']}; border-radius: 4px; padding: 4px; color: white; }}
        QFrame#resultCard {{ background-color: {THEME['CARD_BG']}; border: 1px solid {THEME['BORDER']}; border-radius: 8px; }}
        QSlider::groove:horizontal {{ height: 4px; background: {THEME['BORDER']}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; border-radius: 7px; background: {THEME['BUTTON']}; }}
    """)
    win = Window()
    win.show()
    sys.exit(app.exec_())