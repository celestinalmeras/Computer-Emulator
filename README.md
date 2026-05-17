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

This section documents the complete ISA (Instruction Set Architecture) of the CPU. All opcodes are 1 byte. Operand widths depend on the `data_bytes` and `address_bytes` values set in your `.pcc`.

### 1. System & Control

| Opcode | Instruction | Description |
|---|---|---|
| `0x00` | `NOP` | No Operation. Does nothing for one cycle. |
| `0xFF` | `HLT` | Halt. Stops CPU execution. |

### 2. Data Transfer

| Opcode | Instruction | Description |
|---|---|---|
| `0x10` | `MOV Rn, Rm` | Copies the content of register `Rm` into `Rn`. |
| `0x11` | `MOV Rn, imm` | Loads the immediate value `imm` into `Rn`. |
| `0x12` | `LOAD Rn, [addr]` | Reads the value in RAM at address `addr` and stores it in `Rn`. |
| `0x13` | `STORE [addr], Rn` | Writes the content of `Rn` to RAM at address `addr`. |
| `0x14` | `LOAD Rn, [Rm]` | Indirect: loads into `Rn` the value at the memory address stored in `Rm`. |
| `0x15` | `MOV Rn, [Rm + off]` | Indexed: computes address `(Rm + offset)` and loads the value found there into `Rn`. |

### 3. Arithmetic & Logic (ALU)

> These operations (except `CMP`) update the status flags: **Z** (Zero), **C** (Carry), **N** (Negative), **O** (Overflow).

| Opcode | Instruction | Description |
|---|---|---|
| `0x20` | `ADD Rn, Rm` | Rn = Rn + Rm |
| `0x21` | `ADDI Rn, imm` | Rn = Rn + imm |
| `0x22` | `SUB Rn, Rm` | Rn = Rn − Rm |
| `0x26` | `MUL Rn, Rm` | Rn = Rn × Rm |
| `0x27` | `XOR Rn, Rm` | Bitwise XOR between `Rn` and `Rm`. |
| `0x28` | `CMP Rn, Rm` | Virtually subtracts `Rm` from `Rn` to update flags only (result not stored). |
| `0x29` | `CMP Rn, imm` | Virtually subtracts `imm` from `Rn` to update flags only (result not stored). |
| `0x30` | `AND Rn, Rm` | Bitwise AND between `Rn` and `Rm`. |
| `0x31` | `OR Rn, Rm` | Bitwise OR between `Rn` and `Rm`. |
| `0x32` | `ANDI Rn, imm` | Bitwise AND between `Rn` and immediate `imm`. |
| `0x33` | `NOT Rn` | Inverts all bits of `Rn`. |
| `0x34` | `SHL Rn` | Shift Left: shifts bits left by 1 (equivalent to × 2). |
| `0x35` | `SHR Rn` | Shift Right: shifts bits right by 1 (equivalent to ÷ 2). |

### 4. Branches & Subroutines

| Opcode | Instruction | Condition / Description |
|---|---|---|
| `0x40` | `JMP addr` | Unconditional jump to `addr`. |
| `0x41` | `JZ addr` | Jump if Zero flag (Z) = 1. |
| `0x42` | `JNZ addr` | Jump if Zero flag (Z) = 0. |
| `0x43` | `JC addr` | Jump if Carry flag (C) = 1. |
| `0x44` | `JNC addr` | Jump if Carry flag (C) = 0. |
| `0x45` | `JN addr` | Jump if Negative flag (N) = 1. |
| `0x46` | `JNN addr` | Jump if Negative flag (N) = 0. |
| `0x47` | `JO addr` | Jump if Overflow flag (O) = 1. |
| `0x48` | `JNO addr` | Jump if Overflow flag (O) = 0. |
| `0x49` | `CALL addr` | Saves PC onto the stack and jumps to `addr` (function call). |
| `0x4A` | `RET` | Pops the return address from the stack and resumes execution (return from function). |

- **Symbolic labels**: programs can use named labels instead of hardcoded addresses, improving readability and simplifying code maintenance.

**Example — draw a red pixel at (3, 5):**
```asm
START:
    MOV R0, 1
    JMP START
```
### 5. Stack

| Opcode | Instruction | Description |
|---|---|---|
| `0x50` | `PUSH Rn` | Pushes the value of `Rn` onto the stack. |
| `0x51` | `POP Rn` | Pops the top of the stack into `Rn`. |

### 6. I/O & Cache

| Opcode | Instruction | Data flow |
|---|---|---|
| `0x60` | `IN Rn, port` | Peripheral → Register `Rn` |
| `0x61` | `OUT port, Rn` | Register `Rn` → Peripheral |
| `0x62` | `IN_RAM addr, port` | Peripheral → RAM `[addr]` |
| `0x63` | `OUT_RAM port, addr` | RAM `[addr]` → Peripheral |
| `0x64` | `IN_CACHE addr, port` | Peripheral → Cache `[addr]` |
| `0x65` | `OUT_CACHE port, addr` | Cache `[addr]` → Peripheral |
| `0x70` | `MTC_REG addr, Rn` | Register `Rn` → Cache `[addr]` |
| `0x71` | `MTC_RAM addr` | RAM `[addr]` → Cache `[addr]` |
| `0x72` | `MFC Rn, addr` | Cache `[addr]` → Register `Rn` |

### 7. GPU Subsystem

The GPU listens on dedicated I/O ports to manage an n×n pixel display. Write to these ports using `OUT` instructions before triggering a draw command.

| Port | Register | Description |
|---|---|---|
| `0x10` | X | Pixel X coordinate |
| `0x11` | Y | Pixel Y coordinate |
| `0x12` | R | Red channel (0–255) |
| `0x13` | G | Green channel (0–255) |
| `0x14` | B | Blue channel (0–255) |
| `0x15` | CMD | Command: `1` = `DRAW_PIXEL`, `2` = `CLEAR_SCREEN` |

**Example — draw a red pixel at (3, 5):**
```asm
MOV R0, 3
OUT 0x10, R0   ; X = 3

MOV R0, 5
OUT 0x11, R0   ; Y = 5

MOV R0, 255
OUT 0x12, R0   ; R = 255
MOV R0, 0
OUT 0x13, R0   ; G = 0
OUT 0x14, R0   ; B = 0

MOV R0, 1
OUT 0x15, R0   ; CMD = DRAW_PIXEL
```

---

## IOController & Peripherals

The `IOController` is the bridge between the CPU and the outside world. It maintains a port map where each port number is associated with a read callback, a write callback, or both.

### Built-in: GPU

When ports are mapped to `GPU` in the `.pcc`, `OUT` instructions on those ports are forwarded to the GPU's command handler. The GPU interprets the values as drawing commands (pixel color, position, render trigger, etc.) and updates the VRAM framebuffer, which is then rendered in the screen window.

### Custom Python Callbacks

You can wire any port to a Python function defined in `emulator.py`:

```python
# Write callback — called when the CPU executes OUT 0x10, Rx
def virtual_output(value):
    print(f"[OUTPUT] CPU sent: {value}")

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

### External packages

| Package | Purpose |
|---|---|
| `PyQt6` | GUI windows: GPU screen, Qt debugger, code editor |

```bash
pip install PyQt6
```

### Standard library (no installation required)

| Module | Purpose |
|---|---|
| `sys` | Command-line arguments, application exit |
| `os` | Terminal clearing, file path handling |
| `re` | Parsing `.pcc` config files |
| `argparse` | CLI argument parsing for `emulator.py` and `format_converter.py` |
| `threading` | Running the CPU in a background thread alongside the GUI |
| `inspect` | Detecting I/O callback signatures (read vs write) |
| `cProfile` | CPU performance profiling (`--profile` flag) |
| `time` | Component speed delays, monitor startup pause |
| `shutil` | File utilities |

> **Python ≥ 3.10** is required.


### Future Improvements

The following features are planned for future versions of the emulator:

- Support for multiple languages in the emulator interface and tooling.
- Addition of a comprehensive set of example programs to help users learn and test the system.
- Implementation of multi-core CPU support to allow parallel instruction execution and improved performance.

---
The studio that I co-created : [Github](https://github.com/Floodfield-Sudio), [Website](https://floodfield-sudio.github.io/FFS.index/)
<img width="24" height="24" alt="floodfiled_studio-logo" src="https://github.com/user-attachments/assets/9d98849d-468d-4686-be33-59ec5a89358c" />
