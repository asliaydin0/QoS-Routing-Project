import sys
import time
import math
import random
import os
import csv
import statistics 

import PyQt5
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QCursor

# --- MATPLOTLIB AYARLARI ---
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D

# --- PROJE IMPORTLARI ---
try:
    from network_manager import NetworkManager
    from algorithms.ga import GeneticOptimizer
    from algorithms.ql import QLearningOptimizer
    from algorithms.abc_alg  import ABCOptimizer
    from algorithms.sa import SAOptimizer
    ALGO_IMPORTED = True
except ImportError as e:
    print(f"UYARI: Algoritma veya Manager dosyaları bulunamadı: {e}")
    ALGO_IMPORTED = False

# PyQt5 Plugin Yolu
dirname = os.path.dirname(PyQt5.__file__)
plugin_path = os.path.join(dirname, 'Qt5', 'plugins')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

# Yüksek Çözünürlük Ayarı
if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

# --- DOSYA YOLLARI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

NODE_FILE   = os.path.join(DATA_DIR, "BSM307_317_Guz2025_TermProject_NodeData(in).csv")
EDGE_FILE   = os.path.join(DATA_DIR, "BSM307_317_Guz2025_TermProject_EdgeData(in).csv")
DEMAND_FILE = os.path.join(DATA_DIR, "BSM307_317_Guz2025_TermProject_DemandData(in).csv")

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
    "BTN_BATCH": "#f59e0b",     
    "NODE_COLOR": "#00d0ff",    
    "PATH_COLOR": "#ef4444"     
}

# ==========================================================
#  YARDIMCI FONKSİYONLAR
# ==========================================================
def clean_cost_value(val):
    """
    Maliyet 1.000.000 üzerindeyse (ceza puanı varsa) bunu temizler.
    Böylece raporlarda ve grafiklerde saf maliyet görünür.
    """
    if val > 1000000:
        return val - 1000000
    return val

def dist_point_to_segment(px, py, x1, y1, x2, y2):
    l2 = (x1 - x2)**2 + (y1 - y2)**2
    if l2 == 0: return math.hypot(px - x1, py - y1)
    t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2
    t = max(0, min(1, t))
    proj_x = x1 + t * (x2 - x1)
    proj_y = y1 + t * (y2 - y1)
    return math.hypot(px - proj_x, py - proj_y)

def create_card(title, color, big=False):
    card = QtWidgets.QFrame()
    card.setObjectName("metricCard")
    v = QtWidgets.QVBoxLayout(card)
    v.setContentsMargins(12, 10, 12, 10)
    v.setSpacing(6)
    lbl_title = QtWidgets.QLabel(title)
    lbl_title.setStyleSheet("color:#9fb3c8; font-size:11px;")
    lbl_val = QtWidgets.QLabel("--")
    lbl_val.setStyleSheet(f"color:{color}; font-size:{'22px' if big else '18px'}; font-weight:700;")
    v.addWidget(lbl_title)
    v.addWidget(lbl_val)
    return card, lbl_val

# ==========================================================
#  SONUÇ PENCERESİ (YENİ EKLENEN SINIF)
# ==========================================================
class BatchResultsWindow(QtWidgets.QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Toplu Test Sonuçları")
        self.resize(1000, 600)
        self.data = data
        self.setStyleSheet(f"background-color: {THEME['MAIN_BG']}; color: {THEME['TEXT']};")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Başlık
        lbl = QtWidgets.QLabel("TOPLU TEST RAPORU")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #f59e0b; margin-bottom: 10px;")
        layout.addWidget(lbl)

        # Tablo
        self.table = QtWidgets.QTableWidget()
        self.table.setStyleSheet("""
            QTableWidget { background-color: #1e293b; border: 1px solid #3c4654; gridline-color: #3c4654; }
            QHeaderView::section { background-color: #0f172a; color: white; padding: 5px; font-weight: bold; border: 1px solid #3c4654; }
            QTableWidget::item { padding: 5px; }
        """)
        layout.addWidget(self.table)
        
        # Butonlar
        btn_layout = QtWidgets.QHBoxLayout()
        btn_export = QtWidgets.QPushButton("CSV OLARAK İNDİR")
        btn_export.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        btn_export.clicked.connect(self.export_csv)
        
        btn_close = QtWidgets.QPushButton("KAPAT")
        btn_close.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        btn_close.clicked.connect(self.close)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        
        self.populate_table()

    def populate_table(self):
        if not self.data: return
        
        headers = list(self.data[0].keys())
        self.table.setColumnCount(len(headers))
        self.table.setRowCount(len(self.data))
        self.table.setHorizontalHeaderLabels(headers)
        
        for row_idx, row_data in enumerate(self.data):
            for col_idx, key in enumerate(headers):
                val = row_data[key]
                item = QtWidgets.QTableWidgetItem(str(val))
                
                # Renklendirme
                if key == "Durum":
                    if val == "BAŞARILI": item.setForeground(QtGui.QColor("#22c55e"))
                    else: item.setForeground(QtGui.QColor("#ef4444"))
                
                self.table.setItem(row_idx, col_idx, item)
        
        self.table.resizeColumnsToContents()

    def export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Raporu Kaydet", "Toplu_Test_Sonuclari.csv", "CSV Files (*.csv)")
        if path:
            try:
                with open(path, mode='w', newline='', encoding='utf-8-sig') as file:
                    writer = csv.DictWriter(file, fieldnames=self.data[0].keys(), delimiter=';')
                    writer.writeheader()
                    writer.writerows(self.data)
                QtWidgets.QMessageBox.information(self, "Başarılı", "Dosya başarıyla kaydedildi.")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Hata", str(e))

# ==========================================================
#  BATCH WORKER (TOPLU TEST İÇİN)
# ==========================================================
class BatchTestWorker(QThread):
    progress_signal = pyqtSignal(int, str) 
    finished_signal = pyqtSignal(list)     

    def __init__(self, manager, demands, weights):
        super().__init__()
        self.manager = manager
        self.demands = demands
        self.weights = weights
        self.algorithms = ["GA", "RL", "ABC", "SA"]
        self.repetitions = 5

    def run(self):
        full_report = []
        target_scenario_count = 20
        scenarios_to_run = list(self.demands)
        
        # Eksikse rastgele tamamla
        while len(scenarios_to_run) < target_scenario_count:
            nodes = list(self.manager.G.nodes())
            if not nodes: break
            s = random.choice(nodes)
            d = random.choice(nodes)
            while s == d: d = random.choice(nodes)
            bw = random.choice([50, 100, 150, 250])
            scenarios_to_run.append({'src': s, 'dst': d, 'bw': bw})

        scenarios_to_run = scenarios_to_run[:max(len(self.demands), target_scenario_count)]
        total_steps = len(scenarios_to_run) * len(self.algorithms) * self.repetitions
        current_step = 0

        for i, sc in enumerate(scenarios_to_run):
            src, dst, bw = sc['src'], sc['dst'], sc['bw']
            # --- YOL KONTROLÜ ---
            # Eğer fiziksel olarak yol yoksa, boşuna 4 algoritmayı yorma.
            if not nx.has_path(self.manager.G, src, dst):
                # Rapora direkt "YOL YOK" yazıp geç
                for algo_name in self.algorithms:
                     row = {
                        "Senaryo": i + 1,
                        "Kaynak": src, "Hedef": dst, "Bant_Gen": bw,
                        "Algoritma": algo_name,
                        "Basari": "0/5", "Durum": "BAŞARISIZ",
                        "Ort_Maliyet": "0.00", "Std_Sapma": "0.00",
                        "En_Iyi": "0.00", "En_Kotu": "0.00", "Ort_Sure_ms": "0.00",
                        "Not": "Topolojik Yol Yok (Unreachable)"
                    }
                     full_report.append(row)
                continue # Bir sonraki senaryoya atla
            
            for algo_name in self.algorithms:
                costs = []
                times = []
                success_count = 0
                
                for r in range(self.repetitions):
                    current_step += 1
                    progress_pct = int((current_step / total_steps) * 100)
                    self.progress_signal.emit(progress_pct, f"Senaryo {i+1} - {algo_name} ({r+1}/{self.repetitions})")

                    optimizer = None
                    if algo_name == "GA": optimizer = GeneticOptimizer(self.manager, src, dst, bw)
                    elif algo_name == "RL": optimizer = QLearningOptimizer(self.manager, src, dst, bw)
                    elif algo_name == "ABC": optimizer = ABCOptimizer(self.manager, src, dst, bw)
                    elif algo_name == "SA": optimizer = SAOptimizer(self.manager, src, dst, bw)

                    t_start = time.time()
                    path, cost, metrics = optimizer.solve(self.weights)
                    t_end = time.time()
                    
                    if path:
                        costs.append(cost)
                        times.append((t_end - t_start) * 1000)
                        success_count += 1
                    
                if success_count > 0:
                    # --- Maliyetleri temizle ---
                    cleaned_costs = [clean_cost_value(c) for c in costs]
                    
                    avg_cost = statistics.mean(cleaned_costs)
                    # Standart sapma temizlenmiş veriden hesaplanır
                    std_dev = statistics.stdev(cleaned_costs) if len(cleaned_costs) > 1 else 0.0
                    best_cost = min(cleaned_costs)
                    worst_cost = max(cleaned_costs)
                    
                    avg_time = statistics.mean(times)
                    status = "BAŞARILI"
                    reason = "-"
                else:
                    avg_cost = 0; std_dev = 0; best_cost = 0; worst_cost = 0; avg_time = 0
                    status = "BAŞARISIZ"
                    reason = "Yol Bulunamadı"

                row = {
                    "Senaryo": i + 1,
                    "Kaynak": src,
                    "Hedef": dst,
                    "Bant_Gen": bw,
                    "Algoritma": algo_name,
                    "Basari": f"{success_count}/{self.repetitions}",
                    "Ort_Maliyet": f"{avg_cost:.2f}",
                    "Std_Sapma": f"{std_dev:.4f}", # Hassasiyet artırıldı
                    "En_Iyi": f"{best_cost:.2f}",
                    "En_Kotu": f"{worst_cost:.2f}",
                    "Ort_Sure_ms": f"{avg_time:.2f}",
                    "Durum": status,
                    "Not": reason
                }
                full_report.append(row)

        self.finished_signal.emit(full_report)

# ==========================================================
#  ROUTING WORKER
# ==========================================================
class RoutingWorker(QThread):
    finished_single = pyqtSignal(list, float, dict)
    finished_batch = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, mode, algo_key, manager, src, dst, weights, bw_demand=0):
        super().__init__()
        self.mode = mode 
        self.algo_key = algo_key
        self.manager = manager
        self.src = src
        self.dst = dst
        self.weights = weights
        self.bw_demand = bw_demand

    def _solve_with_algo(self, name):
        if not ALGO_IMPORTED: raise Exception("Algoritma dosyaları eksik!")
        start_time = time.time()
        optimizer = None
        if name == "GA": optimizer = GeneticOptimizer(self.manager, self.src, self.dst, self.bw_demand)
        elif name == "RL": optimizer = QLearningOptimizer(self.manager, self.src, self.dst, self.bw_demand)
        elif name == "ABC": optimizer = ABCOptimizer(self.manager, self.src, self.dst, self.bw_demand)
        elif name == "SA": optimizer = SAOptimizer(self.manager, self.src, self.dst, self.bw_demand)
        
        if optimizer: path, cost, metrics = optimizer.solve(self.weights)
        else: path, cost, metrics = [], 0, {}

        end_time = time.time()
        if not path:
            metrics['success'] = False
            metrics['total_cost'] = float('inf')
        else:
            metrics['success'] = True
        metrics['time_ms'] = (end_time - start_time) * 1000
        return path, cost, metrics

    def run(self):
        try:
            if self.mode == "SINGLE":
                path, cost, metrics = self._solve_with_algo(self.algo_key)
                self.finished_single.emit(path or [], float(cost), metrics or {})
            elif self.mode == "COMPARE":
                results = {}
                algo_list = ["GA", "RL", "ABC", "SA"] 
                for alg in algo_list:
                    _, _, metrics = self._solve_with_algo(alg)
                    results[alg] = metrics
                self.finished_batch.emit(results)
        except Exception as e:
            self.error.emit(str(e))

# ==========================================================
#  GRAFİK 1: AĞ TOPOLOJİSİ (GraphCanvas)
# ==========================================================
class GraphCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = plt.subplots()
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        super().__init__(self.fig)
        self.setParent(parent)
        self.fig.patch.set_facecolor(THEME["GRAPH_BG"])
        self.ax.set_facecolor(THEME["GRAPH_BG"])
        self.G = None
        self.pos = {}
        self.highlight_artists = []
        self.last_hovered_edge = None
        self.last_hovered_node = None
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.updateGeometry()
        self.mpl_connect("scroll_event", self.on_scroll)
        self.mpl_connect("button_press_event", self.on_press)
        self.mpl_connect("button_release_event", self.on_release)
        self.mpl_connect("motion_notify_event", self.on_mouse_move)
        self.panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0

    def on_press(self, event):
        if event.inaxes == self.ax and event.button in [1, 3]:
            if not self.pos: return
            closest, min_d = None, 0.08
            for n, (x, y) in self.pos.items():
                d = math.hypot(event.xdata - x, event.ydata - y)
                if d < min_d: min_d = d; closest = n
            
            if closest is not None:
                mode = "src" if event.button == 1 else "dst"
                mw = self.parent()
                while mw and not isinstance(mw, QtWidgets.QMainWindow) and not isinstance(mw, QtWidgets.QWidget): mw = mw.parent()
                if hasattr(mw, 'set_node_from_click'): mw.set_node_from_click(closest, mode)
                return 

        if event.button == 1 and event.inaxes == self.ax:
            self.panning = True
            self.pan_start_x = event.xdata; self.pan_start_y = event.ydata
            self.setCursor(QtCore.Qt.ClosedHandCursor)

    def on_release(self, event):
        self.panning = False
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.draw_idle()

    def on_mouse_move(self, event):
        if event.inaxes != self.ax: return
        if self.panning and event.xdata:
            dx = event.xdata - self.pan_start_x; dy = event.ydata - self.pan_start_y
            xlim = self.ax.get_xlim(); ylim = self.ax.get_ylim()
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
            self.draw_idle()
            return

        if not event.xdata or not self.pos or not self.G: return
        
        closest_node = None
        min_d_node = 0.08 
        for n, (x, y) in self.pos.items():
            if abs(x - event.xdata) > min_d_node or abs(y - event.ydata) > min_d_node: continue
            d = math.hypot(event.xdata - x, event.ydata - y)
            if d < min_d_node: min_d_node = d; closest_node = n
        
        closest_edge = None
        if closest_node is None:
            min_d_edge = 0.05
            for u, v in self.G.edges():
                if u not in self.pos or v not in self.pos: continue
                x1, y1 = self.pos[u]; x2, y2 = self.pos[v]
                margin = 0.1
                if not (min(x1, x2) - margin < event.xdata < max(x1, x2) + margin and
                        min(y1, y2) - margin < event.ydata < max(y1, y2) + margin): continue
                d = dist_point_to_segment(event.xdata, event.ydata, x1, y1, x2, y2)
                if d < min_d_edge: min_d_edge = d; closest_edge = (u, v)

        if closest_node != self.last_hovered_node or closest_edge != self.last_hovered_edge:
            self.last_hovered_node = closest_node
            self.last_hovered_edge = closest_edge
            for artist in self.highlight_artists: artist.remove()
            self.highlight_artists = []

            if closest_node is not None:
                x, y = self.pos[closest_node]
                c = plt.Circle((x, y), 0.01, color='#facc15', zorder=10, alpha=1.0)
                self.ax.add_patch(c); self.highlight_artists.append(c)
                p = self.G.nodes[closest_node]
                txt = f"<b>DÜĞÜM {closest_node}</b><hr>İşlem: {p.get('processing_delay',0)}ms<br>Güven: {p.get('reliability',0)}"
                QtWidgets.QToolTip.showText(QCursor.pos(), txt)
            
            elif closest_edge is not None:
                u, v = closest_edge
                x1, y1 = self.pos[u]; x2, y2 = self.pos[v]
                l, = self.ax.plot([x1, x2], [y1, y2], color="#facc15", linewidth=2.5, alpha=1.0, zorder=10)
                self.highlight_artists.append(l)
                data = self.G[u][v]
                txt = (f"<b>BAĞLANTI: {u} ↔ {v}</b><hr>BW: {data.get('bandwidth','-')} Mbps<br>Gecikme: {data.get('delay','-')} ms")
                QtWidgets.QToolTip.showText(QCursor.pos(), txt)
            else:
                QtWidgets.QToolTip.hideText()
            self.draw_idle()

    def on_scroll(self, event):
        if event.inaxes != self.ax: return
        scale_factor = 1/1.2 if event.button == 'up' else 1.2
        self.zoom_view(scale_factor, event.xdata, event.ydata)

    def zoom_view(self, scale_factor, anchor_x=None, anchor_y=None):
        cur_xlim = self.ax.get_xlim(); cur_ylim = self.ax.get_ylim()
        if (cur_xlim[1] - cur_xlim[0]) < 0.1 and scale_factor < 1: return
        x_range = cur_xlim[1] - cur_xlim[0]; y_range = cur_ylim[1] - cur_ylim[0]
        new_x_range = x_range * scale_factor; new_y_range = y_range * scale_factor
        if anchor_x is not None:
            x_ratio = (anchor_x - cur_xlim[0]) / x_range; y_ratio = (anchor_y - cur_ylim[0]) / y_range
            new_x_min = anchor_x - (new_x_range * x_ratio); new_y_min = anchor_y - (new_y_range * y_ratio)
        else:
            cx = cur_xlim[0] + x_range/2; cy = cur_ylim[0] + y_range/2
            new_x_min = cx - new_x_range/2; new_y_min = cy - new_y_range/2
        self.ax.set_xlim([new_x_min, new_x_min + new_x_range])
        self.ax.set_ylim([new_y_min, new_y_min + new_y_range])
        self.draw_idle()

    def reset_view(self):
        self.ax.autoscale(); self.draw_idle()

    def draw_graph(self, G, path=None, src=None, dst=None):
        self.G = G; self.ax.clear(); self.ax.set_facecolor(THEME["GRAPH_BG"])
        self.highlight_artists = []; self.last_hovered_edge = None; self.last_hovered_node = None
        
        COLOR_BG_NODE = "#60a5fa"; COLOR_BG_EDGE = "#475569"
        COLOR_SRC = "#22c55e"; COLOR_DST = "#ef4444"; COLOR_PATH = "#00e5ff"
        
        if not self.pos or set(self.pos.keys()) != set(G.nodes()):
            try: self.pos = nx.kamada_kawai_layout(G)
            except: self.pos = nx.spring_layout(G, seed=42)

        nx.draw_networkx_edges(G, self.pos, edge_color=COLOR_BG_EDGE, width=0.8, alpha=0.4, ax=self.ax, arrows=False)
        
        all_nodes = list(G.nodes()); path_nodes_set = set(path) if path else set()
        special_nodes = {src, dst} if src is not None else set()
        bg_nodes = [n for n in all_nodes if n not in path_nodes_set and n not in special_nodes]
        nx.draw_networkx_nodes(G, self.pos, nodelist=bg_nodes, node_size=45, node_color=COLOR_BG_NODE, alpha=1.0, ax=self.ax, edgecolors="#1e293b", linewidths=0.5).set_zorder(2)

        if path and len(path) > 1:
            path_edges = list(zip(path[:-1], path[1:]))
            nx.draw_networkx_edges(G, self.pos, edgelist=path_edges, width=3.0, edge_color=COLOR_PATH, alpha=1.0, ax=self.ax, arrows=True, arrowsize=20, arrowstyle='-|>')
            path_mid_nodes = [n for n in path if n not in (src, dst)]
            nx.draw_networkx_nodes(G, self.pos, nodelist=path_mid_nodes, node_color=COLOR_PATH, node_size=80, ax=self.ax, linewidths=1.5, edgecolors="white").set_zorder(4)

        if src is not None and src in G:
            nx.draw_networkx_nodes(G, self.pos, nodelist=[src], node_color=COLOR_SRC, node_size=220, ax=self.ax, edgecolors="white", linewidths=2.5).set_zorder(5)
        if dst is not None and dst in G:
            nx.draw_networkx_nodes(G, self.pos, nodelist=[dst], node_color=COLOR_DST, node_size=220, ax=self.ax, edgecolors="white", linewidths=2.5).set_zorder(5)

        legend_elements = [
            Line2D([0], [0], marker='o', color='none', markerfacecolor=COLOR_SRC, markersize=10, label="Kaynak (S)", markeredgecolor='white'),
            Line2D([0], [0], marker='o', color='none', markerfacecolor=COLOR_DST, markersize=10, label="Hedef (D)", markeredgecolor='white'),
            Line2D([0], [0], marker='o', color='none', markerfacecolor=COLOR_PATH, markersize=10, label="Seçilen Yol", markeredgecolor='white'),
            Line2D([0], [0], color='#facc15', lw=3, label="Seçim (Mouse)"),
        ]
        legend = self.ax.legend(handles=legend_elements, loc="upper left", frameon=True, facecolor=THEME["GRAPH_BG"], edgecolor="#374151", labelcolor="white", fontsize=9)
        legend.get_frame().set_alpha(0.85)
        self.ax.set_axis_off(); self.draw_idle()

# ==========================================================
#  GRAFİK 2: PERFORMANS KIYASLAMA
# ==========================================================
class ComparisonCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.axs = plt.subplots(2, 2)
        super().__init__(self.fig)
        self.setParent(parent)
        self.fig.patch.set_facecolor(THEME["GRAPH_BG"])
        self.fig.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.1, hspace=0.5, wspace=0.3)

    def update_charts(self, results):
        algos = list(results.keys()); bar_colors = ["#22d3ee", "#818cf8", "#34d399", "#f472b6"][:len(algos)]
        costs = []; times = []; delays = []; rels = []; labels = []
        for a in algos:
            m = results[a]
            if m.get('success', False):
                # --- Grafiklere Temiz Maliyeti Bas ---
                raw_c = m.get('total_cost', 0)
                clean_c = clean_cost_value(raw_c)
                
                costs.append(clean_c)
                times.append(m.get('time_ms', 0))
                delays.append(m.get('delay', 0)); rels.append(m.get('rel_prob', 0)); labels.append(None)
            else:
                costs.append(0); times.append(m.get('time_ms', 0)); delays.append(0); rels.append(0); labels.append("X")

        self._plot_bar(self.axs[0, 0], algos, costs, bar_colors, "Maliyet (Düşük İyi)", "Maliyet", labels)
        self._plot_bar(self.axs[0, 1], algos, times, bar_colors, "Süre (ms)", "ms", [None]*4)
        self._plot_bar(self.axs[1, 0], algos, delays, bar_colors, "Gecikme", "ms", labels)
        self._plot_bar(self.axs[1, 1], algos, rels, bar_colors, "Güvenilirlik", "(0-1)", labels)
        self.draw_idle()

    def _plot_bar(self, ax, x, y, c, title, ylabel, custom_labels=None):
        ax.clear(); ax.set_facecolor(THEME["GRAPH_BG"])
        bars = ax.bar(x, y, color=c, width=0.5, zorder=3)
        ax.set_title(title, color='white', fontsize=9, fontweight='bold', pad=8)
        ax.set_ylabel(ylabel, color='#9ca3af', fontsize=8)
        ax.tick_params(axis='x', colors='white', labelsize=8); ax.tick_params(axis='y', colors='#9ca3af', labelsize=8)
        ax.grid(axis='y', linestyle='--', alpha=0.2, color='white', zorder=0)
        for i, bar in enumerate(bars):
            height = bar.get_height()
            text_val = custom_labels[i] if custom_labels and custom_labels[i] else f'{height:.2f}'
            text_color = "#ef4444" if custom_labels and custom_labels[i] else "white"
            ax.text(bar.get_x() + bar.get_width()/2., height, text_val, ha='center', va='bottom', color=text_color, fontsize=7, fontweight='bold')
        for spine in ax.spines.values(): spine.set_edgecolor('#374151')
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)

# ==========================================================
#  ANA PENCERE
# ==========================================================
class Window(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QoS Yönlendirme Simülatörü")
        self.resize(1450, 850)
        self.last_results = None 
        self.manager = None; self.G = nx.Graph() 
        
        if ALGO_IMPORTED:
            self.manager = NetworkManager()
            if os.path.exists(NODE_FILE) and os.path.exists(EDGE_FILE):
                success = self.manager.load_data(NODE_FILE, EDGE_FILE, DEMAND_FILE)
                if success: self.G = self.manager.G
                else: QtWidgets.QMessageBox.critical(self, "Hata", "CSV okunamadı!")
            else: QtWidgets.QMessageBox.warning(self, "Dosya Yok", f"Veri dosyaları eksik:\n{DATA_DIR}")

        self.build_ui(); self.canvas_net.draw_graph(self.G)

    def on_scenario_changed(self, idx):
        data = self.scenario_combo.itemData(idx)
        if data:
            self.src_edit.setText(str(data['src'])); self.dst_edit.setText(str(data['dst'])); self.current_bw_demand = data['bw']
            self.canvas_net.draw_graph(self.G, path=None, src=data['src'], dst=data['dst'])

    def set_node_from_click(self, node_id, mode):
        if mode == "src": self.src_edit.setText(str(node_id))
        else: self.dst_edit.setText(str(node_id))
        try:
            s = int(self.src_edit.text()); d = int(self.dst_edit.text())
            self.canvas_net.draw_graph(self.G, path=None, src=s, dst=d)
        except: pass

    # --- TOPLU TEST FONKSİYONLARI ---
    def run_batch_test(self):
        reply = QtWidgets.QMessageBox.question(self, 'Toplu Test Başlat', 
            "Bu işlem arka planda toplu test yapıp sonuç penceresini açacaktır.\nBaşlatılsın mı?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            self.btn_batch.setEnabled(False)
            self.btn_batch.setText("Test Yapılıyor... (%0)")
            w = tuple(sl.value()/100 for sl in self.sliders)
            
            self.batch_worker = BatchTestWorker(self.manager, self.manager.demands, w)
            self.batch_worker.progress_signal.connect(self.update_batch_progress)
            self.batch_worker.finished_signal.connect(self.show_batch_results)
            self.batch_worker.start()

    def update_batch_progress(self, val, msg):
        self.btn_batch.setText(f"İşleniyor... (%{val})")
        self.path_box.setPlainText(f"DURUM: {msg}")

    def show_batch_results(self, report_data):
        self.btn_batch.setEnabled(True)
        self.btn_batch.setText("OTOMATİK TOPLU TEST")
        self.path_box.setPlainText("Test tamamlandı. Sonuç penceresi açıldı.")
        
        # Sonuç penceresini aç
        self.results_window = BatchResultsWindow(report_data, self)
        self.results_window.show()

    def export_results(self):
        if not self.last_results:
            QtWidgets.QMessageBox.warning(self, "Uyarı", "Kaydedilecek sonuç yok.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Sonuçları Kaydet", "", "CSV Files (*.csv)")
        if path:
            try:
                with open(path, mode='w', newline='', encoding='utf-8-sig') as file:
                    writer = csv.writer(file, delimiter=';')
                    writer.writerow(["Algoritma", "Maliyet", "Gecikme", "Güvenilirlik", "Kaynak", "Süre"])
                    for algo, m in self.last_results.items():
                        writer.writerow([algo, m.get('total_cost'), m.get('delay'), m.get('rel_prob'), m.get('res_cost'), m.get('time_ms')])
                QtWidgets.QMessageBox.information(self, "Başarılı", "Kayıt tamamlandı.")
            except Exception as e: QtWidgets.QMessageBox.critical(self, "Hata", str(e))

    def build_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self); main_layout.setContentsMargins(10, 10, 10, 10); main_layout.setSpacing(15)
        sidebar = QtWidgets.QVBoxLayout(); sidebar.setSpacing(15)

        gb_algo = QtWidgets.QGroupBox("Algoritma Seçimi"); l_algo = QtWidgets.QVBoxLayout()
        self.algo_combo = QtWidgets.QComboBox(); self.algo_combo.addItems(["Genetik Algoritma (GA)", "Q-Learning (RL)", "Yapay Arı (ABC)", "Benzetimli Tavlama (SA)"])
        l_algo.addWidget(self.algo_combo); gb_algo.setLayout(l_algo); sidebar.addWidget(gb_algo)

        gb_route = QtWidgets.QGroupBox("Rota & Talep"); l_route = QtWidgets.QFormLayout()
        self.scenario_combo = QtWidgets.QComboBox()
        if self.manager and self.manager.demands:
            for i, dem in enumerate(self.manager.demands): self.scenario_combo.addItem(f"Senaryo {i+1}: S:{dem['src']} -> D:{dem['dst']} | {dem['bw']} Mbps", dem)
        else: self.scenario_combo.addItem("Manuel Giriş", {'src':0, 'dst':1, 'bw':0})
        self.scenario_combo.currentIndexChanged.connect(self.on_scenario_changed)
        l_route.addRow("Talep Listesi:", self.scenario_combo)
        self.src_edit = QtWidgets.QLineEdit("0"); self.dst_edit = QtWidgets.QLineEdit("1")
        l_route.addRow("Kaynak:", self.src_edit); l_route.addRow("Hedef:", self.dst_edit)
        gb_route.setLayout(l_route); sidebar.addWidget(gb_route)

        gb_opt = QtWidgets.QGroupBox("Optimizasyon Ağırlıkları"); l_opt = QtWidgets.QVBoxLayout()
        self.sliders = []
        for t, v in [("Gecikme", 40), ("Güvenilirlik", 30), ("Kaynak", 30)]:
            row = QtWidgets.QHBoxLayout(); lbl = QtWidgets.QLabel(str(v)); lbl.setFixedWidth(25)
            s = QtWidgets.QSlider(QtCore.Qt.Horizontal); s.setValue(v); s.setRange(0, 100)
            s.valueChanged.connect(lambda val, l=lbl: l.setText(str(val)))
            row.addWidget(QtWidgets.QLabel(t)); row.addWidget(s); row.addWidget(lbl)
            l_opt.addLayout(row); self.sliders.append(s)
        gb_opt.setLayout(l_opt); sidebar.addWidget(gb_opt)

          # --- EKLEMENİZ GEREKEN KISIM ---
        # --- ŞIK VE MOR BAŞLIKLI SEED GRUBU ---
        self.gb_seed = QtWidgets.QGroupBox("Rastgelelik Ayarları") # Bu başlık otomatik mor olur
        l_seed = QtWidgets.QVBoxLayout()
        
        self.seed_label = QtWidgets.QLabel("Tohum Değeri (Seed):")
        self.seed_input = QtWidgets.QSpinBox()
        self.seed_input.setRange(0, 999999)
        self.seed_input.setValue(42)
        self.seed_input.setMinimumHeight(35)
        
        l_seed.addWidget(self.seed_label)
        l_seed.addWidget(self.seed_input)
        self.gb_seed.setLayout(l_seed)
        
        # Grubu sidebar'a ekliyoruz
        sidebar.addWidget(self.gb_seed) 

        
# ------------------------------
        self.btn_run = QtWidgets.QPushButton("HESAPLA VE ÇİZ"); self.btn_run.setMinimumHeight(45)
        self.btn_run.clicked.connect(self.run_single); sidebar.addWidget(self.btn_run)

        self.btn_compare = QtWidgets.QPushButton("TÜMÜNÜ KIYASLA"); self.btn_compare.setMinimumHeight(45)
        self.btn_compare.setObjectName("compareBtn"); self.btn_compare.clicked.connect(self.run_compare)
        sidebar.addWidget(self.btn_compare)

        # --- YENİ BATCH TEST BUTONU ---
        self.btn_batch = QtWidgets.QPushButton("OTOMATİK TOPLU TEST")
        self.btn_batch.setMinimumHeight(50)
        self.btn_batch.setStyleSheet(f"background-color: {THEME['BTN_BATCH']}; color: white; font-weight: bold; border-radius: 5px;")
        self.btn_batch.clicked.connect(self.run_batch_test)
        sidebar.addWidget(self.btn_batch)

        self.btn_export = QtWidgets.QPushButton("Tekil Sonuç Kaydet"); self.btn_export.setStyleSheet("background-color: #4b5563; color: white; padding: 8px;")
        self.btn_export.clicked.connect(self.export_results); sidebar.addWidget(self.btn_export)

        sidebar.addStretch(); w_side = QtWidgets.QWidget(); w_side.setLayout(sidebar); w_side.setFixedWidth(320)
        main_layout.addWidget(w_side)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 0; } QTabBar::tab { background: #1e293b; color: #94a3b8; padding: 12px; margin-right: 4px; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: bold; } QTabBar::tab:selected { background: #7b2cff; color: white; }")
        
        tab1_widget = QtWidgets.QWidget(); tab1_layout = QtWidgets.QVBoxLayout(tab1_widget); tab1_layout.setContentsMargins(0, 5, 0, 0)
        zoom_toolbar = QtWidgets.QHBoxLayout(); zoom_toolbar.addStretch()
        btn_in = QtWidgets.QPushButton("+"); btn_out = QtWidgets.QPushButton("-"); btn_rst = QtWidgets.QPushButton("⟲")
        for b in [btn_in, btn_out, btn_rst]: b.setFixedSize(40,40); b.setStyleSheet("background-color: #374151; border-radius: 4px; font-size: 20px; font-weight: bold;"); zoom_toolbar.addWidget(b)
        self.canvas_net = GraphCanvas(self)
        btn_in.clicked.connect(lambda: self.canvas_net.zoom_view(0.8)); btn_out.clicked.connect(lambda: self.canvas_net.zoom_view(1.25)); btn_rst.clicked.connect(self.canvas_net.reset_view)
        tab1_layout.addLayout(zoom_toolbar); tab1_layout.addWidget(self.canvas_net); self.tabs.addTab(tab1_widget, "📍 AĞ TOPOLOJİSİ")

        self.canvas_perf = ComparisonCanvas(self); self.tabs.addTab(self.canvas_perf, "📊 ALGORİTMA PERFORMANS")
        main_layout.addWidget(self.tabs, 1)

        right_layout = QtWidgets.QVBoxLayout(); right_layout.setSpacing(10)
        header_layout = QtWidgets.QHBoxLayout(); lbl_results = QtWidgets.QLabel("Sonuçlar"); lbl_results.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.algo_pill = QtWidgets.QLabel("—"); self.algo_pill.setAlignment(QtCore.Qt.AlignCenter); self.algo_pill.setStyleSheet("background-color: #7b2cff; color: white; border-radius: 12px; padding: 4px 10px; font-weight: 600; font-size: 11px;")
        header_layout.addWidget(lbl_results); header_layout.addStretch(); header_layout.addWidget(self.algo_pill); right_layout.addLayout(header_layout)

        self.path_frame = QtWidgets.QFrame(); self.path_frame.setObjectName("resultCard"); pf_layout = QtWidgets.QVBoxLayout(self.path_frame)
        top_path_row = QtWidgets.QHBoxLayout(); self.lbl_path_title = QtWidgets.QLabel("Bulunan Yol"); self.lbl_path_title.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.lbl_hops = QtWidgets.QLabel("(0 sıçrama)"); self.lbl_hops.setStyleSheet("font-size: 11px; color: #a5b1c2;")
        top_path_row.addWidget(self.lbl_path_title); top_path_row.addStretch(); top_path_row.addWidget(self.lbl_hops); pf_layout.addLayout(top_path_row)
        self.lbl_path_nodes = QtWidgets.QLabel("-"); self.lbl_path_nodes.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {THEME['PATH_COLOR']};"); self.lbl_path_nodes.setWordWrap(True); pf_layout.addWidget(self.lbl_path_nodes); right_layout.addWidget(self.path_frame)

        grid_w = QtWidgets.QWidget(); grid = QtWidgets.QGridLayout(grid_w); grid.setSpacing(8); grid.setContentsMargins(0,0,0,0)
        c1, self.val_delay = create_card("Toplam Gecikme", "#c4c4c4", big=True); c2, self.val_rel = create_card("Güvenilirlik", "#c4c4c4", big=True)
        c3, self.val_res = create_card("Kaynak Maliyeti", "#c4c4c4", big=True); c4, self.val_total = create_card("Ağırlıklı Maliyet", "#c4c4c4", big=True)
        grid.addWidget(c1, 0, 0); grid.addWidget(c2, 0, 1); grid.addWidget(c3, 1, 0); grid.addWidget(c4, 1, 1); right_layout.addWidget(grid_w)

        time_row = QtWidgets.QHBoxLayout(); lbl_time_title = QtWidgets.QLabel("Hesaplama Süresi"); lbl_time_title.setStyleSheet("font-size: 11px; color: #a5b1c2;")
        self.lbl_time_val = QtWidgets.QLabel("- ms"); self.lbl_time_val.setStyleSheet("font-size: 13px; font-weight: 600;")
        time_row.addWidget(lbl_time_title); time_row.addStretch(); time_row.addWidget(self.lbl_time_val); right_layout.addLayout(time_row)

        self.path_box = QtWidgets.QTextEdit(); self.path_box.setReadOnly(True); self.path_box.setStyleSheet("background:#1f2937; color:#e5e7eb; border-radius:10px; padding:10px; font-size:14px; font-family: Consolas, monospace;")
        self.path_box.setPlaceholderText("Log kayıtları..."); right_layout.addWidget(self.path_box)

        w_right = QtWidgets.QWidget(); w_right.setLayout(right_layout); w_right.setFixedWidth(280); main_layout.addWidget(w_right)

        if self.scenario_combo.count() > 0: self.on_scenario_changed(0)

    # --- TEKİL VE KIYASLAMA İŞLEVLERİ ---
    def run_single(self):
        # --- SEED AKTİF ETME (EKLEDİĞİMİZ KISIM) ---
        user_seed = self.seed_input.value()
        random.seed(user_seed)
        import numpy as np
        np.random.seed(user_seed)
        # ------------------------------------------

        try: 
            s, d = int(self.src_edit.text()), int(self.dst_edit.text()); 
            bw = getattr(self, 'current_bw_demand', 0)
        except: 
            return

        w = tuple(sl.value()/100 for sl in self.sliders)
        key = ["GA", "RL", "ABC", "SA"][self.algo_combo.currentIndex()]
        
        self.tabs.setCurrentIndex(0); 
        self.btn_run.setText("Hesaplanıyor..."); 
        self.btn_run.setEnabled(False)
        self.path_box.setText("Algoritma çalışıyor, lütfen bekleyin...")
        
        self.worker = RoutingWorker("SINGLE", key, self.manager, s, d, w, bw)
        self.worker.finished_single.connect(self.on_single_done); 
        self.worker.error.connect(self.on_error); 
        self.worker.start()
    def on_single_done(self, path, cost, metrics):
        self.btn_run.setText("HESAPLA VE ÇİZ"); self.btn_run.setEnabled(True)
        try: s, d = int(self.src_edit.text()), int(self.dst_edit.text())
        except: s, d = None, None
        self.canvas_net.draw_graph(self.G, path, s, d)
        self.algo_pill.setText(self.algo_combo.currentText())
        path_str = " -> ".join(map(str, path)) if path else "YOL BULUNAMADI"
        self.lbl_path_nodes.setText(path_str); self.lbl_hops.setText(f"({len(path)-1} sıçrama)" if path else "(-)")
        
        # --- Temiz maliyeti göster ---
        raw_cost = metrics.get('total_cost', cost)
        display_cost = clean_cost_value(raw_cost)

        self.val_delay.setText(f"{metrics.get('delay',0):.2f} ms")
        self.val_rel.setText(f"{metrics.get('rel_prob',0):.4f}")
        self.val_res.setText(f"{metrics.get('res_cost',0):.2f}")
        self.val_total.setText(f"{display_cost:.4f}")

        self.lbl_time_val.setText(f"{metrics.get('time_ms',0):.2f} ms")
        log = f"ALGORİTMA: {self.algo_combo.currentText()}\nTalep: {getattr(self, 'current_bw_demand', 0)} Mbps\nDurum: {'BAŞARILI' if path else 'BAŞARISIZ'}\nMaliyet: {display_cost:.4f}\nRota: {path_str}"
        self.path_box.setPlainText(log)

    def run_compare(self):
        try: s, d = int(self.src_edit.text()), int(self.dst_edit.text()); bw = getattr(self, 'current_bw_demand', 0)
        except: return
        w = tuple(sl.value()/100 for sl in self.sliders)
        self.tabs.setCurrentIndex(1); self.btn_compare.setText("Kıyaslanıyor..."); self.btn_compare.setEnabled(False)
        self.worker = RoutingWorker("COMPARE", "ALL", self.manager, s, d, w, bw)
        self.worker.finished_batch.connect(self.on_batch_done); self.worker.error.connect(self.on_error); self.worker.start()

    def on_batch_done(self, results):
        self.last_results = results
        self.btn_compare.setText("TÜMÜNÜ KIYASLA"); self.btn_compare.setEnabled(True)
        succ = {k: v for k, v in results.items() if v.get('success', False)}
        best = min(succ, key=lambda k: succ[k].get("total_cost", float('inf'))) if succ else "-"
        html = f"<div><h2 style='color:#60a5fa;'>KIYASLAMA BİTTİ</h2><p><b>En İyi:</b> <span style='color:#22c55e; font-size:18px;'>{best}</span></p>"
        ordered = sorted(results.items(), key=lambda kv: kv[1].get("total_cost", float("inf")))
        for algo, m in ordered:
            # ---  Kıyaslama Raporunda Temiz Maliyet ---
            raw_c = m.get('total_cost', 0)
            disp_c = clean_cost_value(raw_c)

            status_html = f"<span style='color:#cbd5f5;'>Gecikme: {m.get('delay',0):.2f} | Güven: {m.get('rel_prob',0):.4f}</span><br><span style='color:#cbd5f5;'>Maliyet: <b>{disp_c:.4f}</b></span>" if m.get('success') else "<span style='color:#ef4444; font-weight:bold;'>BAŞARISIZ</span>"
            color = "#93c5fd" if m.get('success') else "#ef4444"
            html += f"<div style='margin-top:10px; border-bottom:1px solid #374151; padding-bottom:5px;'><b style='color:{color};'>▶ {algo}</b><br>{status_html}</div>"
        html += "</div>"
        self.path_box.setHtml(html); self.canvas_perf.update_charts(results)

    def on_error(self, msg):
        self.btn_run.setText("HESAPLA VE ÇİZ"); self.btn_run.setEnabled(True)
        self.btn_compare.setText("TÜMÜNÜ KIYASLA"); self.btn_compare.setEnabled(True)
        self.path_box.setPlainText(f"HATA OLUŞTU:\n{msg}"); QtWidgets.QMessageBox.critical(self, "Hata", msg)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv); app.setStyle("Fusion")
    app.setStyleSheet(f"""
        QWidget {{ background-color: {THEME['MAIN_BG']}; color: {THEME['TEXT']}; font-family: 'Segoe UI'; }}
        QGroupBox {{ border: 1px solid {THEME['BORDER']}; border-radius: 6px; margin-top: 10px; padding: 10px; font-weight: bold; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {THEME['BUTTON']}; }}
        QPushButton {{ background-color: {THEME['BUTTON']}; border: none; border-radius: 5px; padding: 8px; font-weight: bold; color: white; }}
        QPushButton:hover {{ background-color: {THEME['BUTTON_HOVER']}; }}
        QPushButton#compareBtn {{ background-color: {THEME['BTN_COMPARE']}; }}
        QPushButton#compareBtn:hover {{ background-color: #059669; }}
        
        /* BURAYA QSpinBox EKLEDİK: Böylece seed kutusu da diğerleri gibi koyu olacak */
        QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{ 
            background-color: #262c33; 
            border: 1px solid {THEME['BORDER']}; 
            border-radius: 4px; 
            padding: 4px; 
            color: white; 
        }}
        
        QFrame#resultCard {{ background-color: {THEME['CARD_BG']}; border: 1px solid {THEME['BORDER']}; border-radius: 8px; }}
        QSlider::groove:horizontal {{ height: 4px; background: {THEME['BORDER']}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; border-radius: 7px; background: {THEME['BUTTON']}; }}
    """)
    win = Window(); win.show(); sys.exit(app.exec_())