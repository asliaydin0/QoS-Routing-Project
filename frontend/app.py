import sys
import time
import math
import random
import itertools

# PyQt5 Kütüphaneleri
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QCursor

# Grafik Kütüphaneleri
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import networkx as nx

# Yüksek Çözünürlük Ayarı
if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

# RENK PALETİ
THEME = {
    "MAIN_BG": "#111828",       # Ana Pencere Arka Planı 
    "CARD_BG": "#1e293b",       # Kartların Arka Planı 
    "GRAPH_BG": "#111828",      # Grafik Alanı Arka Planı
    "BORDER": "#3c4654",        # Çerçeve Rengi
    "TEXT": "#f1f2f6",          # Yazı Rengi
    "BUTTON": "#7b2cff",        # Buton Rengi 
    "BUTTON_HOVER": "#6300A5",  # Buton Üzerine Gelince
    "NODE_COLOR": "#00d0ff",    # Düğüm Rengi 
    "PATH_COLOR": "#921717"     # Seçilen Yol Rengi 
}

# ==========================================================
#  BÖLÜM 1: BACKEND (Algoritmalar)
# ==========================================================

def calculate_delay(path, G):
    total_delay = 0
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        total_delay += G[u][v].get('delay', 5)
    for node in path[1:-1]:
        total_delay += G.nodes[node].get('processing_delay', 1)
    return total_delay

def calculate_reliability_cost(path, G):
    total_cost = 0
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        r = G[u][v].get('reliability', 0.99)
        val = -math.log(r) if r > 0 else 100
        total_cost += val
    for node in path[1:-1]:
        r = G.nodes[node].get('reliability', 0.99)
        val = -math.log(r) if r > 0 else 100
        total_cost += val
    return total_cost

def calculate_resource_cost(path, G):
    total_res = 0
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        bw = G[u][v].get('bandwidth', 100)
        total_res += (1000.0 / bw) 
    return total_res

def calculate_total_cost(path, G, w1, w2, w3):
    d = calculate_delay(path, G)
    r = calculate_reliability_cost(path, G)
    res = calculate_resource_cost(path, G)
    return (w1 * d) + (w2 * r * 100) + (w3 * res)

class RoutingWorker(QThread):
    finished = pyqtSignal(list, float, dict)
    error = pyqtSignal(str)

    def __init__(self, G, src, dst, weights):
        super().__init__()
        self.G = G
        self.src = src
        self.dst = dst
        self.weights = weights

    def run(self):
        try:
            start_time = time.time()
            population = []
            try:
                path_gen = nx.shortest_simple_paths(self.G, self.src, self.dst)
                population = list(itertools.islice(path_gen, 40))
            except nx.NetworkXNoPath:
                self.error.emit("Kaynak ve Hedef arasında yol yok!")
                return
            except Exception:
                if nx.has_path(self.G, self.src, self.dst):
                    population = [nx.shortest_path(self.G, self.src, self.dst)]
                else:
                    self.error.emit("Yol bulunamadı.")
                    return

            if not population:
                self.error.emit("Uygun yol bulunamadı.")
                return

            generations = 20
            for gen in range(generations):
                pop_costs = [(p, calculate_total_cost(p, self.G, *self.weights)) for p in population]
                pop_costs.sort(key=lambda x: x[1])
                population = [x[0] for x in pop_costs[:len(population)//2]]
                while len(population) < 40:
                    population.append(population[0])

            best_path = population[0]
            best_cost = calculate_total_cost(best_path, self.G, *self.weights)

            metrics = {
                "delay": calculate_delay(best_path, self.G),
                "rel_cost": calculate_reliability_cost(best_path, self.G),
                "res_cost": calculate_resource_cost(best_path, self.G),
                "total_cost": best_cost,
                "time_ms": (time.time() - start_time) * 1000
            }
            time.sleep(0.5) 
            self.finished.emit(best_path, best_cost, metrics)

        except Exception as e:
            self.error.emit(str(e))


# ==========================================================
#  BÖLÜM 2: FRONTEND
# ==========================================================

class GraphCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = plt.subplots()
        super().__init__(self.fig)
        self.setParent(parent)

        # Temadan renkleri alıyoruz
        self.fig.patch.set_facecolor(THEME["GRAPH_BG"])
        self.ax.set_facecolor(THEME["GRAPH_BG"])
        
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.updateGeometry()
        self.pos = {}

    def draw_graph(self, G, path=None):
        self.ax.clear()
        self.ax.set_facecolor(THEME["GRAPH_BG"])

        try:
            self.pos = nx.spring_layout(G, seed=42, iterations=30)
        except:
            self.pos = nx.random_layout(G, seed=42)

        # Görsel Ayarlar
        nx.draw_networkx_edges(
            G, self.pos,
            edge_color="#404855",
            width=0.1,       
            alpha=0.5,
            ax=self.ax
        )
        
        nx.draw_networkx_nodes(
            G, self.pos,
            node_size=30,
            node_color=THEME["NODE_COLOR"], 
            ax=self.ax
        )

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
            
            labels = {node: str(node) for node in path}
            nx.draw_networkx_labels(G, self.pos, labels, font_size=8, font_color="white", font_weight="bold", ax=self.ax)

        self.ax.set_axis_off()
        self.fig.tight_layout()
        self.draw()

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


class Window(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QoS Yönlendirme Simülatörü - BSM307 (Final)")
        self.resize(1450, 850)
        
        self.generate_initial_graph()
        self.build_ui()

    def generate_initial_graph(self):
        print("250 Düğümlü Ağ Oluşturuluyor... Lütfen bekleyin.")
        self.N = 250 
        self.G = nx.erdos_renyi_graph(self.N, 0.4, seed=42)
        
        for u, v in self.G.edges():
            self.G[u][v]['bandwidth'] = random.randint(100, 1000)
            self.G[u][v]['delay'] = random.randint(3, 15)
            self.G[u][v]['reliability'] = round(random.uniform(0.95, 0.999), 4)
        for n in self.G.nodes():
            self.G.nodes[n]['processing_delay'] = round(random.uniform(0.5, 2.0), 2)
            self.G.nodes[n]['reliability'] = round(random.uniform(0.95, 0.999), 4)

    def build_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # SOL PANEL
        sidebar = QtWidgets.QVBoxLayout()
        sidebar.setSpacing(15)

        # Algoritma Seçimi
        algo_group = QtWidgets.QGroupBox("Algoritma Seçimi")
        algo_layout = QtWidgets.QVBoxLayout()
        self.algo_combo = QtWidgets.QComboBox()
        self.algo_combo.addItems(["Genetik Algoritma (GA)", "Karınca Kolonisi (ACO)"])
        self.algo_combo.setMinimumHeight(35)
        algo_layout.addWidget(QtWidgets.QLabel("Yöntem:"))
        algo_layout.addWidget(self.algo_combo)
        algo_group.setLayout(algo_layout)
        sidebar.addWidget(algo_group)

        # Rota Ayarları
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

        # Sliderlar
        weight_group = QtWidgets.QGroupBox("Optimizasyon Ağırlıkları")
        w_layout = QtWidgets.QVBoxLayout()
        w_layout.setSpacing(12)
        
        def add_slider(label, val):
            l = QtWidgets.QVBoxLayout()
            l.setSpacing(2)
            top_row = QtWidgets.QHBoxLayout()
            top_row.addWidget(QtWidgets.QLabel(label))
            v_lbl = QtWidgets.QLabel(str(val))
            v_lbl.setAlignment(QtCore.Qt.AlignRight)
            top_row.addWidget(v_lbl)
            s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            s.setRange(0, 100); s.setValue(val)
            s.valueChanged.connect(lambda v, lb=v_lbl: lb.setText(str(v)))
            l.addLayout(top_row); l.addWidget(s)
            w_layout.addLayout(l)
            return s

        self.delay_slider = add_slider("Gecikme (Delay)", 40)
        self.rel_slider = add_slider("Güvenilirlik (Reliability)", 30)
        self.res_slider = add_slider("Kaynak (Resource)", 30)
        weight_group.setLayout(w_layout)
        sidebar.addWidget(weight_group)

        # Buton
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

        # ORTA PANEL
        center_layout = QtWidgets.QVBoxLayout()
        title_graph = QtWidgets.QLabel(f"Ağ Topolojisi ({self.N} Düğüm)")
        title_graph.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
        center_layout.addWidget(title_graph)

        self.canvas = GraphCanvas(self)
        self.canvas.setStyleSheet("background-color: transparent;")
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
        center_layout.addWidget(self.canvas)
        main_layout.addLayout(center_layout, 1)

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
        grid.setContentsMargins(0,0,0,0)

        c1, self.val_delay = create_card("Toplam Gecikme", "#4da3ff", big=True)
        c2, self.val_rel = create_card("Güvenilirlik", "#55efc4", big=True)
        c3, self.val_res = create_card("Kaynak Maliyeti", "#ffeaa7", big=True)
        c4, self.val_total = create_card("Ağırlıklı Maliyet", "#a29bfe", big=True)

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

        self.path_box = QtWidgets.QPlainTextEdit()
        self.path_box.setReadOnly(True)
        self.path_box.setPlaceholderText("Log kayıtları...")
        right_layout.addWidget(self.path_box)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setFixedWidth(280)
        main_layout.addWidget(right_widget)

        self.canvas.draw_graph(self.G)

    def run_routing(self):
        try:
            src = int(self.src_edit.text())
            dst = int(self.dst_edit.text())
        except ValueError: return

        if src not in self.G.nodes or dst not in self.G.nodes:
             QtWidgets.QMessageBox.warning(self, "Hata", f"Düğüm 0 ile {self.N-1} arasında olmalı!")
             return

        w1 = self.delay_slider.value() / 100
        w2 = self.rel_slider.value() / 100
        w3 = self.res_slider.value() / 100
        
        self.run_button.setText("Hesaplanıyor...")
        self.run_button.setEnabled(False)
        self.algo_pill.setText("Hesaplanıyor...")

        self.worker = RoutingWorker(self.G, src, dst, (w1, w2, w3))
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_finished(self, path, cost, metrics):
        self.run_button.setText("HESAPLA VE ÇİZ")
        self.run_button.setEnabled(True)
        
        self.canvas.draw_graph(self.G, path)
        
        self.val_delay.setText(f"{metrics['delay']:.2f} ms")
        self.val_rel.setText(f"{metrics['rel_cost']:.2f}")
        self.val_res.setText(f"{metrics['res_cost']:.2f}")
        self.val_total.setText(f"{cost:.4f}")
        self.lbl_time_val.setText(f"{metrics['time_ms']:.2f} ms")
        
        path_str = " -> ".join(map(str, path))
        self.lbl_path_nodes.setText(path_str)
        self.lbl_hops.setText(f"({len(path)-1} sıçrama)")
        
        algo_name = self.algo_combo.currentText()
        self.algo_pill.setText(algo_name)
        
        self.path_box.setPlainText(f"Algoritma: {algo_name}\nToplam Maliyet: {cost:.4f}\nYol: {path_str}")

    def on_error(self, msg):
        self.run_button.setText("HESAPLA VE ÇİZ")
        self.run_button.setEnabled(True)
        self.algo_pill.setText("Hata")
        QtWidgets.QMessageBox.critical(self, "Hata", msg)

    # --- TOOLTIP ---
    def on_mouse_move(self, event):
        if event.inaxes != self.canvas.ax: return
        closest_node = None
        min_dist = float('inf')
        search_limit = 0.05 
        
        for node, (x, y) in self.canvas.pos.items():
            dist = math.sqrt((event.xdata - x)**2 + (event.ydata - y)**2)
            if dist < search_limit and dist < min_dist:
                min_dist = dist
                closest_node = node
        
        if closest_node is not None:
            props = self.G.nodes[closest_node]
            info_text = (f"<b>DÜĞÜM ID: {closest_node}</b><hr>"
                         f"İşlem Süresi: {props['processing_delay']} ms<br>"
                         f"Güvenilirlik: {props['reliability']}")
            QtWidgets.QToolTip.showText(QCursor.pos(), info_text)
        else:
            QtWidgets.QToolTip.hideText()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # CSS İLE RENKLERİ UYGULA
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
