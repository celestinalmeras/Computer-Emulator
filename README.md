# Computer Emulator - Complete technical documentation
<img width="1118" height="170" alt="ascii-art-text" src="https://github.com/user-attachments/assets/22818ced-275e-4be4-86ee-3192e66aac3a" />

## Table of Contents
1. [Introduction and Vision](#introduction-and-vision)
2. [Project Architecture](#project-architecture)
3. [Getting Started](#getting-started)
4. [The .pcc Configuration File](#the-pcc-configuration-file)
5. [Usage Modes](#usage-modes)
   - [Command Line Interface (CLI)](#command-line-interface-cli)
   - [GPU Screen Window](#gpu-screen-window)
   - [Qt Debug Monitor](#qt-debug-monitor)
   - [Code Editor](#code-editor)
6. [The Assembler & Disassembler](#the-assembler--disassembler)
7. [Instruction Set Reference](#instruction-set-reference)
8. [IOController & Peripherals](#iocontroller--peripherals)
9. [Performance Profiling](#performance-profiling)
10. [Dependencies](#dependencies)

---

## Introduction and Vision

Computer Emulator is a **modular computer emulator project** designed to be both **easy** to use and **feature-rich**.

### Main Objectives
1. Choosing data size in bytes and address size in bytes for the Von Neumann architecture.
2. Choosing the speed of each component (CPU, RAM, Cache, DISC, Registers, VRAM).
3. Choosing video monitor size and GPU resolution.
4. Mapping I/O ports to hardware devices or Python callbacks.
5. Running programs loaded into Cache, RAM, or DISC from `.hex` or `.bin` files.
6. Monitoring execution in real time — through a terminal, a graphical debugger, or both.

> The project is built around a single configuration file (`.pcc`) that describes the entire virtual machine. Change the file, change the machine.

---

## Project Architecture

```
computer-emulator/
├── emulator.py          # Main entry point — boots the virtual machine
├── computer.py          # Core hardware: CPU, RAM, DISC, Cache, Registers, ALU, GPU, IOController
├── format_converter.py  # Assembler (ASM → HEX/BIN) and Disassembler (HEX/BIN → ASM)
├── monitor.py           # Real-time CLI monitor with ANSI colors (step-by-step or continuous)
├── monitor_qt.py        # Full Qt-based graphical debug interface
├── editor.py            # Integrated code editor for writing and assembling ASM
└── *.pcc                # Your machine configuration files
```

| Module | Role |
|---|---|
| `emulator.py` | Parses the `.pcc` config, wires all components together, starts the CPU |
| `computer.py` | Implements all hardware components |
| `format_converter.py` | Translates between ASM text, hex strings, and binary |
| `monitor.py` | Hooks into `cpu.step()` and pretty-prints state after each instruction |
| `monitor_qt.py` | Full graphical debugger with registers, flags, memory views, and breakpoints |
| `editor.py` | Write ASM, assemble it, and load it directly into the emulator |

---

## Getting Started

### Prerequisites

```bash
pip install PyQt6
```

### Running your first program

1. Write an assembly file (`program.asm`).
2. Assemble it to hex:
   ```bash
   python format_converter.py program.asm -a -o program.hex
   ```
3. Create a `.pcc` config file that loads your hex file.
4. Launch the emulator:
   ```bash
   python emulator.py my_machine.pcc
   ```

---

## The .pcc Configuration File

The `.pcc` file is the **heart of the emulator**. It fully describes the virtual machine: its architecture, component speeds, memory contents, I/O wiring, and display settings. There is no code to change — just edit your `.pcc` and relaunch.

### Full Example

```
Architecture : [
    data_bytes    : 1,
    address_bytes : 2
]

CPUSpeed       : 0
RAMSpeed       : 0
CacheSpeed     : 0
DISCSpeed      : 0
RegistersSpeed : 0
VRAMSpeed      : 0

GPU     : (16, 16)
Monitor : (16, 16)
Scale   : 20

IOController : [
    0x00 - 0x0F : GPU
    0x10        : py.virtual_output()
    0x11        : py.virtual_input()
]

LOAD : [
    Cache : ("os.hex")
    RAM   : ("stdlib.hex", "program.hex")
    DISC  : ("data.hex")
]
```

### Field Reference

#### `Architecture`
Defines the word size of the virtual machine.

| Key | Description |
|---|---|
| `data_bytes` | Size of a data value in bytes (e.g. `1` = 8-bit data) |
| `address_bytes` | Size of a memory address in bytes (e.g. `2` = 16-bit address space) |

#### Component Speeds
Each speed is a delay in milliseconds added after each memory access. Set to `0` for maximum speed.

| Key | Component |
|---|---|
| `CPUSpeed` | CPU clock delay |
| `RAMSpeed` | RAM read/write delay |
| `CacheSpeed` | Cache read/write delay |
| `DISCSpeed` | DISC read/write delay |
| `RegistersSpeed` | Register access delay |
| `VRAMSpeed` | VRAM / GPU access delay |

#### `GPU` and `Monitor`
- `GPU : (width, height)` — internal resolution of the graphics processing unit (in pixels).
- `Monitor : (width, height)` — size of the display window (should match GPU resolution).
- `Scale : N` — pixel scaling factor. A `16x16` monitor with `Scale : 20` opens a `320x320` window.

#### `IOController`
Maps port numbers (or ranges) to devices or Python functions.

```
IOController : [
    0x00 - 0x0F : GPU            ; Ports 0 to 15 → GPU command bus
    0x10        : py.my_output() ; Port 16 → calls virtual_output(value) in emulator.py
    0x11        : py.my_input()  ; Port 17 → calls virtual_input() → returns value to CPU
]
```

Ports can be specified as:
- A single decimal or hex value: `16` or `0x10`
- A range: `0x00 - 0x0F`
- A comma-separated list: `0x10, 0x12, 0x14`

To add a custom Python I/O function, define it in `emulator.py` under the `# --- Fonctions Python pour l'IOController ---` section. Functions that take a parameter are treated as **output** callbacks; functions with no parameters are treated as **input** callbacks.

#### `LOAD`
Specifies which hex files to load into which memory components at startup. Files are loaded **sequentially**, each starting immediately after the previous one.

```
LOAD : [
    Cache : ("boot.hex")
    RAM   : ("stdlib.hex", "program.hex")
    DISC  : ("assets.hex")
]
```

---

## Usage Modes

The emulator supports multiple display modes that can be **combined freely** using command-line flags.

### Command Line Interface (CLI)

Launches the emulator with a real-time terminal monitor. After each CPU instruction, the terminal is cleared and the full machine state is printed: registers, flags, cache, DISC, and RAM (if enabled).

```bash
python emulator.py my_machine.pcc --cli
```

The CLI monitor supports **step-by-step mode**: execution pauses after each instruction and waits for the user to press `Enter`. This is configured when instantiating `Monitor` in code, or enabled by default when passing `--cli`.

Features of the CLI monitor:
- ANSI color output for easy reading
- Displays all general-purpose registers (value + hex + ASCII bar)
- Displays PC, SP, IR, and FLAGS
- Shows Z / C / N / O flag states with symbols
- Dumps Cache, DISC (with pointer highlight), and RAM

### GPU Screen Window

Opens a graphical window showing the output of the virtual GPU. The GPU renders an RGB framebuffer that maps to the pixel grid defined in your `.pcc`.

```bash
python emulator.py my_machine.pcc --screen
```

- The CPU writes to the GPU by sending commands over the IOController ports mapped to `GPU`.
- The window updates in real time as the VRAM is written.
- The CPU runs in a background thread so the display remains responsive.

> If no display flag is specified, `--screen` is enabled by default.

### Qt Debug Monitor

Opens the full graphical debug interface built with PyQt6. This mode is designed for **interactive debugging**: inspect registers, step through instructions, set breakpoints, and visualize memory.

```bash
python emulator.py my_machine.pcc --qt
```

### Combining Modes

Flags are cumulative — you can run all monitors simultaneously:

```bash
# Screen + Qt debugger + CLI, with CPU profiling
python emulator.py my_machine.pcc --screen --qt --cli --profile
```

| Flag | Effect |
|---|---|
| `--screen` | GPU output window |
| `--cli` | Terminal step-by-step monitor |
| `--qt` | Full Qt graphical debugger |
| `--profile` | Run CPU under `cProfile` and print stats |

### Code Editor

The integrated editor (`editor.py`) provides a graphical environment for writing assembly code, assembling it, and loading it directly into a running or new emulator session — without leaving the application.

Launch it as a standalone application:

```bash
python editor.py
```

---

## The Assembler & Disassembler

`format_converter.py` provides two tools: an **assembler** that compiles `.asm` source into `.hex` or `.bin`, and a **disassembler** that reconstructs `.asm` from hex/binary files.

Both tools respect the architecture defined by `--data-bytes` and `--address-bytes`, producing output compatible with your `.pcc` configuration.

### Assembler (ASM → HEX / BIN)

```bash
python format_converter.py program.asm -a
python format_converter.py program.asm -a --to bin
python format_converter.py program.asm -a -o output.hex --data-bytes 2 --address-bytes 2
```

Features:
- **Label support**: define `MY_LABEL:` anywhere and jump to it by name.
- **Automatic instruction sizing**: the assembler computes the byte length of each instruction based on the configured `data_bytes` and `address_bytes`.
- **Flexible immediate formats**: write values as decimal (`42`) or hex (`0x2A`).
- **Comments**: anything after `;` is ignored.

### Disassembler (HEX / BIN → ASM)

```bash
python format_converter.py program.hex -d
python format_converter.py program.bin -d --data-bytes 2 --address-bytes 2 -o restored.asm
```

The disassembler performs a two-pass analysis: it first identifies all jump targets and generates label names (`LABEL_0`, `LABEL_1`, …), then produces clean annotated assembly.

### Options

| Option | Default | Description |
|---|---|---|
| `-a` / `--assemble` | — | Assemble mode |
| `-d` / `--disassemble` | — | Disassemble mode |
| `--to` | `hex` | Output format for assembly: `hex` or `bin` |
| `--data-bytes` | `1` | Bytes per data value |
| `--address-bytes` | `2` | Bytes per address |
| `-o` / `--output` | auto | Output file path |

---

## Instruction Set Reference

A PDF document **[NAME_FILE]** is included in this repository and describes every instruction in detail: its mnemonic, opcode (hex), operands, flags affected, and a description of its behavior. It is the authoritative reference for programming this CPU.

Below is a quick summary of the available instructions by category.

### Data Movement

| Mnemonic | Opcode | Description |
|---|---|---|
| `MOV Rd, Rs` | `10` | Copy register to register |
| `MOV Rd, Imm` | `11` | Load immediate value into register |
| `MOV Rd, [Rb+Off]` | `15` | Load from memory at base register + offset |
| `LOAD Rd, Addr` | `12` | Load from absolute memory address |
| `LOAD Rd, [Rs]` | `14` | Load from address stored in register |
| `STORE Rs, Addr` | `13` | Store register to absolute memory address |
| `PUSH Rs` | `50` | Push register onto stack |
| `POP Rd` | `51` | Pop top of stack into register |

### Arithmetic & Logic

| Mnemonic | Opcode | Description |
|---|---|---|
| `ADD Rd, Rs` | `20` | Rd = Rd + Rs |
| `ADDI Rd, Imm` | `21` | Rd = Rd + Imm |
| `SUB Rd, Rs` | `22` | Rd = Rd − Rs |
| `MUL Rd, Rs` | `26` | Rd = Rd × Rs |
| `AND Rd, Rs` | `30` | Rd = Rd AND Rs |
| `ANDI Rd, Imm` | `32` | Rd = Rd AND Imm |
| `OR Rd, Rs` | `31` | Rd = Rd OR Rs |
| `XOR Rd, Rs` | `27` | Rd = Rd XOR Rs |
| `NOT Rd` | `33` | Rd = NOT Rd |
| `SHL Rd` | `34` | Shift Rd left by 1 |
| `SHR Rd` | `35` | Shift Rd right by 1 |
| `CMP Rd, Rs` | `28` | Set flags from Rd − Rs (no store) |
| `CMP Rd, Imm` | `29` | Set flags from Rd − Imm (no store) |

### Control Flow

| Mnemonic | Opcode | Description |
|---|---|---|
| `JMP Addr` | `40` | Unconditional jump |
| `JZ Addr` | `41` | Jump if Zero flag set |
| `JNZ Addr` | `42` | Jump if Zero flag not set |
| `JC Addr` | `43` | Jump if Carry flag set |
| `JNC Addr` | `44` | Jump if Carry flag not set |
| `JN Addr` | `45` | Jump if Negative flag set |
| `JNN Addr` | `46` | Jump if Negative flag not set |
| `JO Addr` | `47` | Jump if Overflow flag set |
| `JNO Addr` | `48` | Jump if Overflow flag not set |
| `CALL Addr` | `49` | Push PC, jump to subroutine |
| `RET` | `4A` | Pop PC, return from subroutine |

### I/O

| Mnemonic | Opcode | Description |
|---|---|---|
| `IN Port, Rd` | `60` | Read from I/O port into register |
| `OUT Port, Rs` | `61` | Write register to I/O port |
| `IN_RAM Port, Rd` | `62` | Read from I/O port into RAM address stored in Rd |
| `OUT_RAM Port, Rs` | `63` | Write from RAM address stored in Rs to I/O port |
| `IN_CACHE Port, Rd` | `64` | Read from I/O port into Cache |
| `OUT_CACHE Port, Rs` | `65` | Write from Cache to I/O port |

### Cache Control

| Mnemonic | Opcode | Description |
|---|---|---|
| `MTC_REG Rd, Imm` | `70` | Move To Cache from register at cache line Imm |
| `MTC_RAM Port` | `71` | Move To Cache from RAM |
| `MFC Rd, Imm` | `72` | Move From Cache line Imm into register Rd |

### Misc

| Mnemonic | Opcode | Description |
|---|---|---|
| `NOP` | `00` | No operation |
| `HLT` | `FF` | Halt the CPU |

> For full details on operand encoding, flag effects, and cycle costs, refer to **[NAME_FILE]**.

---

## IOController & Peripherals

The `IOController` is the bridge between the CPU and the outside world. It maintains a port map where each port number is associated with a read callback, a write callback, or both.

### Built-in: GPU

When ports are mapped to `GPU` in the `.pcc`, `OUT` instructions on those ports are forwarded to the GPU's command handler. The GPU interprets the values as drawing commands (pixel color, position, render trigger, etc.) and updates the VRAM framebuffer, which is then rendered in the screen window.

### Custom Python Callbacks

You can wire any port to a Python function defined in `emulator.py`:

```python
# Write callback — called when the CPU executes OUT 0x10, Rx
def virtual_output(valeur):
    print(f"[OUTPUT] CPU sent: {valeur}")

# Read callback — called when the CPU executes IN 0x11, Rx
def virtual_input():
    return int(input("[INPUT] Enter a value (0-255): "))
```

Then in your `.pcc`:
```
IOController : [
    0x10 : py.virtual_output()
    0x11 : py.virtual_input()
]
```

---

## Performance Profiling

Add `--profile` to run the CPU under Python's `cProfile` and print a full function-level performance report when execution ends. This is useful for identifying bottlenecks in the emulator's Python implementation.

```bash
python emulator.py my_machine.pcc --profile
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | GUI windows: GPU screen, Qt debugger, code editor |
| `Python ≥ 3.10` | f-strings, `match`/`case`, and type hints used throughout |

Install all dependencies:

```bash
pip install PyQt6
```

No other external packages are required. The assembler, disassembler, monitor, and emulator core are all pure Python.
