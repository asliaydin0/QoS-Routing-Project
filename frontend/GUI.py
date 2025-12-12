import sys
import math
from pathlib import Path

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QCursor

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import networkx as nx


# ==========================================================
# comparison.py dosyasını (proje kökünde) import edebilmek için
# proje kök dizinini sys.path'e ekliyoruz.
# Bu kısmı DOLDURMA / DEĞİŞTİRME, olduğu gibi kalsın.
# ==========================================================
PROJE_KOKU = Path(__file__).resolve().parents[1]
if str(PROJE_KOKU) not in sys.path:
    sys.path.insert(0, str(PROJE_KOKU))

# Backend API (comparison.py içinde olmalı)
from comparison import get_graph_and_demands, run_single


# ==========================================================
# Tema / Renk Paleti
# ==========================================================
TEMA = {
    "ANA_BG": "#111828",
    "KART_BG": "#1e293b",
    "GRAFIK_BG": "#111828",
    "CIZGI": "#3c4654",
    "YAZI": "#f1f2f6",
    "BUTON": "#7b2cff",
    "BUTON_HOVER": "#6300A5",
    "NODE": "#00d0ff",
    "PATH": "#921717",
}


# ==========================================================
# Worker Thread: sadece backend run_single() çağırır
# (Frontend burada algoritma yazmaz!)
# ==========================================================
class YonlendirmeIsci(QThread):
    bitti = pyqtSignal(list, float, dict)
    hata = pyqtSignal(str)

    def __init__(self, algo_key: str, G, kaynak: int, hedef: int, talep_mbps: float):
        super().__init__()
        self.algo_key = algo_key
        self.G = G
        self.kaynak = kaynak
        self.hedef = hedef
        self.talep = talep_mbps

    def run(self):
        try:
            yol, maliyet, metrik = run_single(
                self.algo_key, self.G, self.kaynak, self.hedef, self.talep
            )
            self.bitti.emit(yol or [], maliyet, metrik or {})
        except Exception as e:
            self.hata.emit(str(e))


# ==========================================================
# Grafik Tuvali (NetworkX çizimi)
# ==========================================================
class GrafikTuval(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = plt.subplots()
        super().__init__(self.fig)
        self.setParent(parent)

        self.fig.patch.set_facecolor(TEMA["GRAFIK_BG"])
        self.ax.set_facecolor(TEMA["GRAFIK_BG"])
        self.pos = {}

        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.updateGeometry()

    def graf_ciz(self, G, yol=None):
        self.ax.clear()
        self.ax.set_facecolor(TEMA["GRAFIK_BG"])

        try:
            self.pos = nx.spring_layout(G, seed=42, iterations=30)
        except Exception:
            self.pos = nx.random_layout(G, seed=42)

        nx.draw_networkx_edges(G, self.pos, edge_color="#404855", width=0.25, alpha=0.45, ax=self.ax)
        nx.draw_networkx_nodes(G, self.pos, node_size=26, node_color=TEMA["NODE"], ax=self.ax)

        if yol and len(yol) > 1:
            yol_kenarlar = list(zip(yol[:-1], yol[1:]))
            nx.draw_networkx_edges(G, self.pos, edgelist=yol_kenarlar, width=2.5, edge_color=TEMA["PATH"], ax=self.ax)
            nx.draw_networkx_nodes(G, self.pos, nodelist=yol, node_color=TEMA["PATH"], node_size=60, ax=self.ax)
            etiketler = {n: str(n) for n in yol}
            nx.draw_networkx_labels(G, self.pos, etiketler, font_size=8, font_color="white", font_weight="bold", ax=self.ax)

        self.ax.set_axis_off()
        self.fig.tight_layout()
        self.draw()


def kart_olustur(baslik, baslik_renk="#ffffff", buyuk=False):
    frame = QtWidgets.QFrame()
    frame.setObjectName("sonucKart")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)

    lbl_baslik = QtWidgets.QLabel(baslik)
    lbl_baslik.setStyleSheet(f"font-size: 11px; color: {baslik_renk}; font-weight: 600;")
    layout.addWidget(lbl_baslik)

    lbl_deger = QtWidgets.QLabel("-")
    lbl_deger.setStyleSheet("font-size: 18px; font-weight: 700;" if buyuk else "font-size: 15px; font-weight: 600;")
    layout.addWidget(lbl_deger)

    layout.addStretch()
    return frame, lbl_deger


# ==========================================================
# Ana Pencere (Frontend Only)
# ==========================================================
class Pencere(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QoS Yönlendirme Simülatörü (Sadece Frontend)")
        self.resize(1450, 850)

        # Graf ve demand verisini backend'den al
        G, df_demand = get_graph_and_demands()
        if G is None or df_demand is None:
            raise RuntimeError("Veri yüklenemedi! 'datalar' klasörü ve CSV dosyalarını kontrol edin.")

        self.G = G
        self.df_demand = df_demand

        self.arayuz_kur()
        self.canvas.graf_ciz(self.G)

    def arayuz_kur(self):
        ana = QtWidgets.QHBoxLayout(self)
        ana.setContentsMargins(10, 10, 10, 10)
        ana.setSpacing(15)

        # ---------------- SOL PANEL ----------------
        sol = QtWidgets.QVBoxLayout()
        sol.setSpacing(15)

        algo_group = QtWidgets.QGroupBox("Algoritma Seçimi")
        algo_layout = QtWidgets.QVBoxLayout()

        self.algo_combo = QtWidgets.QComboBox()
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
        sol.addWidget(algo_group)

        senaryo_group = QtWidgets.QGroupBox("Senaryo (DemandData)")
        senaryo_layout = QtWidgets.QFormLayout()

        self.senaryo_edit = QtWidgets.QLineEdit("1")
        self.senaryo_edit.setMinimumHeight(30)
        senaryo_layout.addRow("Senaryo ID:", self.senaryo_edit)

        self.lbl_senaryo_bilgi = QtWidgets.QLabel("—")
        self.lbl_senaryo_bilgi.setWordWrap(True)
        self.lbl_senaryo_bilgi.setStyleSheet("font-size: 12px; color: #a5b1c2;")
        senaryo_layout.addRow("Bilgi:", self.lbl_senaryo_bilgi)

        senaryo_group.setLayout(senaryo_layout)
        sol.addWidget(senaryo_group)

        self.run_btn = QtWidgets.QPushButton("ÇALIŞTIR")
        self.run_btn.setMinimumHeight(50)
        self.run_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.calistir)
        sol.addWidget(self.run_btn)

        sol.addStretch()

        sol_w = QtWidgets.QWidget()
        sol_w.setLayout(sol)
        sol_w.setFixedWidth(360)
        ana.addWidget(sol_w)

        # ---------------- ORTA PANEL ----------------
        orta = QtWidgets.QVBoxLayout()

        baslik = QtWidgets.QLabel("Ağ Topolojisi (Graph)")
        baslik.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
        orta.addWidget(baslik)

        self.canvas = GrafikTuval(self)
        self.canvas.mpl_connect("motion_notify_event", self.mouse_hareket)
        orta.addWidget(self.canvas)

        ana.addLayout(orta, 1)

        # ---------------- SAĞ PANEL ----------------
        sag = QtWidgets.QVBoxLayout()
        sag.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        lbl_sonuc = QtWidgets.QLabel("Sonuçlar")
        lbl_sonuc.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(lbl_sonuc)

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
        header.addStretch()
        header.addWidget(self.algo_pill)
        sag.addLayout(header)

        self.yol_frame = QtWidgets.QFrame()
        self.yol_frame.setObjectName("sonucKart")
        yol_layout = QtWidgets.QVBoxLayout(self.yol_frame)

        top_row = QtWidgets.QHBoxLayout()
        lbl_yol = QtWidgets.QLabel("Bulunan Yol")
        lbl_yol.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.lbl_hop = QtWidgets.QLabel("(0 sıçrama)")
        self.lbl_hop.setStyleSheet("font-size: 11px; color: #a5b1c2;")
        top_row.addWidget(lbl_yol)
        top_row.addStretch()
        top_row.addWidget(self.lbl_hop)
        yol_layout.addLayout(top_row)

        self.lbl_yol_dugumler = QtWidgets.QLabel("-")
        self.lbl_yol_dugumler.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEMA['PATH']};")
        self.lbl_yol_dugumler.setWordWrap(True)
        yol_layout.addWidget(self.lbl_yol_dugumler)

        sag.addWidget(self.yol_frame)

        c1, self.val_maliyet = kart_olustur("Toplam Maliyet", "#a29bfe", buyuk=True)
        c2, self.val_sure = kart_olustur("Süre (ms)", "#4da3ff", buyuk=True)
        c3, self.val_uzunluk = kart_olustur("Yol Uzunluğu", "#55efc4", buyuk=True)

        sag.addWidget(c1)
        sag.addWidget(c2)
        sag.addWidget(c3)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Log...")
        sag.addWidget(self.log_box)

        sag_w = QtWidgets.QWidget()
        sag_w.setLayout(sag)
        sag_w.setFixedWidth(280)
        ana.addWidget(sag_w)

    def _algo_key(self) -> str:
        t = self.algo_combo.currentText()
        if "(GA)" in t:
            return "GA"
        if "(RL)" in t:
            return "Q"
        if "(ABC)" in t:
            return "ABC"
        return "SA"

    def calistir(self):
        try:
            sid = int(self.senaryo_edit.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Hata", "Lütfen geçerli bir Senaryo ID girin.")
            return

        if sid < 1 or sid > len(self.df_demand):
            QtWidgets.QMessageBox.warning(self, "Hata", f"Senaryo ID 1 ile {len(self.df_demand)} arasında olmalı!")
            return

        row = self.df_demand.iloc[sid - 1]

        # DemandData kolonları: src, dst, demand_mbps (comparison.py böyle okuyor)
        try:
            src = int(row["src"])
            dst = int(row["dst"])
            bw = float(row["demand_mbps"])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Hata", f"DemandData kolonları beklenenden farklı: {e}")
            return

        self.lbl_senaryo_bilgi.setText(f"{src} -> {dst} | Talep: {bw} Mbps")

        algo_key = self._algo_key()
        algo_name = self.algo_combo.currentText()

        self.run_btn.setText("Çalışıyor...")
        self.run_btn.setEnabled(False)
        self.algo_pill.setText(algo_name)

        self.worker = YonlendirmeIsci(algo_key, self.G, src, dst, bw)
        self.worker.bitti.connect(self.bitti)
        self.worker.hata.connect(self.hata)
        self.worker.start()

    def bitti(self, yol, maliyet, metrik):
        self.run_btn.setText("ÇALIŞTIR")
        self.run_btn.setEnabled(True)

        if yol:
            self.canvas.graf_ciz(self.G, yol)
            yol_str = " -> ".join(map(str, yol))
            self.lbl_yol_dugumler.setText(yol_str)
            self.lbl_hop.setText(f"({len(yol)-1} sıçrama)")
        else:
            self.canvas.graf_ciz(self.G, None)
            self.lbl_yol_dugumler.setText("-")
            self.lbl_hop.setText("(0 sıçrama)")

        toplam_maliyet = metrik.get("total_cost", maliyet)
        sure_ms = metrik.get("time_ms", 0.0)
        yol_uzunluk = metrik.get("path_len", len(yol) if yol else 0)

        self.val_maliyet.setText(f"{toplam_maliyet:.4f}" if yol else "---")
        self.val_sure.setText(f"{sure_ms:.2f}")
        self.val_uzunluk.setText(str(yol_uzunluk))

        self.log_box.setPlainText(
            f"Algoritma: {metrik.get('algo','-')}\n"
            f"Maliyet: {toplam_maliyet}\n"
            f"Süre(ms): {sure_ms:.2f}\n"
            f"Yol: {(' -> '.join(map(str, yol)) if yol else '-')}"
        )

    def hata(self, msg):
        self.run_btn.setText("ÇALIŞTIR")
        self.run_btn.setEnabled(True)
        self.algo_pill.setText("Hata")
        QtWidgets.QMessageBox.critical(self, "Hata", msg)

    def mouse_hareket(self, event):
        if event.inaxes != self.canvas.ax:
            return
        if event.xdata is None or event.ydata is None:
            return

        en_yakin = None
        min_dist = float("inf")
        limit = 0.05

        for node, (x, y) in self.canvas.pos.items():
            dist = math.sqrt((event.xdata - x) ** 2 + (event.ydata - y) ** 2)
            if dist < limit and dist < min_dist:
                min_dist = dist
                en_yakin = node

        if en_yakin is not None:
            props = self.G.nodes[en_yakin]
            bilgi = (
                f"<b>DÜĞÜM: {en_yakin}</b><hr>"
                f"proc_delay: {props.get('proc_delay', '-') }<br>"
                f"reliability: {props.get('reliability', '-')}"
            )
            QtWidgets.QToolTip.showText(QCursor.pos(), bilgi)
        else:
            QtWidgets.QToolTip.hideText()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    app.setStyleSheet(f"""
        QWidget {{ background-color: {TEMA['ANA_BG']}; color: {TEMA['YAZI']}; font-family: 'Segoe UI', sans-serif; }}
        QGroupBox {{ border: 1px solid {TEMA['CIZGI']}; border-radius: 6px; margin-top: 10px; padding: 10px; font-weight: bold; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
        QPushButton {{ background-color: {TEMA['BUTON']}; border: none; border-radius: 5px; padding: 8px; font-weight: bold; color: white; }}
        QPushButton:hover {{ background-color: {TEMA['BUTON_HOVER']}; }}
        QPushButton:disabled {{ background-color: #555; color: #aaa; }}
        QLineEdit, QComboBox, QPlainTextEdit {{ background-color: #262c33; border: 1px solid {TEMA['CIZGI']}; border-radius: 4px; padding: 4px; color: white; }}
        QFrame#sonucKart {{ background-color: {TEMA['KART_BG']}; border: 1px solid {TEMA['CIZGI']}; border-radius: 8px; }}
    """)

    win = Pencere()
    win.show()
    sys.exit(app.exec_())
