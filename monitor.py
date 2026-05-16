import os

# =========================
# COULEURS ANSI
# =========================

class _C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"

    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

    BG_BLACK   = "\033[40m"
    BG_BLUE    = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN    = "\033[46m"


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _bar(value, max_value, width=16, fill="█", empty="░"):
    filled = int((value / max_value) * width) if max_value else 0
    return fill * filled + empty * (width - filled)


# =========================
# AFFICHAGE REGISTRES
# =========================

def _display_registers(reg, arch):
    print(f"{_C.BOLD}{_C.BG_BLUE}{_C.WHITE}  REGISTRES  {_C.RESET}")
    print()

    for i in range(arch.registers_count):
        val = reg.read(i)
        bar = _bar(val, arch.data_mask)
        print(f"  {_C.CYAN}R{i}{_C.RESET}  {_C.YELLOW}{val:>3} {_C.DIM}({val:#04x}){_C.RESET}  {_C.GREEN}{bar}{_C.RESET}")

    print()
    pc  = reg.get_pc()
    sp  = reg.get_sp()
    ir  = reg.get_ir()
    fl  = reg.FLAGS

    print(f"  {_C.MAGENTA}PC{_C.RESET}  {_C.YELLOW}{pc:>5} {_C.DIM}({pc:#06x}){_C.RESET}")
    print(f"  {_C.MAGENTA}SP{_C.RESET}  {_C.YELLOW}{sp:>5} {_C.DIM}({sp:#06x}){_C.RESET}")
    print(f"  {_C.MAGENTA}IR{_C.RESET}  {_C.YELLOW}{ir:>5} {_C.DIM}({ir:#04x}){_C.RESET}")
    print(f"  {_C.MAGENTA}FL{_C.RESET}  {_C.YELLOW}{fl:>5} {_C.DIM}({fl:04b}b){_C.RESET}")


# =========================
# AFFICHAGE FLAGS
# =========================

def _display_flags(reg):
    print()
    print(f"{_C.BOLD}{_C.BG_MAGENTA}{_C.WHITE}  FLAGS  {_C.RESET}")
    print()

    flags = [
        (0, "Z", "Zero"),
        (1, "C", "Carry"),
        (2, "N", "Negative"),
        (3, "O", "Overflow"),
    ]

    for bit, short, name in flags:
        active = reg.get_flag(bit)
        color  = _C.GREEN if active else _C.RED
        symbol = "●" if active else "○"
        print(f"  {color}{symbol} {_C.BOLD}{short}{_C.RESET} {_C.DIM}{name}{_C.RESET}")


# =========================
# AFFICHAGE RAM
# =========================

def _display_ram(ram, cols=16):
    print()
    print(f"{_C.BOLD}{_C.BG_CYAN}{_C.BLACK}  RAM  {_C.RESET}")
    print()

    # en-tête colonnes
    header = "       " + "".join(f"{i:>3}" for i in range(cols))
    print(f"{_C.DIM}{header}{_C.RESET}")

    for row in range(0, ram.size, cols):
        line = f"  {_C.YELLOW}{row:#06x}{_C.RESET} "
        for col in range(cols):
            addr = row + col
            if addr < ram.size:
                val = ram.read(addr)
                color = _C.WHITE if val != 0 else _C.DIM
                line += f"{color}{val:>3}{_C.RESET}"
            else:
                line += "   "
        print(line)


# =========================
# AFFICHAGE DISC
# =========================

def _display_disc(disc, cols=16):
    print()
    print(f"{_C.BOLD}{_C.BG_BLACK}{_C.WHITE}  DISC  {_C.RESET}")
    print()

    # pointeur courant
    print(f"  {_C.DIM}pointeur : {_C.RESET}{_C.YELLOW}{disc.pointer:#06x}{_C.RESET} {_C.DIM}({disc.pointer}){_C.RESET}")
    print()

    # en-tête colonnes
    header = "       " + "".join(f"{i:>3}" for i in range(cols))
    print(f"{_C.DIM}{header}{_C.RESET}")

    for row in range(0, disc.size, cols):
        line = f"  {_C.YELLOW}{row:#06x}{_C.RESET} "
        for col in range(cols):
            addr = row + col
            if addr < disc.size:
                val = disc.memory[addr]
                # met en avant l'octet pointé par disc.pointer
                if addr == disc.pointer:
                    color = f"{_C.BOLD}{_C.MAGENTA}"
                elif val != 0:
                    color = _C.WHITE
                else:
                    color = _C.DIM
                line += f"{color}{val:>3}{_C.RESET}"
            else:
                line += "   "
        print(line)

    print(f"\n  {_C.DIM}▲ {_C.MAGENTA}●{_C.RESET}{_C.DIM} = position du pointeur{_C.RESET}")


# =========================
# AFFICHAGE CACHE
# =========================

def _display_cache(cache):
    print()
    print(f"{_C.BOLD}{_C.BG_BLACK}{_C.WHITE}  CACHE  {_C.RESET}")
    print()

    print(f"  {_C.DIM}{'idx':>4}  {'V':>1}  {'tag':>6}  {'data'}{_C.RESET}")

    for i in range(cache.size):
        valid = cache.valid[i]
        tag   = cache.tags[i]
        data  = list(cache.data[i])

        v_sym  = f"{_C.GREEN}✓{_C.RESET}" if valid else f"{_C.RED}✗{_C.RESET}"
        tag_s  = f"{tag:#06x}" if tag >= 0 else "  ----"
        data_s = " ".join(
            f"{_C.WHITE}{b:02x}{_C.RESET}" if b != 0 else f"{_C.DIM}00{_C.RESET}"
            for b in data
        )

        print(f"  {_C.CYAN}{i:>4}{_C.RESET}  {v_sym}  {_C.YELLOW}{tag_s}{_C.RESET}  {data_s}")


# =========================
# MONITEUR PRINCIPAL
# =========================

class Monitor:
    """
    Moniteur temps réel à brancher sur un CPU.

    Usage :
        from monitor import Monitor

        monitor = Monitor(arch, cpu, reg, ram, cache, disc=disc)
        monitor.attach()   # hook automatique sur cpu.step()

        cpu.run()          # chaque step affiche l'état complet
    """

    def __init__(
        self,
        arch,
        cpu,
        reg,
        ram,
        cache,
        disc=None,
        show_ram=True,
        show_cache=True,
        show_disc=True,
        step_by_step=False,
    ):
        self.arch         = arch
        self.cpu          = cpu
        self.reg          = reg
        self.ram          = ram
        self.cache        = cache
        self.disc         = disc
        self.show_ram     = show_ram
        self.show_cache   = show_cache
        self.show_disc    = show_disc
        self.step_by_step = step_by_step  # pause après chaque step (appui Entrée)
        self._step_count  = 0
        self._original_step = None

    # -----------------------------------------------

    def attach(self):
        """Remplace cpu.step() par une version instrumentée."""
        self._original_step = self.cpu.step

        monitor = self  # référence capturée dans la closure

        def instrumented_step():
            monitor._original_step()
            monitor._step_count += 1
            monitor.display()
            if monitor.step_by_step:
                input(f"\n  {_C.DIM}[Entrée pour continuer...]{_C.RESET} ")

        self.cpu.step = instrumented_step

    def detach(self):
        """Restaure le cpu.step() original."""
        if self._original_step:
            self.cpu.step = self._original_step

    # -----------------------------------------------

    def display(self):
        _clear()

        width = 60
        print()
        print(f"{_C.BOLD}{_C.BG_BLUE}{_C.WHITE}{'':=<{width}}{_C.RESET}")
        print(f"{_C.BOLD}{_C.BG_BLUE}{_C.WHITE}{'  MONITEUR CPU — STEP #' + str(self._step_count):<{width}}{_C.RESET}")
        print(f"{_C.BOLD}{_C.BG_BLUE}{_C.WHITE}{'':=<{width}}{_C.RESET}")
        print()

        _display_registers(self.reg, self.arch)
        _display_flags(self.reg)

        if self.show_cache:
            _display_cache(self.cache)

        if self.show_disc and self.disc is not None:
            _display_disc(self.disc)

        if self.show_ram:
            _display_ram(self.ram)

        print()
        print(f"  {_C.DIM}running = {self.cpu.running}{_C.RESET}")
        print()