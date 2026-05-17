import time

def _throttle(delay: float):
    """Introduit un délai si delay > 0 (simule une vitesse limitée)."""
    if delay > 0:
        time.sleep(delay)

class DISC:
    def __init__(self, arch: Architecture, size=256, mem_speed=0):
        self.arch = arch
        self.size = size
        self.memory = bytearray([0] * size)
        self.pointer = 0  # pointeur interne
        self._mem_delay = (1.0 / mem_speed) if mem_speed > 0 else 0

    # écrire toute la ROM (initialisation)
    def set_all(self, data: bytes):
        length = min(len(data), self.size)
        self.memory[:length] = data[:length]

    # récupérer toute la ROM
    def get_all(self) -> bytes:
        return bytes(self.memory)

    # écrire à une adresse (mode "flash")
    def write(self, address: int, data: bytes):
        _throttle(self._mem_delay)
        address = self.arch.normalize_address(address)
        for i, b in enumerate(data):
            if 0 <= address + i < self.size:
                self.memory[address + i] = self.arch.normalize(b)

    # lecture avec pointeur
    def read(self, size: int = 1) -> bytes:
        _throttle(self._mem_delay)
        data = self.memory[self.pointer:self.pointer + size]
        self.pointer += size
        self.pointer %= self.size
        return bytes(data)

    # lecture directe à une adresse
    def read_at(self, address: int, size: int) -> bytes:
        _throttle(self._mem_delay)
        address = self.arch.normalize_address(address)
        return bytes(self.memory[address:address + size])

    # gestion du pointeur
    def seek(self, address: int):
        self.pointer = self.arch.normalize_address(address) % self.size

    def reset(self):
        self.pointer = 0


class RAM:
    def __init__(self, arch: Architecture, size=256, mem_speed=0):
        self.arch = arch
        self.size = size
        self.memory = bytearray([0] * size)
        self.pointer = 0  # pointeur interne (optionnel)
        self._mem_delay = (1.0 / mem_speed) if mem_speed > 0 else 0

    # écrire un byte à une adresse
    def write(self, address: int, value: int):
        _throttle(self._mem_delay)
        address = self.arch.normalize_address(address)
        if 0 <= address < self.size:
            self.memory[address] = self.arch.normalize(value)

    # écrire plusieurs bytes
    def write_block(self, address: int, data: bytes):
        _throttle(self._mem_delay)
        address = self.arch.normalize_address(address)
        for i, b in enumerate(data):
            if 0 <= address + i < self.size:
                self.memory[address + i] = self.arch.normalize(b)

    # lire un byte
    def read(self, address: int) -> int:
        _throttle(self._mem_delay)
        address = self.arch.normalize_address(address)
        if 0 <= address < self.size:
            return self.memory[address]
        return 0

    # lire plusieurs bytes
    def read_block(self, address: int, size: int) -> bytes:
        _throttle(self._mem_delay)
        address = self.arch.normalize_address(address)
        end = min(address + size, self.size)
        return bytes(self.memory[address:end])

    # pointeur interne (utile pour certains modes CPU)
    def seek(self, address: int):
        self.pointer = self.arch.normalize_address(address) % self.size

    def read_ptr(self, size: int = 1) -> bytes:
        data = self.read_block(self.pointer, size)
        self.pointer = self.arch.normalize_address(self.pointer + size) % self.size
        return data

    # reset RAM
    def clear(self):
        for i in range(self.size):
            self.memory[i] = 0


class Cache:
    def __init__(self, arch: Architecture, size=32, line_size=4, mem_speed=0):
        self.arch = arch
        self.size = size
        self.line_size = line_size

        # cache lines
        self.data = [bytearray(line_size) for _ in range(size)]
        self.tags = [-1] * size
        self.valid = [False] * size
        self._mem_delay = (1.0 / mem_speed) if mem_speed > 0 else 0

    # calcul index cache
    def _index(self, address):
        address = self.arch.normalize_address(address)
        return (address // self.line_size) % self.size

    # tag mémoire
    def _tag(self, address):
        address = self.arch.normalize_address(address)
        return address // self.line_size

    # lecture d'un byte
    def read(self, address):
        _throttle(self._mem_delay)
        index = self._index(address)
        tag = self._tag(address)

        if not self.valid[index] or self.tags[index] != tag:
            return 0

        offset = self.arch.normalize_address(address) % self.line_size
        return self.data[index][offset]

    # écriture indépendante
    def write(self, address, value):
        _throttle(self._mem_delay)
        index = self._index(address)
        tag = self._tag(address)

        if not self.valid[index] or self.tags[index] != tag:
            self.valid[index] = True
            self.tags[index] = tag
            for i in range(self.line_size):
                self.data[index][i] = 0

        offset = self.arch.normalize_address(address) % self.line_size
        self.data[index][offset] = self.arch.normalize(value)

    # debug cache
    def dump(self):
        for i in range(self.size):
            print(i, self.valid[i], self.tags[i], list(self.data[i]))

class Registers:
    def __init__(self, arch: Architecture, mem_speed=0):
        self.arch = arch

        # registres généraux
        self.R = [0] * arch.registers_count

        # registres spéciaux
        # PC et SP sont des adresses → address_mask
        # IR stocke une instruction (donnée) → data_mask
        self.PC = 0
        self.SP = arch.address_mask   # valeur initiale = adresse maximale (ex : 0xFF pour 8 bits)
        self.IR = 0
        self.FLAGS = 0
        self._mem_delay = (1.0 / mem_speed) if mem_speed > 0 else 0

    # =========================
    # accès registres généraux
    # =========================

    def read(self, index: int) -> int:
        _throttle(self._mem_delay)
        return self.R[index & (self.arch.registers_count - 1)]

    def write(self, index: int, value: int):
        _throttle(self._mem_delay)
        self.R[index & (self.arch.registers_count - 1)] = value & self.arch.data_mask

    # =========================
    # PC (Program Counter)
    # =========================

    def set_pc(self, value: int):
        self.PC = value & self.arch.address_mask

    def get_pc(self) -> int:
        return self.PC

    def inc_pc(self):
        self.PC = (self.PC + 1) & self.arch.address_mask

    # =========================
    # SP (Stack Pointer)
    # =========================

    def set_sp(self, value: int):
        self.SP = value & self.arch.address_mask

    def get_sp(self) -> int:
        return self.SP

    def push_sp(self):
        self.SP = (self.SP - 1) & self.arch.address_mask

    def pop_sp(self):
        self.SP = (self.SP + 1) & self.arch.address_mask

    # =========================
    # IR (instruction register)
    # =========================

    def set_ir(self, value: int):
        self.IR = value & self.arch.data_mask

    def get_ir(self) -> int:
        return self.IR

    # =========================
    # FLAGS
    # =========================

    def set_flag(self, bit: int, value: bool):
        if value:
            self.FLAGS |= (1 << bit)
        else:
            self.FLAGS &= ~(1 << bit)

    def get_flag(self, bit: int) -> bool:
        return (self.FLAGS >> bit) & 1

    def reset_flags(self):
        self.FLAGS = 0


class ALU:
    def __init__(self, arch: Architecture, registers: Registers):
        self.arch = arch
        self.reg = registers

    # =========================
    # utilitaires flags
    # =========================

    def _set_flags(self, result, carry=False, overflow=False):
        self.reg.set_flag(0, (result & self.arch.data_mask) == 0)   # Z
        self.reg.set_flag(1, carry)                                  # C
        self.reg.set_flag(2, (result & self.arch.sign_bit) != 0)    # N
        self.reg.set_flag(3, overflow)                               # O

    # =========================
    # ADDITION
    # =========================

    def add(self, a, b):
        result = a + b
        carry = result > self.arch.data_mask
        result &= self.arch.data_mask

        overflow = (~(a ^ b) & (a ^ result) & self.arch.sign_bit) != 0

        self._set_flags(result, carry, overflow)
        return result

    # =========================
    # SOUSTRACTION
    # =========================

    def sub(self, a, b):
        result = a - b
        carry = result < 0

        result &= self.arch.data_mask

        overflow = ((a ^ b) & (a ^ result) & self.arch.sign_bit) != 0

        self._set_flags(result, carry, overflow)
        return result

    # =========================
    # MULTIPLICATION
    # =========================

    def mul(self, a, b):
        result = 0
        carry = False

        while b > 0:
            if b & 1:
                result += a

            a <<= 1
            b >>= 1

            if result > self.arch.data_mask:
                carry = True

        result &= self.arch.data_mask
        self._set_flags(result, carry)
        return result

    # =========================
    # DIVISION
    # =========================

    def div(self, a, b):
        if b == 0:
            self._set_flags(0, carry=True)
            return 0

        quotient = 0
        remainder = a

        while remainder >= b:
            remainder -= b
            quotient += 1

        self._set_flags(quotient)
        return quotient

    # =========================
    # COMPARAISON
    # =========================

    def cmp(self, a, b):
        result = (a - b) & self.arch.data_mask

        self.reg.set_flag(0, a == b)                          # Z
        self.reg.set_flag(1, a < b)                           # C
        self.reg.set_flag(2, bool(result & self.arch.sign_bit))  # N

    # =========================
    # AND / OR / XOR / NOT
    # =========================

    def and_op(self, a, b):
        result = a & b
        self._set_flags(result)
        return result

    def or_op(self, a, b):
        result = a | b
        self._set_flags(result)
        return result

    def xor_op(self, a, b):
        result = a ^ b
        self._set_flags(result)
        return result

    def not_op(self, a):
        result = (~a) & self.arch.data_mask
        self._set_flags(result)
        return result

class IOController:
    def __init__(self, arch: Architecture):
        self.arch = arch
        # Dictionnaire pour lier un port à des fonctions de lecture/écriture
        self.ports = {}

    def connect_device(self, port: int, read_callback=None, write_callback=None):
        """Branche un périphérique sur un port donné."""
        self.ports[port] = {'read': read_callback, 'write': write_callback}

    def read(self, port: int) -> int:
        device = self.ports.get(port)
        if device and device['read']:
            return self.arch.normalize(device['read']())
        return 0  # Retourne 0 si rien n'est branché ou lisible

    def write(self, port: int, value: int):
        device = self.ports.get(port)
        if device and device['write']:
            device['write'](self.arch.normalize(value))
    
class VRAM:
    def __init__(self, width=16, height=16, mem_speed=0):
        self.width = width
        self.height = height
        # 3 octets par pixel (RGB)
        self.buffer = bytearray([0] * (width * height * 3))
        self._mem_delay = (1.0 / mem_speed) if mem_speed > 0 else 0

    def write_pixel(self, x, y, r, g, b):
        _throttle(self._mem_delay)
        if 0 <= x < self.width and 0 <= y < self.height:
            base = (y * self.width + x) * 3
            self.buffer[base] = r
            self.buffer[base+1] = g
            self.buffer[base+2] = b

    def clear(self):
        for i in range(len(self.buffer)):
            self.buffer[i] = 0

class GPU:
    """
    Le GPU possède ses propres registres internes pour éviter au CPU 
    de renvoyer les coordonnées à chaque fois.
    """
    def __init__(self, width=16, height=16, mem_speed=0):
        self.vram = VRAM(width, height, mem_speed=mem_speed)
        # Registres internes du GPU
        self.reg_x = 0
        self.reg_y = 0
        self.reg_r = 0
        self.reg_g = 0
        self.reg_b = 0
        
        # Callback pour mettre à jour l'affichage PyQt
        self.on_render = None 

    def handle_command(self, port, value):
        """
        Le GPU écoute sur plusieurs ports (adresses de registres GPU)
        """
        if port == 0x10: self.reg_x = value
        elif port == 0x11: self.reg_y = value
        elif port == 0x12: self.reg_r = value
        elif port == 0x13: self.reg_g = value
        elif port == 0x14: self.reg_b = value
        elif port == 0x15:
            if value == 1: # Commande 1 : DRAW_PIXEL
                self.vram.write_pixel(self.reg_x, self.reg_y, self.reg_r, self.reg_g, self.reg_b)
            elif value == 2: # Commande 2 : CLEAR_SCREEN
                self.vram.clear()
            
            # On prévient l'interface qu'il faut redessiner
            if self.on_render:
                self.on_render(self.vram.buffer)
            
class CPU:
    def __init__(self, arch: Architecture, ram, rom, cache, reg: Registers, alu: ALU, io_ctrl: IOController, cpu_speed=0):
        self.arch = arch
        self.ram = ram
        self.rom = rom
        self.cache = cache
        self.reg = reg
        self.alu = alu
        self.io = io_ctrl
        self.running = True
        self._cpu_delay = (1.0 / cpu_speed) if cpu_speed > 0 else 0

    # =========================
    # FETCH
    # =========================

    def fetch(self):
        pc = self.reg.get_pc()
        val = self.cache.read(pc)
        self.reg.inc_pc()
        return val

    # =========================
    # EXECUTE (simplifié)
    # =========================

    def step(self):
        opcode = self.fetch()

        self.reg.set_ir(opcode)
        
        # --- SYSTÈME & CONTRÔLE ---
        if opcode == 0x00:   # NOP
            pass
        elif opcode == 0xFF: # HLT
            self.running = False

        # --- TRANSFERT DE DONNÉES ---
        elif opcode == 0x10: # MOV Rn, Rm (Copie registre vers registre)
            r1, r2 = self.fetch(), self.fetch()
            self.reg.write(r1, self.reg.read(r2))
        elif opcode == 0x11: # MOV Rn, imm (Chargement immédiat)
            r1, val = self.fetch(), self.fetch()
            self.reg.write(r1, val)
        elif opcode == 0x12: # LOAD Rn, [addr] (Lecture RAM)
            r1, addr = self.fetch(), self.fetch()
            self.reg.write(r1, self.ram.read(addr))
        elif opcode == 0x13: # STORE [addr], Rn (Écriture RAM)
            addr, r1 = self.fetch(), self.fetch()
            self.ram.write(addr, self.reg.read(r1))

        # --- ARITHMÉTIQUE (ALU) ---
        elif opcode == 0x20: # ADD Rn, Rm
            r1, r2 = self.fetch(), self.fetch()
            self.reg.write(r1, self.alu.add(self.reg.read(r1), self.reg.read(r2)))
        elif opcode == 0x22: # SUB Rn, Rm
            r1, r2 = self.fetch(), self.fetch()
            self.reg.write(r1, self.alu.sub(self.reg.read(r1), self.reg.read(r2)))
        elif opcode == 0x26: # MUL Rn, Rm
            r1, r2 = self.fetch(), self.fetch()
            self.reg.write(r1, self.alu.mul(self.reg.read(r1), self.reg.read(r2)))
        elif opcode == 0x28: # CMP Rn, Rm (Compare sans modifier Rn)
            r1, r2 = self.fetch(), self.fetch()
            self.alu.cmp(self.reg.read(r1), self.reg.read(r2))
        elif opcode == 0x29: # CMP Rn, imm (Compare immédiat sans modifier Rn)
            r1, imm = self.fetch(), self.fetch()
            self.alu.cmp(self.reg.read(r1), imm)

        # --- LOGIQUE ---
        elif opcode == 0x30: # AND Rn, Rm
            r1, r2 = self.fetch(), self.fetch()
            self.reg.write(r1, self.alu.and_op(self.reg.read(r1), self.reg.read(r2)))
        elif opcode == 0x31: # OR Rn, Rm
            r1, r2 = self.fetch(), self.fetch()
            self.reg.write(r1, self.alu.or_op(self.reg.read(r1), self.reg.read(r2)))
        elif opcode == 0x33: # NOT Rn
            r1 = self.fetch()
            self.reg.write(r1, self.alu.not_op(self.reg.read(r1)))

        # --- BRANCHEMENTS (CONTROL FLOW) ---
        elif opcode == 0x40: # JMP addr (Saut inconditionnel)
            self.reg.set_pc(self.fetch())
        elif opcode == 0x41: # JZ addr (Saut si Z=1 / Égalité)
            addr = self.fetch()
            if self.reg.get_flag(0): self.reg.set_pc(addr)
        elif opcode == 0x42: # JNZ addr (Saut si Z=0 / Différent)
            addr = self.fetch()
            if not self.reg.get_flag(0): self.reg.set_pc(addr)
        elif opcode == 0x43: # JC addr (Saut si Z=1 / Égalité)
            addr = self.fetch()
            if self.reg.get_flag(1): self.reg.set_pc(addr)
        elif opcode == 0x44: # JNC addr (Saut si Z=0 / Différent)
            addr = self.fetch()
            if not self.reg.get_flag(1): self.reg.set_pc(addr)
        elif opcode == 0x45: # JN addr (Saut si Z=1 / Égalité)
            addr = self.fetch()
            if self.reg.get_flag(2): self.reg.set_pc(addr)
        elif opcode == 0x46: # JNN addr (Saut si Z=0 / Différent)
            addr = self.fetch()
            if not self.reg.get_flag(2): self.reg.set_pc(addr)
        elif opcode == 0x47: # JO addr (Saut si Z=1 / Égalité)
            addr = self.fetch()
            if self.reg.get_flag(3): self.reg.set_pc(addr)
        elif opcode == 0x48: # JNO addr (Saut si Z=0 / Différent)
            addr = self.fetch()
            if not self.reg.get_flag(3): self.reg.set_pc(addr)

        # --- PILE (STACK) ---
        elif opcode == 0x50: # PUSH Rn
            r1 = self.fetch()
            self.ram.write(self.reg.get_sp(), self.reg.read(r1))
            self.reg.push_sp()
        elif opcode == 0x51: # POP Rn
            r1 = self.fetch()
            self.reg.pop_sp()
            val = self.ram.read(self.reg.get_sp())
            self.reg.write(r1, val)
        
        # --- ENTRÉES / SORTIES (I/O) ---
        elif opcode == 0x60: # IN Rn, port (Lit le port et stocke dans Rn)
            r1 = self.fetch()
            port = self.fetch()
            val = self.io.read(port)
            self.reg.write(r1, val)

        elif opcode == 0x61: # OUT port, Rn (Écrit la valeur de Rn sur le port)
            port = self.fetch()
            r1 = self.fetch()
            self.io.write(port, self.reg.read(r1))
        
        # --- ENTRÉES / SORTIES DIRECTES (MÉMOIRE) ---
        
        elif opcode == 0x62: # IN_RAM addr, port (Lit le port et écrit dans la RAM)
            addr = self.fetch()
            port = self.fetch()
            self.ram.write(addr, self.io.read(port))
        
        elif opcode == 0x63: # OUT_RAM port, addr (Envoie la valeur de la RAM au port)
            port = self.fetch()
            addr = self.fetch()
            self.io.write(port, self.ram.read(addr))

        elif opcode == 0x64: # IN_CACHE addr, port (Lit le port et écrit dans le Cache)
            addr = self.fetch()
            port = self.fetch()
            self.cache.write(addr, self.io.read(port))
            

        elif opcode == 0x65: # OUT_CACHE port, addr (Envoie la valeur du Cache au port)
            port = self.fetch()
            addr = self.fetch()
            self.io.write(port, self.cache.read(addr))
        
        # --- 1. SOUS-ROUTINES (FONCTIONS) ---
        if opcode == 0x49: # CALL addr
            addr = self.fetch()
            # On pousse l'adresse de l'instruction SUIVANTE sur la pile
            self.ram.write(self.reg.get_sp(), self.reg.get_pc())
            self.reg.push_sp()
            # On saute à l'adresse de la fonction
            self.reg.set_pc(addr)

        elif opcode == 0x4A: # RET
            # On récupère l'adresse de retour depuis la pile
            self.reg.pop_sp()
            ret_addr = self.ram.read(self.reg.get_sp())
            self.reg.set_pc(ret_addr)

        # --- 2. MODES D'ADRESSAGE FLEXIBLES ---
        elif opcode == 0x14: # LOAD Rn, [Rm] (Indirect)
            r1, r2 = self.fetch(), self.fetch()
            address = self.reg.read(r2)
            self.reg.write(r1, self.ram.read(address))

        elif opcode == 0x15: # MOV Rn, [Rm + offset]
            r1, r2, offset = self.fetch(), self.fetch(), self.fetch()
            address = (self.reg.read(r2) + offset) & self.arch.address_mask
            self.reg.write(r1, self.ram.read(address))

        # --- 3. OPÉRATIONS IMMÉDIATES ---
        elif opcode == 0x21: # ADDI Rn, imm
            r1, imm = self.fetch(), self.fetch()
            self.reg.write(r1, self.alu.add(self.reg.read(r1), imm))

        elif opcode == 0x32: # ANDI Rn, imm
            r1, imm = self.fetch(), self.fetch()
            self.reg.write(r1, self.alu.and_op(self.reg.read(r1), imm))

        # --- 4. GESTION DU CACHE (TRANSFERTS INTERNES) ---
        elif opcode == 0x70: # MTC_REG (Move To Cache from Reg) : CACHE[addr] = Rn
            addr, r1 = self.fetch(), self.fetch()
            self.cache.write(addr, self.reg.read(r1))

        elif opcode == 0x71: # MTC_RAM (Move To Cache from RAM) : CACHE[addr] = RAM[addr]
            addr = self.fetch()
            val = self.ram.read(addr)
            self.cache.write(addr, val)

        elif opcode == 0x72: # MFC (Move From Cache) : Rn = CACHE[addr]
            r1, addr = self.fetch(), self.fetch()
            self.reg.write(r1, self.cache.read(addr))

        # --- 5. ARITHMÉTIQUE ÉTENDUE ---
        elif opcode == 0x27: # XOR Rn, Rm
            r1, r2 = self.fetch(), self.fetch()
            self.reg.write(r1, self.alu.xor_op(self.reg.read(r1), self.reg.read(r2)))

        elif opcode == 0x34: # SHL Rn (Shift Left)
            r1 = self.fetch()
            val = self.reg.read(r1) << 1
            # Mise à jour manuelle des flags ou via une nouvelle méthode ALU
            carry = val > self.arch.data_mask
            val &= self.arch.data_mask
            self.reg.write(r1, val)
            self.alu._set_flags(val, carry=carry)

        elif opcode == 0x35: # SHR Rn (Shift Right)
            r1 = self.fetch()
            val = self.reg.read(r1) >> 1
            self.reg.write(r1, val)
            self.alu._set_flags(val)
                
    # =========================
    # RUN LOOP
    # =========================

    def run(self):
        while self.running:
            self.step()
            _throttle(self._cpu_delay)

class Architecture:
    def __init__(
        self,
        data_bytes=1,
        address_bytes=2,
        registers_count=8,
        little_endian=True
    ):

        # =========================
        # TAILLE DES DONNÉES
        # =========================

        self.data_bytes = data_bytes
        self.data_bits = data_bytes * 8

        # masque max
        self.data_mask = (1 << self.data_bits) - 1

        # bit de signe
        self.sign_bit = 1 << (self.data_bits - 1)

        # =========================
        # TAILLE DES ADRESSES
        # =========================

        self.address_bytes = address_bytes
        self.address_bits = address_bytes * 8

        self.address_mask = (1 << self.address_bits) - 1

        self.max_address = self.address_mask

        # =========================
        # REGISTRES
        # =========================

        self.registers_count = registers_count

        # =========================
        # ENDIANNESS
        # =========================

        self.little_endian = little_endian

    # =========================
    # UTILITAIRES
    # =========================

    def normalize(self, value):
        return value & self.data_mask

    def normalize_address(self, value):
        return value & self.address_mask

    def is_negative(self, value):
        return (value & self.sign_bit) != 0

    def max_signed(self):
        return (1 << (self.data_bits - 1)) - 1

    def min_signed(self):
        return -(1 << (self.data_bits - 1))

    def info(self):
        print("===== ARCHITECTURE =====")
        print(f"Data           : {self.data_bits} bits")
        print(f"Addresses      : {self.address_bits} bits")
        print(f"Registers      : {self.registers_count}")
        print(f"Endianness     : {'Little' if self.little_endian else 'Big'}")
        print(f"Data mask      : {hex(self.data_mask)}")
        print(f"Address mask   : {hex(self.address_mask)}")
        print("========================")