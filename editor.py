import sys
import os
import shutil

import emulator

from format_converter import assembler_v4, disassembler_v4
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QTextEdit,
    QScrollBar,
    QTabWidget,
    QPushButton,
    QTreeView,
    QSplitter,
    QInputDialog,
    QMessageBox,
    QMenu,
    QFileDialog,
    QLabel,
    QLineEdit,
)
from PyQt6.QtGui import (
    QColor,
    QTextFormat,
    QPainter,
    QTextCursor,
    QFileSystemModel,
    QSyntaxHighlighter,
    QTextCharFormat,
    QFont,
    QShortcut,
    QKeySequence
)
from PyQt6.QtCore import (
    Qt,
    QRect,
    QSize,
    QDir,
    QMimeData,
    QUrl,
    QRegularExpression,
    QProcess,
    QProcessEnvironment,
)

# =========================================================
# Convertisseur ASM ↔ HEX ↔ BIN
# (import depuis format_converter.py)
# =========================================================

from format_converter import assembler_v4, disassembler_v4
# =========================================================
# Utilitaire
# =========================================================

def fmt(color, bold=False, italic=False):
    """Crée un QTextCharFormat coloré."""
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


# =========================================================
# Highlighter ASM
# =========================================================

ASM_INSTRUCTIONS = [
    "MOV", "MOVI", "MOVR",
    "ADD", "ADDI", "ADDR", "SUB", "SUBI", "SUBR",
    "AND", "ANDI", "OR", "ORI", "XOR", "XORI", "NOT",
    "SHL", "SHR",
    "CMP", "CMPI",
    "JMP", "JZ", "JNZ", "JE", "JNE", "JL", "JG", "JLE", "JGE",
    "CALL", "RET",
    "PUSH", "POP",
    "IN", "OUT",
    "HLT", "NOP", "HALT",
    "INC", "DEC",
    "LD", "ST", "LDR", "STR",
]

class AsmHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # 1. Références de labels en PREMIER (base colorée)
        #    Mots tout-majuscules — les règles suivantes écrasent si besoin
        self.rules.append((
            QRegularExpression(r"\b[A-Z_][A-Z0-9_]+\b"),
            fmt("#f64fff")            # cyan vif
        ))

        # 2. Définitions de labels : MOT:
        self.rules.append((
            QRegularExpression(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*:"),
            fmt("#f9c74f", bold=True) # jaune doré — distinct des instructions
        ))

        # 3. Instructions — passent PAR-DESSUS les refs de labels
        instr = r"\b(?:" + "|".join(ASM_INSTRUCTIONS) + r")\b"
        self.rules.append((
            QRegularExpression(instr, QRegularExpression.PatternOption.CaseInsensitiveOption),
            fmt("#569cd6", bold=True)
        ))

        # 4. Registres R0-R31
        self.rules.append((
            QRegularExpression(r"\bR\d{1,2}\b"),
            fmt("#9cdcfe")
        ))

        # 5. Nombres hexadécimaux
        self.rules.append((
            QRegularExpression(r"\b0[xX][0-9A-Fa-f]+\b"),
            fmt("#ce9178")
        ))

        # 6. Nombres décimaux
        self.rules.append((
            QRegularExpression(r"\b\d+\b"),
            fmt("#b5cea8")
        ))

        # Crochets [n]
        self.rules.append((
            QRegularExpression(r"\[[^\]]*\]"),
            fmt("#808080", italic=True)
        ))

        # Commentaires ; …  (priorité maximale, appliqués en dernier)
        self.comment_fmt = fmt("#6a9955", italic=True)
        self.comment_re  = QRegularExpression(r";[^\n]*")

    def highlightBlock(self, text):
        for pattern, char_fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), char_fmt)
        # Commentaires par-dessus tout
        it = self.comment_re.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self.comment_fmt)


# =========================================================
# Highlighter Python
# =========================================================

PY_KEYWORDS = [
    "False","None","True","and","as","assert","async","await",
    "break","class","continue","def","del","elif","else","except",
    "finally","for","from","global","if","import","in","is",
    "lambda","nonlocal","not","or","pass","raise","return",
    "try","while","with","yield",
]

PY_BUILTINS = [
    "print","len","range","int","float","str","list","dict","set",
    "tuple","bool","type","isinstance","super","self","cls",
    "open","enumerate","zip","map","filter","sorted","reversed",
    "min","max","sum","abs","round","input","hasattr","getattr",
    "setattr","property","staticmethod","classmethod",
]

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # Décorateurs
        self.rules.append((QRegularExpression(r"@[A-Za-z_]\w*"), fmt("#c586c0")))

        # Mots-clés
        self.rules.append((
            QRegularExpression(r"\b(?:" + "|".join(PY_KEYWORDS) + r")\b"),
            fmt("#569cd6", bold=True)
        ))

        # Builtins
        self.rules.append((
            QRegularExpression(r"\b(?:" + "|".join(PY_BUILTINS) + r")\b"),
            fmt("#4ec9b0")
        ))

        # Noms après def / class
        self.rules.append((
            QRegularExpression(r"(?<=\bdef\s)[A-Za-z_]\w*"),
            fmt("#dcdcaa")
        ))
        self.rules.append((
            QRegularExpression(r"(?<=\bclass\s)[A-Za-z_]\w*"),
            fmt("#4ec9b0", bold=True)
        ))

        # Hex
        self.rules.append((QRegularExpression(r"\b0[xX][0-9A-Fa-f]+\b"), fmt("#ce9178")))
        # Nombres
        self.rules.append((QRegularExpression(r"\b\d+\.?\d*\b"), fmt("#b5cea8")))

        # Chaînes simples (simple et double)
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt("#ce9178")))
        self.rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), fmt("#ce9178")))

        # f-strings simples
        self.rules.append((QRegularExpression(r'f"[^"]*"'), fmt("#ce9178")))
        self.rules.append((QRegularExpression(r"f'[^']*'"), fmt("#ce9178")))

        # Commentaires
        self.comment_fmt = fmt("#6a9955", italic=True)
        self.comment_re  = QRegularExpression(r"#[^\n]*")

        # Docstrings triple-guillemets (état bloc)
        self.tq_fmt   = fmt("#ce9178")
        self.tq_start = QRegularExpression(r'"""')
        self.tq_end   = QRegularExpression(r'"""')

    def highlightBlock(self, text):
        # Docstrings multilignes
        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            m = self.tq_start.match(text)
            start = m.capturedStart() if m.hasMatch() else -1
        if start >= 0:
            m_end = self.tq_end.match(text, start + 3)
            if m_end.hasMatch():
                self.setFormat(start, m_end.capturedEnd() - start, self.tq_fmt)
            else:
                self.setCurrentBlockState(1)
                self.setFormat(start, len(text) - start, self.tq_fmt)

        for pattern, char_fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), char_fmt)

        it = self.comment_re.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self.comment_fmt)


# =========================================================
# Fabrique
# =========================================================

def make_highlighter(ext, document):
    e = ext.lower()
    if e in (".asm", ".s"):
        return AsmHighlighter(document)
    if e in (".py", ".pyw"):
        return PythonHighlighter(document)
    return None


# =========================================================
# Zone des numéros de lignes
# =========================================================

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


# =========================================================
# Éditeur de code
# =========================================================

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        self._highlighter = None

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

        font = self.font()
        font.setFamily("Consolas")
        font.setPointSize(11)
        self.setFont(font)

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; border: none;")

    def apply_highlighter(self, ext):
        self._highlighter = make_highlighter(ext, self.document())

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 15 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))
        block        = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top          = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom       = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                is_current = self.textCursor().blockNumber() == block_number
                painter.setPen(QColor("#c6c6c6") if is_current else QColor("#858585"))
                painter.drawText(
                    0, top,
                    self.line_number_area.width() - 8, self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight, str(block_number + 1)
                )
            block        = block.next()
            top          = bottom
            bottom       = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#2a2d2e"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)


# =========================================================
# Arbre de fichiers (Drag & Drop, clic droit, raccourcis)
# =========================================================

class FileTreeView(QTreeView):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QTreeView.SelectionMode.SingleSelection)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def keyPressEvent(self, event):
        index = self.currentIndex()
        if not index.isValid():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Delete:
            self.main_window.delete_item(index)
        elif event.key() == Qt.Key.Key_F2:
            self.main_window.rename_item(index)
        else:
            super().keyPressEvent(event)

    def show_context_menu(self, pos):
        index = self.indexAt(pos)
        menu  = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #444;
                padding: 4px 0;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background-color: #37373d; }
            QMenu::separator { height: 1px; background: #444; margin: 4px 0; }
        """)

        if index.isValid():
            path   = self.model().filePath(index)
            is_dir = os.path.isdir(path)
            action_open = menu.addAction("Ouvrir")
            action_open.triggered.connect(lambda: self.main_window.open_file_from_sidebar(index))
            menu.addSeparator()
            action_rename = menu.addAction("Renommer  (F2)")
            action_rename.triggered.connect(lambda: self.main_window.rename_item(index))
            action_delete = menu.addAction("Supprimer  (Suppr)")
            action_delete.triggered.connect(lambda: self.main_window.delete_item(index))
            menu.addSeparator()

        menu.addAction("Nouveau fichier").triggered.connect(self.main_window.create_new_file)
        menu.addAction("Nouveau dossier").triggered.connect(self.main_window.create_new_folder)
        menu.exec(self.viewport().mapToGlobal(pos))

    # ── Drag & Drop ──────────────────────────────────────────

    def dragEnterEvent(self, event):
        event.acceptProposedAction() if event.mimeData().hasUrls() else super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        event.acceptProposedAction() if event.mimeData().hasUrls() else super().dragMoveEvent(event)

    def dropEvent(self, event):
        target_index = self.indexAt(event.position().toPoint())
        model        = self.model()
        if not target_index.isValid():
            target_dir = self.main_window.root_path
        else:
            p = model.filePath(target_index)
            target_dir = p if os.path.isdir(p) else os.path.dirname(p)

        errors = []
        for url in event.mimeData().urls():
            src = url.toLocalFile()
            if not src:
                continue
            name = os.path.basename(src)
            dst  = os.path.join(target_dir, name)
            if os.path.abspath(src) == os.path.abspath(dst):
                continue
            if os.path.isdir(src) and os.path.abspath(dst).startswith(os.path.abspath(src)):
                errors.append(f"Impossible de déplacer '{name}' dans lui-même.")
                continue
            if os.path.exists(dst):
                reply = QMessageBox.question(
                    self, "Conflit",
                    f"'{name}' existe déjà. Remplacer ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    continue
                (shutil.rmtree if os.path.isdir(dst) else os.remove)(dst)
            try:
                shutil.move(src, dst)
                self.main_window.update_tabs_after_move(src, dst)
            except Exception as e:
                errors.append(f"{name} : {e}")

        if errors:
            QMessageBox.critical(self, "Erreurs de déplacement", "\n".join(errors))
        event.acceptProposedAction()

    def mimeData(self, indexes):
        mime = QMimeData()
        mime.setUrls([
            QUrl.fromLocalFile(self.model().filePath(i))
            for i in indexes if i.column() == 0
        ])
        return mime


# =========================================================
# Fenêtre principale
# =========================================================

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyCode IDE")
        self.resize(1400, 900)

        self.file_model = QFileSystemModel()
        self.root_path  = QDir.currentPath()
        self.file_model.setRootPath(self.root_path)

        self.tree = FileTreeView(self)
        self.tree.setModel(self.file_model)
        self.tree.setRootIndex(self.file_model.index(self.root_path))
        for i in range(1, 4):
            self.tree.setColumnHidden(i, True)
        self.tree.setHeaderHidden(True)
        self.tree.doubleClicked.connect(self.open_file_from_sidebar)

        # Sidebar
        sidebar_container = QWidget()
        sidebar_layout    = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        sidebar_tools = QHBoxLayout()
        sidebar_tools.setContentsMargins(10, 5, 10, 5)
        btn_new_file   = QPushButton("Nouveau fichier")
        btn_new_folder = QPushButton("Nouveau dossier")
        btn_save       = QPushButton("Sauvegarder")
        btn_new_file.setToolTip("Nouveau fichier")
        btn_new_folder.setToolTip("Nouveau dossier")
        btn_save.setToolTip("Sauvegarder (Ctrl+S)")
        btn_new_file.clicked.connect(self.create_new_file)
        btn_new_folder.clicked.connect(self.create_new_folder)
        btn_save.clicked.connect(self.save_current_file)
        sidebar_tools.addWidget(btn_new_file)
        sidebar_tools.addWidget(btn_new_folder)
        sidebar_tools.addWidget(btn_save)
        sidebar_tools.addStretch()

        sidebar_layout.addLayout(sidebar_tools)
        sidebar_layout.addWidget(self.tree)

        # Onglets
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.sync_active_editor)

        # Scrollbars
        self.vertical_slider   = QScrollBar(Qt.Orientation.Vertical)
        self.vertical_slider.setInvertedAppearance(True)
        self.horizontal_slider = QScrollBar(Qt.Orientation.Horizontal)

        # Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter   = QSplitter(Qt.Orientation.Horizontal)
        right_container = QWidget()
        right_outer     = QVBoxLayout(right_container)
        right_outer.setContentsMargins(0, 0, 0, 0)
        right_outer.setSpacing(0)

        # ── Barre d'outils principale ────────────────────────
        top_bar = QWidget()
        top_bar.setObjectName("top_bar")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(8, 5, 8, 5)
        top_bar_layout.setSpacing(6)

        # -- Boutons de conversion (gauche) -------------------
        btn_asm_hex = QPushButton("ASM -> HEX")
        btn_hex_bin = QPushButton("HEX -> BIN")
        btn_asm_bin = QPushButton("ASM -> BIN")
        for btn in (btn_asm_hex, btn_hex_bin, btn_asm_bin):
            btn.setObjectName("conv_btn")
            top_bar_layout.addWidget(btn)

        btn_asm_hex.setToolTip("Assembler le code ASM de l'onglet actif en HEX")
        btn_hex_bin.setToolTip("Convertir le HEX de l'onglet actif en binaire")
        btn_asm_bin.setToolTip("Assembler directement le code ASM en binaire")
        btn_asm_hex.clicked.connect(lambda: self.run_conversion("asm_hex"))
        btn_hex_bin.clicked.connect(lambda: self.run_conversion("hex_bin"))
        btn_asm_bin.clicked.connect(lambda: self.run_conversion("asm_bin"))

        top_bar_layout.addStretch()

        # -- Sélecteur de fichier .pcc (droite) ---------------
        lbl_pcc = QLabel(".pcc :")
        lbl_pcc.setObjectName("run_label")
        self.pcc_path_edit = QLineEdit()
        self.pcc_path_edit.setObjectName("pcc_edit")
        self.pcc_path_edit.setReadOnly(True)
        self.pcc_path_edit.setFixedWidth(200)
        self.pcc_path_edit.setPlaceholderText("Aucun fichier sélectionné")
        btn_browse = QPushButton("📂") # Emoji
        btn_browse.setObjectName("run_btn")
        btn_browse.setToolTip("Sélectionner un fichier .pcc")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self.browse_pcc)

        top_bar_layout.addWidget(lbl_pcc)
        top_bar_layout.addWidget(self.pcc_path_edit)
        top_bar_layout.addWidget(btn_browse)

        # -- Boutons d'exécution (droite) ---------------------
        btn_run        = QPushButton("Run")
        btn_run_mon    = QPushButton("Buggué") # TODO : "Monitor", Affichage non correct !!!
        btn_run_qt     = QPushButton("Qt")
        for btn in (btn_run, btn_run_mon, btn_run_qt):
            btn.setObjectName("run_btn")
            top_bar_layout.addWidget(btn)

        btn_run.setToolTip("Exécuter le(s) programme(s)")
        btn_run_mon.setToolTip("Exécuter en mode monitor")
        btn_run_qt.setToolTip("Exécuter en mode Qt monitor")
        btn_run.clicked.connect(lambda: self.run_main())
        btn_run_mon.clicked.connect(lambda: self.run_main(monitor=True))
        btn_run_qt.clicked.connect(lambda: self.run_main(qt=True))

        right_outer.addWidget(top_bar)

        # ── Tabs + scrollbar verticale ───────────────────────
        right_inner  = QWidget()
        right_layout = QHBoxLayout(right_inner)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.tabs)
        right_layout.addWidget(self.vertical_slider)
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.right_splitter.addWidget(right_inner)

        # Création de la console intégrée (Zone de texte en lecture seule)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            background-color: #121212;
            color: #d4d4d4;
            font-family: 'Consolas', monospace;
            font-size: 11px;
            border-top: 1px solid #333;
        """)
        self.right_splitter.addWidget(self.console)
        
        # Définit les tailles initiales par défaut (650px pour le code, 200px pour la console)
        self.right_splitter.setSizes([650, 200])

        right_outer.addWidget(self.right_splitter)

        self.splitter.addWidget(sidebar_container)
        self.splitter.addWidget(right_container)
        self.splitter.setSizes([250, 1150])

        main_layout.addWidget(self.splitter)
        main_layout.addWidget(self.horizontal_slider)

        self.add_new_tab("Bienvenue", "# Bienvenue dans l'éditeur !\n")
        self.apply_style()

        # Raccourci Ctrl+S
        shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        shortcut_save.activated.connect(self.save_current_file)

    # ── Sélecteur .pcc & exécution ──────────────────────────

    def browse_pcc(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier .pcc", "", "PCC Files (*.pcc);;All Files (*)"
        )
        if path:
            self.pcc_path_edit.setText(path)

    def run_main(self, monitor=False, qt=False):
        pcc = self.pcc_path_edit.text().strip()
        if not pcc:
            QMessageBox.warning(self, "Aucun fichier .pcc", "Veuillez d'abord sélectionner un fichier .pcc.")
            return

        # Nettoyer la console avant le lancement
        self.console.clear()
        self.console.appendPlainText("-> Démarrage du sous-processus de l'émulateur...\n")

        self.process = QProcess(self)
        
        # =====================================================================
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUTF8", "1")          # Active le mode UTF-8 natif de Python
        env.insert("PYTHONIOENCODING", "utf-8") # Force l'encodage des flux print()
        self.process.setProcessEnvironment(env)
        # =====================================================================

        # Connexion des signaux pour capturer les flux de sortie en temps réel
        self.process.readyReadStandardOutput.connect(self.read_stdout)
        self.process.readyReadStandardError.connect(self.read_stderr)

        # Préparation des arguments
        args = ["emulator.py", pcc]
        if qt:
            args.append("--qt")
        if monitor:
            args.append("--cli")
        if not monitor:
            args.append("--screen")

        # Lance l'émulateur
        self.process.start(sys.executable, args)
    
    def read_stdout(self):
        """Lit la sortie standard de l'émulateur et l'ajoute à la console."""
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
        self.console.insertPlainText(data)
        self.console.ensureCursorVisible() # Scroll automatique vers le bas

    def read_stderr(self):
        """Lit les erreurs de l'émulateur et les affiche dans la console."""
        data = self.process.readAllStandardError().data().decode('utf-8', errors='ignore')
        self.console.insertPlainText(data)
        self.console.ensureCursorVisible()

    # ── Conversion ASM / HEX / BIN ──────────────────────────

    def run_conversion(self, mode):
        editor = self.tabs.currentWidget()
        if not isinstance(editor, CodeEditor):
            return
        content = editor.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Onglet vide", "L'onglet actif ne contient aucun contenu à convertir.")
            return

        src_name = self.tabs.tabText(self.tabs.currentIndex())
        base     = os.path.splitext(src_name)[0]
        
        src_path = getattr(editor, "file_path", None)

        try:
            if mode == "asm_hex":
                result   = assembler_v4(content, to="hex")
                out_name = base + ".hex"
                out_ext  = ".hex"
            elif mode == "hex_bin":
                result   = assembler_v4(
                    content, to="bin"
                ) if False else " ".join(
                    format(int(tok, 16), f"0{len(tok)*4}b")
                    for tok in content.split()
                )
                out_name = base + ".bin"
                out_ext  = ".bin"
            elif mode == "asm_bin":
                result   = assembler_v4(content, to="bin")
                out_name = base + ".bin"
                out_ext  = ".bin"
            else:
                return
        except Exception as e:
            QMessageBox.critical(self, "Erreur de conversion", str(e))
            return

        out_path = None
        if src_path:
            dir_name = os.path.dirname(src_path)
            out_path = os.path.join(dir_name, out_name)
            
            try:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(result)
            except Exception as e:
                QMessageBox.warning(self, "Erreur d'écriture", f"Impossible d'écrire le fichier sur le disque : {e}")

        self.add_new_tab(out_name, result, ext=out_ext, file_path=out_path)

    # ── Sauvegarde ───────────────────────────────────────────

    def save_current_file(self):
        editor = self.tabs.currentWidget()
        if not isinstance(editor, CodeEditor):
            return
        path = getattr(editor, "file_path", None)
        if not path:
            QMessageBox.information(
                self, "Aucun fichier associé",
                "Cet onglet n'est lié à aucun fichier sur le disque."
            )
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            # Feedback visuel : astérisque retiré du nom d'onglet si présent
            idx = self.tabs.currentIndex()
            tab_name = self.tabs.tabText(idx)
            if tab_name.endswith(" *"):
                self.tabs.setTabText(idx, tab_name[:-2])
        except Exception as e:
            QMessageBox.critical(self, "Erreur de sauvegarde", str(e))

    # ── Fichiers ────────────────────────────────────────────

    def get_current_directory(self):
        index = self.tree.currentIndex()
        if index.isValid():
            path = self.file_model.filePath(index)
            return path if os.path.isdir(path) else os.path.dirname(path)
        return self.root_path

    def create_new_file(self):
        name, ok = QInputDialog.getText(self, "Nouveau Fichier", "Nom du fichier :")
        if ok and name:
            target = os.path.join(self.get_current_directory(), name)
            try:
                open(target, 'w').close()
                self.add_new_tab(name, "", file_path=target)
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Impossible de créer le fichier : {e}")

    def create_new_folder(self):
        name, ok = QInputDialog.getText(self, "Nouveau Dossier", "Nom du dossier :")
        if ok and name:
            try:
                os.makedirs(os.path.join(self.get_current_directory(), name), exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Impossible de créer le dossier : {e}")

    def rename_item(self, index):
        if not index.isValid():
            return
        old_path   = self.file_model.filePath(index)
        old_name   = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "Renommer", "Nouveau nom :", text=old_name)
        if not ok or not new_name or new_name == old_name:
            return
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Conflit", f"'{new_name}' existe déjà.")
            return
        try:
            os.rename(old_path, new_path)
            self.update_tabs_after_move(old_path, new_path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de renommer : {e}")

    def delete_item(self, index):
        if not index.isValid():
            return
        path   = self.file_model.filePath(index)
        name   = os.path.basename(path)
        is_dir = os.path.isdir(path)
        kind   = "le dossier" if is_dir else "le fichier"
        if QMessageBox.question(
            self, "Confirmer la suppression",
            f"Supprimer définitivement {kind} « {name} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            (shutil.rmtree if is_dir else os.remove)(path)
            self.close_tabs_for_path(path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de supprimer : {e}")

    # ── Onglets ─────────────────────────────────────────────

    def close_tabs_for_path(self, path):
        name = os.path.basename(path)
        for i in range(self.tabs.count() - 1, -1, -1):
            editor = self.tabs.widget(i)
            # Ferme si le fichier correspond exactement, ou si son chemin est sous le dossier supprimé
            fp = getattr(editor, "file_path", None) if isinstance(editor, CodeEditor) else None
            by_path = fp and (fp == path or fp.startswith(path + os.sep))
            by_name = self.tabs.tabText(i) == name
            if (by_path or by_name) and self.tabs.count() > 1:
                self.tabs.removeTab(i)

    def update_tabs_after_move(self, old_path, new_path):
        old_name = os.path.basename(old_path)
        new_name = os.path.basename(new_path)
        new_ext  = os.path.splitext(new_name)[1]
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            # Correspondance prioritaire par chemin complet, fallback sur le nom
            tab_matches = (
                isinstance(editor, CodeEditor) and getattr(editor, "file_path", None) == old_path
            ) or self.tabs.tabText(i) == old_name
            if tab_matches:
                self.tabs.setTabText(i, new_name)
                if isinstance(editor, CodeEditor):
                    editor.file_path = new_path
                    editor.apply_highlighter(new_ext)

    def open_file_from_sidebar(self, index):
        path = self.file_model.filePath(index)
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                ext = os.path.splitext(path)[1]
                self.add_new_tab(os.path.basename(path), content, ext, file_path=path)
            except Exception as e:
                print(e)

    def add_new_tab(self, name, content="", ext=None, file_path=None):
        editor = CodeEditor()
        editor.file_path = file_path  # chemin complet ou None si non sauvegardé
        editor.setPlainText(content)
        editor.apply_highlighter(ext if ext else os.path.splitext(name)[1])
        index = self.tabs.addTab(editor, name)
        self.tabs.setCurrentIndex(index)

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)

    def sync_active_editor(self):
        editor = self.tabs.currentWidget()
        if not editor:
            return
        try:
            self.vertical_slider.valueChanged.disconnect()
            self.horizontal_slider.valueChanged.disconnect()
        except Exception:
            pass
        self.vertical_slider.valueChanged.connect(editor.verticalScrollBar().setValue)
        self.horizontal_slider.valueChanged.connect(editor.horizontalScrollBar().setValue)
        editor.verticalScrollBar().valueChanged.connect(self.vertical_slider.setValue)
        editor.horizontalScrollBar().valueChanged.connect(self.horizontal_slider.setValue)
        editor.verticalScrollBar().rangeChanged.connect(
            lambda mn, mx: self.vertical_slider.setRange(mn, mx))
        editor.horizontalScrollBar().rangeChanged.connect(
            lambda mn, mx: self.horizontal_slider.setRange(mn, mx))
        self.vertical_slider.setRange(0, editor.verticalScrollBar().maximum())
        self.horizontal_slider.setRange(0, editor.horizontalScrollBar().maximum())

    # ── Style ────────────────────────────────────────────────

    def apply_style(self):
        self.setStyleSheet("""
            QWidget { background-color: #1e1e1e; color: #cccccc; }

            QPushButton {
                background: transparent; border: none;
                font-size: 16px; padding: 2px;
            }
            QPushButton:hover { background: #37373d; border-radius: 3px; }

            QWidget#top_bar {
                background-color: #252526;
                border-bottom: 1px solid #333;
            }
            QPushButton#conv_btn {
                background-color: #0e639c;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 12px;
                border-radius: 4px;
                border: none;
            }
            QPushButton#conv_btn:hover   { background-color: #1177bb; }
            QPushButton#conv_btn:pressed { background-color: #0a4f7e; }

            QLabel#run_label {
                color: #888;
                font-size: 12px;
            }
            QLineEdit#pcc_edit {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
            }
            QPushButton#run_btn {
                background-color: #2d7a3a;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 12px;
                border-radius: 4px;
                border: none;
            }
            QPushButton#run_btn:hover   { background-color: #389648; }
            QPushButton#run_btn:pressed { background-color: #1f5928; }

            QTreeView { background-color: #252526; border: none; }
            QTreeView::item:hover    { background-color: #2a2d2e; }
            QTreeView::item:selected { background-color: #37373d; }

            QSplitter::handle { background-color: #000000; }

            QTabWidget::pane { border-top: 1px solid #333333; }
            QTabBar::tab {
                background: #2d2d2d; padding: 8px 12px;
                border-right: 1px solid #1e1e1e;
            }
            QTabBar::tab:selected {
                background: #1e1e1e;
                border-bottom: 2px solid #007acc;
                color: white;
            }

            QScrollBar { background: #1e1e1e; border: none; }
            QScrollBar:vertical   { width: 10px; }
            QScrollBar:horizontal { height: 10px; }
            QScrollBar::handle    { background: #424242; }

            QInputDialog QLineEdit {
                background: #3c3c3c; color: #cccccc;
                border: 1px solid #555; padding: 4px;
            }
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())