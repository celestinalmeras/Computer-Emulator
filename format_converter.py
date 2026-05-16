import re

# ==============================================================================
#  ASSEMBLER (ASM -> HEX/BIN)
# ==============================================================================

def assembler_v4(asm_code, to="hex", data_bytes=1, address_bytes=1):
    opcodes = {
        "NOP": "00", "HLT": "FF", "ADD": "20", "ADDI": "21", "SUB": "22", 
        "MUL": "26", "XOR": "27", "AND": "30", "OR": "31", 
        "ANDI": "32", "NOT": "33", "SHL": "34", "SHR": "35", "JMP": "40", 
        "JZ": "41", "JNZ": "42", "JC": "43", "JNC": "44", "JN": "45", 
        "JNN": "46", "JO": "47", "JNO": "48", "CALL": "49", "RET": "4A", 
        "PUSH": "50", "POP": "51", "IN": "60", "OUT": "61", "IN_RAM": "62", 
        "OUT_RAM": "63", "IN_CACHE": "64", "OUT_CACHE": "65", "MTC_REG": "70", 
        "MTC_RAM": "71", "MFC": "72", "STORE": "13"
    }

    # Définition des types d'instructions pour calculer la taille automatiquement
    # (Opcode toujours 1 byte)
    ADDR_INSTR = ["JMP", "JZ", "JNZ", "JC", "JNC", "JN", "JNN", "JO", "JNO", "CALL", "LOAD", "STORE"]
    DATA_INSTR = ["ADDI", "ANDI", "MOV", "MTC_REG", "MFC", "CMP"] # Instructions avec immédiat
    REG_ONLY_2 = ["ADD", "SUB", "MUL", "XOR", "AND", "OR", "IN", "OUT", "IN_RAM", "OUT_RAM", "IN_CACHE", "OUT_CACHE"]
    REG_ONLY_1 = ["PUSH", "POP", "NOT", "SHL", "SHR"]

    lines = []
    labels = {}
    current_address = 0
    raw_lines = asm_code.strip().split('\n')
    
    # 1. Calcul des adresses et repérage des labels
    temp_program = []
    for line in raw_lines:
        line = line.split(';')[0].strip()
        if not line: continue
        
        if line.endswith(':'):
            labels[line[:-1].upper()] = current_address
            continue

        parts = re.split(r'[ ,\t]+', line)
        instr = parts[0].upper()
        
        # Calcul dynamique de la taille
        size = 1 # Opcode
        if instr in ADDR_INSTR:
            # Si LOAD/STORE/MOV avec registre + adresse : Opcode + Reg + Adresse
            size += 1 + address_bytes if instr in ["LOAD", "STORE"] else address_bytes
        elif instr == "MOV" and "+" in line: size += 1 + 1 + data_bytes # Rd, [Rb+Off]
        elif instr in DATA_INSTR: size += 1 + data_bytes # Rd, Imm
        elif instr in REG_ONLY_2: size += 2 # Rd, Rs
        elif instr in REG_ONLY_1: size += 1 # Rd
        elif instr == "MTC_RAM": size += 1 # Port hex
            
        temp_program.append((line, current_address, instr))
        current_address += size

    # 2. Traduction
    hex_output = []
    for line_text, addr, instr in temp_program:
        parts = re.split(r'[ ,\t]+', line_text)
        args = parts[1:]
        
        # Détermination de l'opcode
        if instr == "MOV":
            if "+" in line_text: opcode = "15"
            elif args[1].upper().startswith('R'): opcode = "10"
            else: opcode = "11"
        elif instr == "LOAD":
            opcode = "14" if args[1].startswith('[R') else "12"
        elif instr == "CMP":
            opcode = "28" if args[1].upper().startswith('R') else "29"
        else:
            opcode = opcodes.get(instr, "00")

        line_hex = [opcode]

        for i, arg in enumerate(args):
            arg_clean = arg.upper().replace('[', '').replace(']', '').replace('+', '').replace('R', '')
            
            if arg.upper() in labels:
                val = labels[arg.upper()]
                # Formater selon address_bytes
                line_hex.append(hex(val)[2:].upper().zfill(address_bytes * 2))
            else:
                try:
                    val = int(arg_clean, 16) if '0X' in arg_clean else int(arg_clean)
                    # Choisir la taille de l'encodage
                    if instr in ADDR_INSTR and i == len(args)-1:
                        line_hex.append(hex(val)[2:].upper().zfill(address_bytes * 2))
                    elif instr in DATA_INSTR and i == len(args)-1:
                        line_hex.append(hex(val)[2:].upper().zfill(data_bytes * 2))
                    else:
                        # Registres ou ports restent en 1 byte (8-bit)
                        line_hex.append(hex(val)[2:].upper().zfill(2))
                except:
                    if arg_clean.isdigit(): line_hex.append(arg_clean.zfill(2))

        hex_output.append(" ".join(line_hex))

    full_hex = " ".join(hex_output)
    if to == "bin":
        return " ".join(format(int(x, 16), f"0{len(x)*4}b") for x in full_hex.split())
    return full_hex

# ==============================================================================
#  DISASSEMBLER (HEX -> ASM)
# ==============================================================================
 
def disassembler_v4(input_data, base_address=0, data_bytes=1, address_bytes=1, from_="hex"):
    if from_ == "bin":
        # Gestion des tailles binaires variables
        input_data = " ".join(hex(int(b, 2))[2:].upper().zfill(2) for b in input_data.split())
    
    try:
        program = [int(b, 16) for b in input_data.strip().split()]
    except:
        return "Erreur de parsing"
 
    # Définition des instructions : (Nom, [Types])
    # 'R' = Registre (1 octet), 'I' = Immédit (data_bytes), 'A' = Adresse (address_bytes), 'H' = Port (1 octet)
    INSTR = {
        0x00: ('NOP', []), 0xFF: ('HLT', []), 0x4A: ('RET', []),
        0x10: ('MOV', ['R', 'R']), 0x11: ('MOV', ['R', 'I']), 0x12: ('LOAD', ['R', 'A']),
        0x13: ('STORE', ['R', 'A']), 0x14: ('LOAD', ['R', '[R]']), 0x15: ('MOV', ['R', 'R', 'I']),
        0x20: ('ADD', ['R', 'R']), 0x21: ('ADDI', ['R', 'I']), 0x22: ('SUB', ['R', 'R']),
        0x26: ('MUL', ['R', 'R']), 0x27: ('XOR', ['R', 'R']), 0x28: ('CMP', ['R', 'R']), 0x29: ('CMP', ['R', 'I']),
        0x30: ('AND', ['R', 'R']), 0x31: ('OR', ['R', 'R']), 0x32: ('ANDI', ['R', 'I']),
        0x33: ('NOT', ['R']), 0x34: ('SHL', ['R']), 0x35: ('SHR', ['R']),
        0x40: ('JMP', ['A']), 0x41: ('JZ', ['A']), 0x42: ('JNZ', ['A']),
        0x43: ('JC', ['A']), 0x44: ('JNC', ['A']), 0x45: ('JN', ['A']),
        0x46: ('JNN', ['A']), 0x47: ('JO', ['A']), 0x48: ('JNO', ['A']),
        0x49: ('CALL', ['A']), 0x50: ('PUSH', ['R']), 0x51: ('POP', ['R']),
        0x60: ('IN', ['H', 'R']), 0x61: ('OUT', ['H', 'R']), 0x62: ('IN_RAM', ['H', 'R']),
        0x63: ('OUT_RAM', ['H', 'R']), 0x64: ('IN_CACHE', ['H', 'R']), 0x65: ('OUT_CACHE', ['H', 'R']),
        0x70: ('MTC_REG', ['R', 'I']), 0x71: ('MTC_RAM', ['H']), 0x72: ('MFC', ['R', 'I']),
    }
 
    # 1. Pour les labels
    jump_targets = set()
    pc = 0
    while pc < len(program):
        op = program[pc]
        if op in INSTR:
            name, fmt = INSTR[op]
            temp_pc = pc + 1
            for t in fmt:
                if t == 'A':
                    val = 0
                    for b in range(address_bytes):
                        val = (val << 8) | program[temp_pc + b]
                    jump_targets.add(val + base_address)
                temp_pc += address_bytes if t == 'A' else (data_bytes if t == 'I' else 1)
            pc = temp_pc
        else: pc += 1
 
    label_map = {addr: f"LABEL_{i}" for i, addr in enumerate(sorted(jump_targets))}
 
    # 2. Désassemblage
    asm_lines = []
    pc = 0
    while pc < len(program):
        cur_addr = pc + base_address
        if cur_addr in label_map: asm_lines.append(f"{label_map[cur_addr]}:")
 
        op = program[pc]
        if op not in INSTR:
            asm_lines.append(f"    DB 0x{op:02X}")
            pc += 1
            continue
 
        mnemonic, fmt = INSTR[op]
        pc += 1
        ops = []
        
        for t in fmt:
            if t == 'R':
                ops.append(f"R{program[pc]}")
                pc += 1
            elif t == 'I':
                val = 0
                for _ in range(data_bytes):
                    val = (val << 8) | program[pc]
                    pc += 1
                ops.append(str(val))
            elif t == 'A':
                val = 0
                for _ in range(address_bytes):
                    val = (val << 8) | program[pc]
                    pc += 1
                ops.append(label_map.get(val + base_address, f"0x{val:0X}"))
            elif t == 'H':
                ops.append(f"0x{program[pc]:02X}")
                pc += 1
            elif t == '[R]':
                ops.append(f"[R{program[pc]}]")
                pc += 1

        # Cas spécial pour MOV Rd, [Rb+Off]
        if op == 0x15:
            line = f"    MOV {ops[0]}, [R{ops[1]}+{ops[2]}]"
        else:
            line = f"    {mnemonic} {', '.join(ops)}".strip()
        
        asm_lines.append(line)
 
    return "\n".join(asm_lines)

def load(path: str) -> str:
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            # supprimer les commentaires et les espaces superflus
            line = raw_line.split(";")[0].strip()
            if not line:
                continue
            
            lines.append(line)

        return "\n".join(lines)
def write(path: str, data: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)

if __name__ == "__main__":
    import argparse
    import os, sys

    parser = argparse.ArgumentParser(
        description="Compilateur et désassembleur"
    )
    
    # Argument positionnel obligatoire
    parser.add_argument("input_file", type=str, help="Chemin du fichier source à convertir")
    
    # Argument optionnel pour spécifier la sortie
    parser.add_argument("-o", "--output", type=str, help="Chemin du fichier de sortie (optionnel)")

    # Choix exclusif de l'action
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-a", "--assemble", action="store_true", help="Assemble un fichier .asm en .hex ou .bin")
    group.add_argument("-d", "--disassemble", action="store_true", help="Désassemble un fichier .hex ou .bin en .asm")

    # Options de configuration de l'architecture
    parser.add_argument("--to", choices=["hex", "bin"], default="hex", help="Format cible de l'assemblage (par défaut: hex)")
    parser.add_argument("--data-bytes", type=int, default=1, help="Nombre d'octets pour les données (par défaut: 1)")
    parser.add_argument("--address-bytes", type=int, default=2, help="Nombre d'octets pour les adresses (par défaut: 2)")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Erreur : Le fichier '{args.input_file}' n'existe pas.")
        sys.exit(1)

    # 1. MODE ASSEMBLAGE (ASM ➔ HEX / BIN)
    if args.assemble:
        print(f"Assemblage de '{args.input_file}'...")
        try:
            asm_content = load(args.input_file)
            result = assembler_v4(
                asm_content, 
                to=args.to, 
                data_bytes=args.data_bytes, 
                address_bytes=args.address_bytes
            )
            
            # Détermination du fichier de sortie par défaut si non fourni
            output_path = args.output
            if not output_path:
                base, _ = os.path.splitext(args.input_file)
                output_path = f"{base}.{args.to}"
            
            write(output_path, result)
            print(f"Fichier assemblé avec succès dans : {output_path}")
            
        except Exception as e:
            print(f"Erreur lors de l'assemblage : {e}")
            sys.exit(1)

    # 2. MODE DÉSASSEMBLAGE (HEX / BIN -> ASM)
    elif args.disassemble:
        print(f"Désassemblage de '{args.input_file}'...")
        try:
            program_bytes = []
            
            # Lecture intelligente selon l'extension ou le format réel
            _, ext = os.path.splitext(args.input_file).lower()
            
            if ext == ".bin":
                with open(args.input_file, "rb") as f:
                    program_bytes = list(f.read())
            else:
                # On traite le fichier comme du texte contenant des valeurs Hexadécimales
                with open(args.input_file, "r", encoding="utf-8") as f:
                    content = f.read().strip().split()
                # Conversion des tokens "0xAA" ou "AA" en entiers
                program_bytes = [int(token, 16) for token in content if token]

            # Appel du désassembleur
            asm_result = disassembler_v4(
                program_bytes, 
                data_bytes=args.data_bytes, 
                address_bytes=args.address_bytes
            )
            
            # Détermination du fichier de sortie par défaut si non fourni
            output_path = args.output
            if not output_path:
                base, _ = os.path.splitext(args.input_file)
                output_path = f"{base}_disassembled.asm"
                
            write(output_path, asm_result)
            print(f"Fichier désassemblé avec succès dans : {output_path}")
            
        except Exception as e:
            print(f"Erreur lors du désassemblage : {e}")
            sys.exit(1)