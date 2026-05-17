import computer
import hex_loader
from monitor_qt import MonitorQt
# On importe le moniteur CLI s'il existe
try:
    from monitor import Monitor
except ImportError:
    Monitor = None

import sys
import re
import inspect
import threading
import cProfile
import argparse
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QImage
from PyQt6.QtCore import Qt, pyqtSignal

# --- Fonctions Python pour l'IOController ---
def virtual_output(value):
    print(f"[OUTPUT] The CPU has sent the value : {value}")

def virtual_input():
    return int(input("[INPUT] Enter a value (0-255): "))

class RGBScreenWindow(QWidget):
    frame_ready = pyqtSignal(bytes)

    def __init__(self, width=16, height=16, scale=20):
        super().__init__()
        self.setWindowTitle("GPU Screen")
        self.setFixedSize(width * scale, height * scale)
        self.width, self.height, self.scale = width, height, scale
        self.image = QImage(width, height, QImage.Format.Format_RGB888)
        self.image.fill(Qt.GlobalColor.black)
        self.frame_ready.connect(self._apply_frame)

    def update_frame(self, vram_buffer):
        self.frame_ready.emit(bytes(vram_buffer))

    def _apply_frame(self, vram_buffer):
        self.image = QImage(vram_buffer, self.width, self.height, QImage.Format.Format_RGB888)
        self.update()

    def paintEvent(self, event):
        QPainter(self).drawImage(self.contentsRect(), self.image)

def parse_ports(ports_str):
    ports = []
    for part in ports_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = [int(p.strip(), 16) if '0x' in p else int(p.strip()) for p in part.split('-')]
            ports.extend(range(start, end + 1))
        else:
            ports.append(int(part, 16) if '0x' in part else int(part))
    return ports

def load_pcc_config(filename):
    config = {"Architecture": {}, "GPU": (16,16), "Monitor": (16,16), "Scale": 1, "IOController": [], "LOAD": {},
              "CPUSpeed": 0, "RAMSpeed": 0, "CacheSpeed": 0, "DISCSpeed": 0, "RegistersSpeed": 0, "VRAMSpeed": 0}
    with open(filename, 'r') as f:
        content = f.read()

    arch_match = re.search(r'Architecture\s*:\s*\[(.*?)\]', content, re.DOTALL)
    if arch_match:
        for line in arch_match.group(1).split(','):
            k, v = line.split(':')
            config["Architecture"][k.strip()] = int(v.strip())

    for key in ["GPU", "Monitor"]:
        m = re.search(rf'{key}\s*:\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', content)
        if m: config[key] = (int(m.group(1)), int(m.group(2)))

    io_match = re.search(r'IOController\s*:\s*\[(.*?)\]', content, re.DOTALL)
    if io_match:
        for line in io_match.group(1).split('\n'):
            if ':' in line:
                p, t = line.split(':')
                config["IOController"].append((p.strip(), t.strip().rstrip(',')))

    m = re.search(r'Scale\s*:\s*(\d+)', content)
    if m: config["Scale"] = int(m.group(1))

    for key in ["CPUSpeed", "RAMSpeed", "CacheSpeed", "DISCSpeed", "RegistersSpeed", "VRAMSpeed"]:
        m = re.search(rf'{key}\s*:\s*(\d+)', content)
        if m: config[key] = int(m.group(1))

    load_match = re.search(r'LOAD\s*:\s*\[(.*?)\]', content, re.DOTALL)
    if load_match:
        for comp in ["Cache", "RAM", "DISC"]:
            m = re.search(rf'{comp}\s*:\s*\((.*?)\)', load_match.group(1))
            if m:
                files = [f.strip(' "') for f in m.group(1).split(',') if f.strip()]
                config["LOAD"][comp] = files
    return config


# --- COEUR DU SYSTEME / MODE BIBLIOTHÈQUE ---

def run_computer(config_file, with_screen=False, with_cli=False, with_qt=False, profile_cpu=False):
    """
    Lance le computer avec les composants d'affichage demandés.
    
    :param config_file: Chemin vers le fichier .pcc
    :param with_screen: Active la fenêtre de l'écran GPU seul
    :param with_cli: Active le moniteur interactif dans le terminal
    :param with_qt: Active l'interface complète de debugging MonitorQt
    :param profile_cpu: Active cProfile sur l'exécution du CPU
    """
    cfg = load_pcc_config(config_file)

    # Detect if a Qt app environment is already running (e.g., from the IDE)
    existing_app = QApplication.instance()
    is_standalone = existing_app is None

    app = None
    if with_screen or with_qt:
        app = existing_app or QApplication(sys.argv)

    # 1. Init Matériel
    arch = computer.Architecture(cfg["Architecture"]["data_bytes"], cfg["Architecture"]["address_bytes"])
    ram   = computer.RAM(arch,   mem_speed=cfg["RAMSpeed"])
    disc  = computer.DISC(arch,  mem_speed=cfg["DISCSpeed"])
    cache = computer.Cache(arch, mem_speed=cfg["CacheSpeed"])
    reg   = computer.Registers(arch, mem_speed=cfg["RegistersSpeed"])
    alu, io_ctrl = computer.ALU(arch, reg), computer.IOController(arch)

    # 2. IO & GPU
    gpu = computer.GPU(*cfg["GPU"], mem_speed=cfg["VRAMSpeed"])
    screen = None

    if with_screen:
        screen = RGBScreenWindow(*cfg["Monitor"], scale=cfg["Scale"])
        screen.show()
        gpu.on_render = screen.update_frame

    for p_str, target in cfg["IOController"]:
        ports = parse_ports(p_str)
        for port in ports:
            if target == "GPU":
                io_ctrl.connect_device(port, write_callback=lambda v, p=port: gpu.handle_command(p, v))
            elif target.startswith("py."):
                func = globals().get(target[3:].replace("()", ""))
                if func:
                    sig = inspect.signature(func)
                    if len(sig.parameters) > 0: io_ctrl.connect_device(port, write_callback=func)
                    else: io_ctrl.connect_device(port, read_callback=func)

    # 3. Chargement séquentiel
    loading_map = {"Cache": (cache, hex_loader.load_into_cache), 
                   "RAM": (ram, hex_loader.load_into_ram), 
                   "DISC": (disc, hex_loader.load_into_disc)}

    for comp_name, files in cfg["LOAD"].items():
        obj, loader_func = loading_map[comp_name]
        offset = 0
        print(f"\n--- Loading {comp_name} ---")
        for f in files:
            size = loader_func(f, obj, base_address=offset)
            print(f"✅ {f} ({size} bytes): loaded from 0x{offset:04X} to 0x{offset+size-1:04X}") # Emoji
            offset += size
                
    cpu = computer.CPU(arch, ram, disc, cache, reg, alu, io_ctrl, cpu_speed=cfg["CPUSpeed"])
    arch.info()

    # 4. Configuration des hooks de monitoring
    if with_cli:
        if Monitor:
            monitor = Monitor(arch, cpu, reg, ram, cache, disc, show_ram=False, step_by_step=True)
            monitor.attach()
            print("📺 CLI Monitor attached.") # Emoji
        else:
            print("⚠️ Unable to attach CLI Monitor : 'monitor.py' not found.") # Emoji

    if with_qt:
        monitor_qt = MonitorQt(arch, cpu, reg, ram, cache, disc)
        monitor_qt.attach()
        print("📊 Qt Monitor attached.") # Emoji -> Enlever peut-etre cette ligne

    # 5. Lancement du CPU
    print("--- STARTING CPU ---")
    
    def target_cpu_run():
        if profile_cpu:
            cProfile.runctx("cpu.run()", globals(), locals())
        else:
            cpu.run()

    if with_screen or with_qt:
        # Le CPU doit tourner dans son propre thread pour ne pas bloquer l'affichage
        cpu_thread = threading.Thread(target=target_cpu_run, daemon=True, name="CPU")
        cpu_thread.start()
        
        # CRITICAL FIX: Only execute the event loop if running standalone!
        if is_standalone:
            sys.exit(app.exec())
    else:
        # Mode purement CLI / Terminal sans aucune fenêtre
        target_cpu_run()


# --- GESTION DU MODE CLI (LIGNE DE COMMANDE) ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modular Computer Emulator")
    
    # Argument obligatoire
    parser.add_argument("config", type=str, help="Path to the configuration file .pcc")
    
    # Drapeaux activables (cumulables !)
    parser.add_argument("--screen", action="store_true", help="Activate the GPU screen window")
    parser.add_argument("--cli", action="store_true", help="Activate the interactive monitor in the terminal")
    parser.add_argument("--qt", action="store_true", help="Activate the complete monitoring interface MonitorQt")
    
    # Profilage
    parser.add_argument("--profile", action="store_true", help="Activate cProfile profiling on the CPU")

    args = parser.parse_args()

    # Si l'utilisateur lance le script sans spécifier d'affichage, on lui met l'écran par défaut
    if not (args.screen or args.cli or args.qt):
        args.screen = True

    # Lancement
    run_computer(
        config_file=args.config, 
        with_screen=args.screen, 
        with_cli=args.cli, 
        with_qt=args.qt, 
        profile_cpu=args.profile
    )