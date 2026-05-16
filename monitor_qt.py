"""
monitor_qt.py — Moniteur CPU temps réel (PyQt6)
Supporte : navigation step-by-step, retour arrière, play/pause, slider, vitesse.

Usage :
    from monitor_qt import Monitor

    monitor = Monitor(arch, cpu, reg, ram, cache, disc=disc)
    monitor.attach()   # lance la fenêtre — bloquant jusqu'à fermeture
"""

import sys
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QGroupBox,
    QSplitter, QProgressBar, QPushButton, QFrame, QSlider,
    QSpinBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor


# ══════════════════════════════════════════════
#  PALETTE
# ══════════════════════════════════════════════

BG      = "#0d1117"
BG2     = "#161b22"
BG3     = "#21262d"
BORDER  = "#30363d"
FG      = "#c9d1d9"
FG_DIM  = "#484f58"
CYAN    = "#79c0ff"
GREEN   = "#56d364"
RED     = "#f85149"
YELLOW  = "#e3b341"
MAGENTA = "#d2a8ff"
ORANGE  = "#ffa657"
BLUE    = "#388bfd"

STYLE = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {FG};
}}
QGroupBox {{
    background-color: {BG2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px;
    font-weight: bold;
    font-size: 11px;
    color: {CYAN};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {CYAN};
}}
QTableWidget {{
    background-color: {BG3};
    color: {FG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    gridline-color: {BORDER};
    font-size: 11px;
}}
QTableWidget::item {{ padding: 2px 6px; }}
QHeaderView::section {{
    background-color: {BG2};
    color: {FG_DIM};
    border: 1px solid {BORDER};
    padding: 3px 6px;
    font-size: 10px;
}}
QScrollBar:vertical {{
    background: {BG2}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 4px; min-height: 20px;
}}
QProgressBar {{
    background-color: {BG3};
    border: 1px solid {BORDER};
    border-radius: 3px;
    height: 8px;
}}
QProgressBar::chunk {{ background-color: {GREEN}; border-radius: 3px; }}
QPushButton {{
    background-color: {BG3};
    color: {FG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 14px;
}}
QPushButton:hover   {{ background-color: {BORDER}; }}
QPushButton:pressed {{ background-color: {BG}; }}
QPushButton:disabled {{ color: {FG_DIM}; border-color: {BG3}; }}
QSlider::groove:horizontal {{
    background: {BG3}; height: 4px; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {CYAN};
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{ background: {BLUE}; border-radius: 2px; }}
QSpinBox {{
    background-color: {BG3};
    color: {FG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 11px;
}}
QLabel {{ background-color: transparent; }}
QSplitter::handle {{ background-color: {BORDER}; }}
"""


# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════

def _mono(size=11):
    f = QFont("JetBrains Mono", size)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f

def _label(text, color=FG, size=11, bold=False):
    lbl = QLabel(text)
    lbl.setFont(_mono(size))
    lbl.setStyleSheet(f"color:{color}; {'font-weight:bold;' if bold else ''}")
    return lbl

def _item(text, color=FG, bg=None):
    it = QTableWidgetItem(text)
    it.setForeground(QColor(color))
    it.setFont(_mono(10))
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if bg:
        it.setBackground(QColor(bg))
    return it

def _sep():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{BORDER};")
    return f

def get_instruction_name(opcode: int) -> str:
    instructions_map = {
            0x00: "NOP",
            0x10: "MOV (Reg)",
            0x11: "MOV (Imm)",
            0x12: "LOAD (RAM)",
            0x13: "STORE",
            0x14: "LOAD (Ind)",
            0x15: "MOV (Idx)",
            0x20: "ADD",
            0x21: "ADDI",
            0x22: "SUB",
            0x26: "MUL",
            0x27: "XOR",
            0x28: "CMP (Reg)",
            0x29: "CMP (Imm)",
            0x30: "AND",
            0x31: "OR",
            0x32: "ANDI",
            0x33: "NOT",
            0x34: "SHL",
            0x35: "SHR",
            0x40: "JMP",
            0x41: "JZ",
            0x42: "JNZ",
            0x43: "JC",
            0x44: "JNC",
            0x45: "JN",
            0x46: "JNN",
            0x47: "JO",
            0x48: "JNO",
            0x49: "CALL",
            0x4A: "RET",
            0x50: "PUSH",
            0x51: "POP",
            0x60: "IN (Reg)",
            0x61: "OUT (Reg)",
            0x62: "OUT (RAM)",
            0x63: "IN (RAM)",
            0x64: "OUT (Cache)",
            0x65: "IN (Cache)",
            0xFF: "HLT"
        }
    return instructions_map.get(opcode, f"UNKNOWN ({hex(opcode)})")

# ══════════════════════════════════════════════
#  SNAPSHOT  (capture complète de l'état)
# ══════════════════════════════════════════════

class Snapshot:
    def __init__(self, reg, ram, cache, disc, step: int):
        self.step = step
        # registres
        self.R     = list(reg.R)
        self.PC    = reg.PC
        self.SP    = reg.SP
        self.IR    = reg.IR
        self.FLAGS = reg.FLAGS
        # RAM
        self.ram_mem = bytes(ram.memory)
        # cache
        self.cache_data  = [bytes(line) for line in cache.data]
        self.cache_tags  = list(cache.tags)
        self.cache_valid = list(cache.valid)
        # disc
        if disc is not None:
            self.disc_mem     = bytes(disc.memory)
            self.disc_pointer = disc.pointer
        else:
            self.disc_mem = self.disc_pointer = None

    def restore(self, reg, ram, cache, disc):
        reg.R[:]  = self.R
        reg.PC    = self.PC
        reg.SP    = self.SP
        reg.IR    = self.IR
        reg.FLAGS = self.FLAGS
        ram.memory[:] = self.ram_mem
        for i, line in enumerate(self.cache_data):
            cache.data[i][:] = line
        cache.tags[:]  = list(self.cache_tags)
        cache.valid[:] = list(self.cache_valid)
        if disc is not None and self.disc_mem is not None:
            disc.memory[:] = self.disc_mem
            disc.pointer   = self.disc_pointer


# ══════════════════════════════════════════════
#  PANNEAU REGISTRES
# ══════════════════════════════════════════════

class _RegistersPanel(QGroupBox):
    def __init__(self, arch):
        super().__init__("REGISTRES")
        self.arch   = arch
        self._bars  = []
        self._vals  = []
        self._prev  = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(4)
        for i in range(self.arch.registers_count):
            row = QHBoxLayout(); row.setSpacing(6)
            lbl = _label(f"R{i}", CYAN, bold=True); lbl.setFixedWidth(24)
            val = _label("  0  0x00", YELLOW);       val.setFixedWidth(110)
            bar = QProgressBar()
            bar.setRange(0, self.arch.data_mask)
            bar.setValue(0); bar.setFixedHeight(8); bar.setTextVisible(False)
            row.addWidget(lbl); row.addWidget(val); row.addWidget(bar)
            self._bars.append(bar); self._vals.append(val)
            lay.addLayout(row)
        lay.addWidget(_sep())
        self._specials = {}
        for name, color in [("PC", MAGENTA), ("SP", MAGENTA), ("IR", ORANGE), ("FL", FG_DIM)]:
            row = QHBoxLayout(); row.setSpacing(6)
            lbl = _label(name, color, bold=True); lbl.setFixedWidth(24)
            val = _label("—", FG)
            self._specials[name] = val
            row.addWidget(lbl); row.addWidget(val)
            lay.addLayout(row)

    def refresh(self, snap: Snapshot):
        for i in range(self.arch.registers_count):
            v       = snap.R[i]
            changed = self._prev is not None and self._prev[i] != v
            self._vals[i].setText(f"{v:>3}  {v:#04x}")
            self._vals[i].setStyleSheet(f"color:{''+ORANGE if changed else YELLOW};")
            self._bars[i].setValue(v)
        self._prev = list(snap.R)
        self._specials["PC"].setText(f"{snap.PC:#06x}  ({snap.PC})")
        self._specials["SP"].setText(f"{snap.SP:#06x}  ({snap.SP})")
        self._specials["IR"].setText(f"{snap.IR:#04x}")
        self._specials["FL"].setText(f"{snap.FLAGS:04b}b  ({snap.FLAGS})")


# ══════════════════════════════════════════════
#  PANNEAU FLAGS
# ══════════════════════════════════════════════

class _FlagsPanel(QGroupBox):
    _DEFS = [(0,"Z","Zero"),(1,"C","Carry"),(2,"N","Negative"),(3,"O","Overflow")]

    def __init__(self):
        super().__init__("FLAGS")
        self._leds = {}
        lay = QHBoxLayout(self); lay.setSpacing(16)
        for bit, short, name in self._DEFS:
            col = QVBoxLayout(); col.setAlignment(Qt.AlignmentFlag.AlignCenter)
            led = _label("●", RED, size=18, bold=True)
            led.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(_label(short, FG, bold=True))
            col.addWidget(led)
            col.addWidget(_label(name, FG_DIM, size=9))
            self._leds[bit] = led
            lay.addLayout(col)

    def refresh(self, snap: Snapshot):
        for bit, led in self._leds.items():
            active = (snap.FLAGS >> bit) & 1
            led.setStyleSheet(f"color:{''+GREEN if active else RED}; background:transparent;")


# ══════════════════════════════════════════════
#  PANNEAU MÉMOIRE GÉNÉRIQUE
# ══════════════════════════════════════════════

class _MemoryPanel(QGroupBox):
    def __init__(self, title, size, cols=16, has_pointer=False):
        super().__init__(title)
        self.size = size; self.cols = cols
        self._prev = None
        lay = QVBoxLayout(self); lay.setContentsMargins(4, 12, 4, 4)
        self._ptr_lbl = _label("", FG_DIM, size=10)
        if has_pointer:
            lay.addWidget(self._ptr_lbl)
        rows = (size + cols - 1) // cols
        self._table = QTableWidget(rows, cols)
        self._table.setFont(_mono(10))
        self._table.horizontalHeader().setDefaultSectionSize(26)
        self._table.verticalHeader().setDefaultSectionSize(16)
        self._table.setHorizontalHeaderLabels([f"{i:02x}" for i in range(cols)])
        self._table.setVerticalHeaderLabels([f"{r*cols:#05x}" for r in range(rows)])
        lay.addWidget(self._table)

    def refresh(self, mem_bytes: bytes, pointer=None):
        if pointer is not None:
            self._ptr_lbl.setText(f"ptr → {pointer:#06x}  ({pointer})")
        for addr in range(self.size):
            row, col = addr // self.cols, addr % self.cols
            val     = mem_bytes[addr]
            changed = self._prev is not None and self._prev[addr] != val
            if addr == pointer:
                it = _item(f"{val:02x}", MAGENTA, BG2)
            elif changed:
                it = _item(f"{val:02x}", ORANGE)
            elif val:
                it = _item(f"{val:02x}", GREEN)
            else:
                it = _item("··", FG_DIM)
            self._table.setItem(row, col, it)
        self._prev = mem_bytes


# ══════════════════════════════════════════════
#  PANNEAU CACHE
# ══════════════════════════════════════════════

class _CachePanel(QGroupBox):
    def __init__(self, cache_size):
        super().__init__("CACHE")
        lay = QVBoxLayout(self); lay.setContentsMargins(4, 12, 4, 4)
        self._table = QTableWidget(cache_size, 4)
        self._table.setFont(_mono(10))
        self._table.setHorizontalHeaderLabels(["idx","V","tag","data"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(16)
        lay.addWidget(self._table)

    def refresh(self, snap: Snapshot):
        for i, (valid, tag, data) in enumerate(
            zip(snap.cache_valid, snap.cache_tags, snap.cache_data)
        ):
            self._table.setItem(i, 0, _item(str(i), FG_DIM))
            self._table.setItem(i, 1, _item("✓" if valid else "✗", GREEN if valid else RED))
            self._table.setItem(i, 2, _item(f"{tag:#06x}" if tag >= 0 else "----", YELLOW))
            ds = " ".join(f"{b:02x}" if b else "··" for b in data)
            self._table.setItem(i, 3, _item(ds, FG if any(data) else FG_DIM))


# ══════════════════════════════════════════════
#  BARRE DE NAVIGATION
# ══════════════════════════════════════════════

class _NavBar(QWidget):
    sig_first = pyqtSignal()
    sig_prev  = pyqtSignal()
    sig_next  = pyqtSignal()
    sig_last  = pyqtSignal()
    sig_play  = pyqtSignal(bool)
    sig_seek  = pyqtSignal(int)
    sig_speed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(56)
        self.setStyleSheet(f"background-color:{BG2}; border-top:1px solid {BORDER};")
        self._playing = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4); lay.setSpacing(4)

        self._btn_first = QPushButton("⏮"); self._btn_first.setFixedWidth(38) # Emoji : "⏮"
        self._btn_prev  = QPushButton("|◀"); self._btn_prev.setFixedWidth(38) # Emoji : "|◀"
        self._btn_play  = QPushButton("▶"); self._btn_play.setFixedWidth(38) # Emoji : "▶"
        self._btn_next  = QPushButton("▶|");self._btn_next.setFixedWidth(38) # Emoji : "▶|"
        self._btn_last  = QPushButton("⏭"); self._btn_last.setFixedWidth(38) # Emoji : "⏭"

        for b in [self._btn_first, self._btn_prev, self._btn_play,
                  self._btn_next, self._btn_last]:
            lay.addWidget(b)

        lay.addSpacing(8)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        lay.addWidget(self._slider, stretch=3)

        self._lbl_pos = _label("0 / 0", FG_DIM, size=10)
        self._lbl_pos.setFixedWidth(80)
        lay.addWidget(self._lbl_pos)

        lay.addWidget(_label("  vitesse:", FG_DIM, size=10))
        self._spin = QSpinBox()
        self._spin.setRange(1, 2000); self._spin.setValue(200)
        self._spin.setSuffix(" ms");  self._spin.setFixedWidth(80)
        lay.addWidget(self._spin)

        self._btn_first.clicked.connect(self.sig_first)
        self._btn_prev.clicked.connect(self.sig_prev)
        self._btn_next.clicked.connect(self.sig_next)
        self._btn_last.clicked.connect(self.sig_last)
        self._btn_play.clicked.connect(self._toggle)
        self._slider.valueChanged.connect(self.sig_seek)
        self._spin.valueChanged.connect(self.sig_speed)

    def _toggle(self):
        self._playing = not self._playing
        self._btn_play.setText("⏸" if self._playing else "▶")
        self.sig_play.emit(self._playing)

    def set_playing(self, val: bool):
        self._playing = val
        self._btn_play.setText("⏸" if val else "▶")

    def update_range(self, max_idx: int, cur_idx: int):
        self._slider.blockSignals(True)
        self._slider.setRange(0, max(0, max_idx))
        self._slider.setValue(cur_idx)
        self._slider.blockSignals(False)
        self._lbl_pos.setText(f"{cur_idx} / {max_idx}")

    def set_buttons_enabled(self, has_prev: bool, has_next: bool, cpu_running: bool):
        self._btn_first.setEnabled(has_prev)
        self._btn_prev.setEnabled(has_prev)
        self._btn_next.setEnabled(has_next or cpu_running)
        self._btn_last.setEnabled(has_next or cpu_running)


# ══════════════════════════════════════════════
#  BARRE D'ÉTAT
# ══════════════════════════════════════════════

class _StatusBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(24)
        self.setStyleSheet(f"background-color:{BG2}; border-top:1px solid {BORDER};")
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 0, 12, 0)
        self._lbl_step  = _label("step: 0",    CYAN,   size=10)
        self._lbl_hist  = _label("hist: 0",    FG_DIM, size=10)
        self._lbl_state = _label("● running",  GREEN,  size=10)
        lay.addWidget(self._lbl_step)
        lay.addStretch()
        lay.addWidget(self._lbl_hist)
        lay.addStretch()
        lay.addWidget(self._lbl_state)

    def refresh(self, cur_idx: int, hist_len: int, cpu_running: bool, at_live: bool):
        self._lbl_step.setText(f"step: {cur_idx}")
        replay = not at_live
        self._lbl_hist.setText(f"hist: {hist_len}{'  (replay)' if replay else ''}")
        if not cpu_running:
            self._lbl_state.setText("■ halted")
            self._lbl_state.setStyleSheet(f"color:{RED}; background:transparent;")
        elif replay:
            self._lbl_state.setText("◀ replay")
            self._lbl_state.setStyleSheet(f"color:{YELLOW}; background:transparent;")
        else:
            self._lbl_state.setText("● live")
            self._lbl_state.setStyleSheet(f"color:{GREEN}; background:transparent;")


# ==============================================
#  SIGNAUX INTER-THREAD
# ==============================================

class _Signals(QObject):
    new_snapshot = pyqtSignal()


# ==============================================
#  FENÊTRE PRINCIPALE
# ==============================================

class _MonitorWindow(QMainWindow):
    def __init__(self, arch, reg, ram, cache, disc):
        super().__init__()
        self.setWindowTitle("CPU Monitor")
        self.setStyleSheet(STYLE)
        self.resize(1280, 860)
        self._build(arch, ram, cache, disc)

    def _build(self, arch, ram, cache, disc):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 0); root.setSpacing(6)

        title = _label("CPU MONITOR", CYAN, size=14, bold=True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        
        self.instruction_label = _label("Instruction (IR) : IDLE", YELLOW, size=13, bold=True)
        self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instruction_label.setStyleSheet(f"background-color:{BG2}; border:1px solid {BORDER}; border-radius:4px; padding:6px;")
        root.addWidget(self.instruction_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # gauche
        left = QWidget(); ll = QVBoxLayout(left); ll.setSpacing(6)
        self.reg_panel  = _RegistersPanel(arch)
        self.flag_panel = _FlagsPanel()
        ll.addWidget(self.reg_panel); ll.addWidget(self.flag_panel); ll.addStretch()
        splitter.addWidget(left)

        # droite
        right = QWidget(); rl = QVBoxLayout(right); rl.setSpacing(6)
        self.cache_panel = _CachePanel(cache.size)
        rl.addWidget(self.cache_panel)
        mem_split = QSplitter(Qt.Orientation.Vertical)
        self.ram_panel  = _MemoryPanel("RAM",  ram.size)
        mem_split.addWidget(self.ram_panel)
        if disc:
            self.disc_panel = _MemoryPanel("DISC", disc.size, has_pointer=True)
            mem_split.addWidget(self.disc_panel)
        else:
            self.disc_panel = None
        rl.addWidget(mem_split)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.nav    = _NavBar()
        self.status = _StatusBar()
        root.addWidget(self.nav)
        root.addWidget(self.status)

    def apply(self, snap: Snapshot, hist_len: int, cpu_running: bool, at_live: bool):
        instr_name = get_instruction_name(snap.IR)
        self.instruction_label.setText(f"Dernière instruction exécutée : {instr_name}  (Opcode: {snap.IR:#04x})")
        
        self.reg_panel.refresh(snap)
        self.flag_panel.refresh(snap)
        self.cache_panel.refresh(snap)
        self.ram_panel.refresh(snap.ram_mem)
        if self.disc_panel and snap.disc_mem is not None:
            self.disc_panel.refresh(snap.disc_mem, snap.disc_pointer)
        self.nav.update_range(hist_len - 1, snap.step)
        self.nav.set_buttons_enabled(snap.step > 0, snap.step < hist_len - 1, cpu_running)
        self.status.refresh(snap.step, hist_len, cpu_running, at_live)


# ==============================================
#  MONITEUR PUBLIC
# ==============================================

class MonitorQt:
    def __init__(self, arch, cpu, reg, ram, cache, disc=None, auto_play=False):
        self.arch  = arch
        self.cpu   = cpu
        self.reg   = reg
        self.ram   = ram
        self.cache = cache
        self.disc  = disc

        self._history: list[Snapshot] = []
        self._cur_idx   = 0
        self._at_live   = True
        self._playing   = auto_play
        self._play_speed = 200

        # synchronisation CPU - GUI
        self._step_event = threading.Event()
        self._lock       = threading.Lock()
        self._orig_step  = None
        self._signals    = _Signals()

        self._app = QApplication.instance() or QApplication(sys.argv)
        self._win = _MonitorWindow(arch, reg, ram, cache, disc)

        # timer auto-play
        self._timer = QTimer()
        self._timer.timeout.connect(self._auto_next)

        # connexions boutons
        nav = self._win.nav
        nav.sig_first.connect(self._go_first)
        nav.sig_prev.connect(self._go_prev)
        nav.sig_next.connect(self._go_next)
        nav.sig_last.connect(self._go_last)
        nav.sig_play.connect(self._on_play)
        nav.sig_seek.connect(self._go_to)
        nav.sig_speed.connect(self._set_speed)

        self._signals.new_snapshot.connect(self._on_new_snapshot)

    # ─────────────────────────────────────────
    #  API PUBLIQUE
    # ─────────────────────────────────────────

    def attach(self):
        """Instrumente cpu.step(), démarre le CPU dans un thread, puis la GUI (bloquant)."""
        # snapshot initial (état avant tout step)
        self._save_snapshot()
        self._display(0)

        self._orig_step = self.cpu.step
        monitor = self

        def _step():
            # 1. On attend le feu vert (via "Next", "Play" ou le Timer)
            monitor._step_event.wait()
            # 2. On referme la barrière immédiatement pour le step suivant
            monitor._step_event.clear()

            if not monitor.cpu.running:
                return
                
            monitor._orig_step()
            monitor._save_snapshot()
            monitor._signals.new_snapshot.emit()

        self.cpu.step = _step

        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()

        self._win.show()

        # Initialisation de l'état UI
        if self._playing:
            self._win.nav.set_playing(True)

        # On donne le feu vert pour la toute première instruction (Step 1)
        self._step_event.set()

        self._app.exec()

    def detach(self):
        if self._orig_step:
            self.cpu.step = self._orig_step

    # -----------------------------------------
    #  INTERNES
    # -----------------------------------------

    def _run_loop(self):
        """Remplace cpu.run() pour garder le contrôle."""
        while self.cpu.running:
            self.cpu.step()
        # snapshot final après HLT
        self._save_snapshot()
        self._signals.new_snapshot.emit()

    def _save_snapshot(self):
        with self._lock:
            idx  = len(self._history)
            snap = Snapshot(self.reg, self.ram, self.cache, self.disc, step=idx)
            self._history.append(snap)

    def _on_new_snapshot(self):
        """Appelé dans le thread Qt — met à jour l'affichage si on est en live."""
        with self._lock:
            hist_len = len(self._history)

        if self._at_live:
            self._cur_idx = hist_len - 1
            self._display(self._cur_idx)

        # en auto-play : on relâche immédiatement le CPU pour le step suivant
        if self._playing and self._at_live and self.cpu.running:
            QTimer.singleShot(self._play_speed, self._release_cpu)

    def _display(self, idx: int):
        with self._lock:
            if not (0 <= idx < len(self._history)):
                return
            snap     = self._history[idx]
            hist_len = len(self._history)
        self._at_live = (idx == hist_len - 1)
        self._win.apply(snap, hist_len, self.cpu.running, self._at_live)

    def _restore(self, idx: int):
        """Restaure l'état des composants depuis un snapshot et met à jour l'UI."""
        with self._lock:
            if not (0 <= idx < len(self._history)):
                return
            snap = self._history[idx]
        snap.restore(self.reg, self.ram, self.cache, self.disc)
        self._cur_idx = idx
        self._display(idx)

    def _release_cpu(self):
        self._step_event.set()

    # ─────────────────────────────────────────
    #  NAVIGATION
    # ─────────────────────────────────────────

    def _go_first(self):
        self._stop_play()
        self._restore(0)

    def _go_prev(self):
        self._stop_play()
        self._restore(self._cur_idx - 1)

    def _go_next(self):
        with self._lock:
            hist_len = len(self._history)

        if self._cur_idx < hist_len - 1:
            # navigation dans l'historique existant
            self._restore(self._cur_idx + 1)
        elif self.cpu.running:
            # on est au dernier snapshot -> demander un step au CPU
            self._at_live = True
            self._step_event.set()

    def _go_last(self):
        with self._lock:
            last = len(self._history) - 1
        self._restore(last)
        self._at_live = True

    def _go_to(self, idx: int):
        self._stop_play()
        self._restore(idx)

    def _on_play(self, playing: bool):
        self._playing = playing
        if playing:
            # débloquer le CPU si on est live
            if self._at_live and self.cpu.running:
                self._step_event.set()
            else:
                # replay automatique dans l'historique via timer
                self._timer.start(self._play_speed)
        else:
            self._timer.stop()

    def _stop_play(self):
        if self._playing:
            self._playing = False
            self._timer.stop()
            self._win.nav.set_playing(False)

    def _set_speed(self, ms: int):
        self._play_speed = ms
        if self._timer.isActive():
            self._timer.setInterval(ms)

    def _auto_next(self):
        """Appelé par le timer en mode auto-play replay (navigation historique)."""
        if self._at_live:
            self._timer.stop()
            return
        with self._lock:
            hist_len = len(self._history)
        if self._cur_idx < hist_len - 1:
            self._restore(self._cur_idx + 1)
        else:
            self._at_live = True
            self._timer.stop()
            if self.cpu.running:
                self._step_event.set()