"""
Tamanho permitido do corpo (bytes após len/checksum/cmd) de cada pacote C->S, extraído do servidor original
(GunBoundServ3.exe, FUN_00427b60, via REA/Ghidra). Pacote fora da regra é descartado antes do handler,
como o original faz. Opcode ausente da tabela não tem regra no original (aceito).
"""
# cmd: (mínimo, máximo, múltiplo)
BODY_RULES: dict[int, tuple[int, int, int]] = {
    0x0000: (0, 0, 1), 0x1000: (0, 0, 1), 0x1011: (0x40, 0x40, 1), 0x1016: (16, 16, 1),
    0x1020: (2, 0x4B2, 1), 0x1021: (2, 0x642, 1), 0x1090: (0, 0x65, 1), 0x1100: (0, 0, 1),
    0x2000: (2, 2, 1), 0x2010: (16, 0xFFFF, 16), 0x2020: (0, 0, 1), 0x2022: (0, 0, 1),
    0x2100: (5, 5, 1), 0x2101: (0, 0x18, 1), 0x2104: (2, 2, 1), 0x2110: (6, 6, 1),
    0x2120: (10, 0x4A, 1), 0x2130: (0, 0, 1), 0x2140: (0, 0, 1),
    0x3001: (2, 2, 1), 0x3100: (1, 1, 1), 0x3101: (4, 4, 1), 0x3102: (8, 8, 1), 0x3103: (1, 1, 1),
    0x3104: (1, 0x40, 1), 0x3150: (1, 1, 1), 0x3200: (2, 2, 1), 0x3210: (1, 1, 1), 0x3230: (1, 1, 1),
    0x3232: (0, 0, 1), 0x3430: (0, 0x80, 1),
    0x4000: (16, 16, 1), 0x4100: (5, 5, 1), 0x4104: (16, 16, 1), 0x4200: (16, 16, 1),
    0x4412: (0x20, 0xFFFF, 1), 0x4500: (4, 0x20A, 1),
    0x5000: (0x20, 0xFFFF, 1), 0x5010: (0x10, 0x110, 1),
    0x5110: (0, 0, 1), 0x5112: (1, 0xC9, 1), 0x5114: (1, 0xC9, 1), 0x5116: (8, 8, 1), 0x5120: (4, 4, 1),
    0x5122: (2, 2, 1), 0x5124: (8, 8, 1), 0x5126: (2, 0xFFFF, 1), 0x5128: (6, 6, 1), 0x512A: (2, 2, 1),
    0x512C: (8, 8, 1),
    0x6000: (0, 0, 1), 0x6004: (0, 0, 1), 0x6008: (0, 0x10, 1), 0x600A: (2, 0x962, 1), 0x600E: (7, 0x52, 1),
    0x6020: (16, 16, 1), 0x6024: (16, 16, 1), 0x6028: (0x30, 0x70, 1), 0x6030: (0, 0x80, 1),
    0x6100: (0, 0, 1), 0x6104: (0, 0, 1),
}


def body_ok(cmd: int, size: int) -> bool:
    rule = BODY_RULES.get(cmd)
    if rule is None:
        return True
    lo, hi, mult = rule
    return lo <= size <= hi and size % mult == 0
