def dump(data: str|bytes, start_addr: int = 0):
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_bytes = ' '.join(f'{b:02X}' for b in chunk)
        ascii_bytes = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        addr = start_addr + i
        lines.append(f'{addr:08X}  {hex_bytes:<47}  {ascii_bytes}')
    print('\n'.join(lines))
