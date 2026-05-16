MOV R2, 255
OUT 0x12, R2
MOV R2, 0
OUT 0x13, R2
OUT 0x14, R2
MOV R0, 0
LIGNE:
    MOV R1, 0
    COLONNE:
        OUT 0x10, R1
        OUT 0x11, R0
        MOV R2, 1
        OUT 0x15, R2
        ADDI R1, 1
        CMP R1, 4
        JNZ COLONNE
    ADDI R0, 1
    CMP R0, 4
    JNZ LIGNE
HLT