"""
Leitor do container XFS2 (avatar.xfs / graphics.xfs) do GunBound WC.

Formato (decifrado e validado contra avatar.xfs e graphics.xfs, somente leitura):

  Cabeçalho do arquivo
    u32 LE no offset 0 = offset do trailer (tabela de arquivos).

  Grupos (dados)
    Cada entrada da tabela aponta para um offset de dados. Os dados são uma sequência de blocos zlib:
      bloco "cheio": u16 comp, 0x00, u24 (crc, não usado)  + zlib  -> sempre 65536 bytes decomprimidos
      bloco "final": u16 dec, 0x80, u16 comp, u24 (crc)     + zlib  -> último bloco do grupo
    Não há cifra: é só zlib. Um grupo tem exatamente o tamanho decomprimido informado na tabela.

  Trailer
    Em ptr = u32 do offset 0: 1 byte de flag, depois zlib de cabeçalho de 64 bytes que começa com "XFS2".
    Em ptr+1+len(zlib_cabecalho)+3 : zlib da tabela de arquivos, com count*128 bytes (count = u32 no cabeçalho, off. 8).
    Cada entrada da tabela tem 128 bytes:
      0..31   nome do arquivo (cstring)
      32..111 campos desconhecidos (ex.: flags, datas)
      112     u32 offset do grupo no arquivo
      116     u32 = 1 (não usado)
      120     u32 tamanho decomprimido do grupo
      124     u32 tamanho comprimido do grupo (0xFFFFFFFF em graphics.xfs, não confiável)

  Conteúdo do grupo de itens (avatar.xfs)
    u32 count, depois count registros de 644 bytes (tabela de itens da loja/avatar).
    Campos do registro (offsets dentro do registro): veja ITEM_* abaixo e docs em item_sync.py.
    Alguns grupos usam registros de 684 bytes ou não são tabelas (texto "1111..."): são ignorados aqui.

Só usa a biblioteca padrão (zlib, struct).
"""
import os
import struct
import sys
import zlib
from dataclasses import dataclass, field

XFS_MAGIC = b'XFS2'
TABLE_ENTRY_SIZE = 128
BLOCK_SIZE = 65536
ZLIB_HEADERS = (b'\x78\x01', b'\x78\x5e', b'\x78\x9c', b'\x78\xda')
ITEM_STRIDE = 644          # tamanho do registro de item (tabela de avatar)
TH_ITEM_STRIDE = 148       # TH: registro aberto (gbedit/dat.py item-th-148); um preço só: gold @40, cash @44, vende @48
ITEM_NAME_OFF = 12         # nome do item (cstring, até 20 bytes)
SLOT_BY_SUFFIX = {'b': 0, 'h': 1, 'g': 2, 'f': 3}   # sufixo do arquivo -> slot no código
MALE_BIT = 0x8000
ITEM_NAME_LEN = 20

# Faixas de preço: (offset do gold, offset do cash, offset da flag de venda). Cash = gold / 30 nos tiers principais.
PRICE_TIERS = [
    (40, 44, 48),    # tier 0
    (52, 56, 60),    # tier 1 (não usado pelo servidor)
    (64, 68, 72),    # tier 2
    (76, 80, 84),    # tier 3
    (88, 92, 96),    # tier 4 (flag é o bit 0 do u32 do offset 96)
]


class XfsError(Exception):
    """Container XFS inválido ou corrompido."""


@dataclass
class TableEntry:
    name: str
    offset: int
    dec_size: int


@dataclass
class PriceTier:
    gold: int
    cash: int
    enabled: bool


@dataclass
class ItemRecord:
    code: int                     # chave completa u32 @0: (slot<<16)|(masculino<<15)|índice local = Menu.No
    name: str
    source: str                   # nome do arquivo de origem na tabela XFS (ex.: fb.dat)
    slot_raw: int                 # u32 @8: tipo/slot (valor bruto, mapeamento pendente)
    gender_raw: int               # byte @35: candidato a gênero (bruto, não confirmado)
    period_mask_raw: int          # u32 @36: máscara (279/23), candidato a períodos (não confirmado)
    tiers: list = field(default_factory=list)  # lista de PriceTier


def read_cstring(data: bytes, off: int, length: int) -> str:
    raw = data[off:off + length].split(b'\0', 1)[0]
    return raw.decode('latin-1')


def _zlib_at(buf: bytes, pos: int):
    """Descomprime um zlib em buf[pos:]. Retorna (dados, bytes_consumidos)."""
    z = zlib.decompressobj()
    out = z.decompress(buf[pos:])
    if not z.eof:
        raise XfsError(f'zlib incompleto em {pos:#x}')
    return out, len(buf) - pos - len(z.unused_data)


def read_trailer(f) -> tuple[int, list[TableEntry]]:
    """Lê cabeçalho e tabela de arquivos. f: arquivo aberto em modo binário."""
    f.seek(0)
    head = f.read(4)
    if len(head) < 4:
        raise XfsError('arquivo muito pequeno')
    ptr = struct.unpack('<I', head)[0]
    f.seek(ptr)
    raw = f.read(4096)
    hdr, used = _zlib_at(raw, 1)
    if hdr[:4] != XFS_MAGIC:
        raise XfsError(f'cabeçalho XFS2 não encontrado em {ptr:#x}')
    count = struct.unpack_from('<I', hdr, 8)[0]
    table_pos = ptr + 1 + used + 3   # 3 bytes de prefixo antes da zlib da tabela
    f.seek(table_pos)
    raw = f.read(count * TABLE_ENTRY_SIZE * 2 + 4096)
    table, _ = _zlib_at(raw, 0)
    if len(table) != count * TABLE_ENTRY_SIZE:
        raise XfsError(f'tabela com {len(table)} bytes, esperado {count * TABLE_ENTRY_SIZE}')
    entries = []
    for i in range(count):
        e = table[i * TABLE_ENTRY_SIZE:(i + 1) * TABLE_ENTRY_SIZE]
        entries.append(TableEntry(
            name=read_cstring(e, 0, 32),
            offset=struct.unpack_from('<I', e, 112)[0],
            dec_size=struct.unpack_from('<I', e, 120)[0],
        ))
    return ptr, entries


def read_entry(f, entry: TableEntry) -> bytes:
    """Descomprime um grupo inteiro pelos blocos zlib a partir de entry.offset."""
    f.seek(entry.offset)
    buf = f.read(entry.dec_size + 2 * 65536)  # folga para cabeçalhos e blocos
    out = []
    pos = 0
    remaining = entry.dec_size
    while remaining > 0:
        # Bloco final: u16 dec == restante, zlib em pos+8. Senão é bloco cheio (zlib em pos+5).
        is_final = (remaining <= BLOCK_SIZE
                    and struct.unpack_from('<H', buf, pos)[0] == remaining
                    and buf[pos + 8:pos + 10] in ZLIB_HEADERS)
        if is_final:
            hl = 8
            comp = struct.unpack_from('<H', buf, pos + 3)[0]
        else:
            hl = 5
            comp = struct.unpack_from('<H', buf, pos)[0]
        if buf[pos + hl:pos + hl + 2] not in ZLIB_HEADERS:
            # Ex.: bloco final com flag 0xC0 em graphics.xfs: formato ainda não decodificado
            raise XfsError(f'bloco não reconhecido em {entry.name} (rel. {pos:#x}, flag {buf[pos + 2]:#04x})')
        chunk = zlib.decompress(buf[pos + hl:pos + hl + comp])
        if len(chunk) > remaining:
            raise XfsError(f'bloco maior que o restante em {entry.name}')
        out.append(chunk)
        remaining -= len(chunk)
        pos += hl + comp
    return b''.join(out)


def expected_key(source: str, local_index: int) -> int:
    """Chave esperada para um índice local num arquivo de tabela (ex.: 'mh.dat', índice 1 -> 0x18001)."""
    slot = SLOT_BY_SUFFIX[source[1]]
    male = MALE_BIT if source[0] == 'm' else 0
    return (slot << 16) | male | (local_index & 0x7FFF)


def key_matches_source(code: int, source: str) -> bool:
    """Confere se a chave u32 do registro bate com o arquivo de origem (slot e gênero)."""
    return ((code >> 16) & 0xF) == SLOT_BY_SUFFIX.get(source[1], -1)         and bool(code & MALE_BIT) == (source[0] == 'm')


def parse_item_table(data: bytes, source: str) -> list[ItemRecord]:
    """Interpreta um grupo se for tabela de itens de 644 bytes. Retorna [] para outros grupos."""
    if len(data) < 4:
        return []
    count = struct.unpack_from('<I', data, 0)[0]
    stride, price_tiers = ITEM_STRIDE, PRICE_TIERS
    if count and len(data) - 4 == count * TH_ITEM_STRIDE:
        stride, price_tiers = TH_ITEM_STRIDE, [(40, 44, 48)] * len(PRICE_TIERS)  # o preço único vale para todos
    elif count != (len(data) - 4) / ITEM_STRIDE:
        return []  # ex.: grupos de texto "1111..." ou tabelas com layout diferente
    items = []
    for i in range(count):
        base = 4 + i * stride
        rec = data[base:base + stride]
        tiers = []
        for g_off, c_off, f_off in price_tiers:
            tiers.append(PriceTier(
                gold=struct.unpack_from('<I', rec, g_off)[0],
                cash=struct.unpack_from('<I', rec, c_off)[0],
                enabled=bool(struct.unpack_from('<I', rec, f_off)[0] & 1),
            ))
        items.append(ItemRecord(
            code=struct.unpack_from('<I', rec, 0)[0],
            name=read_cstring(rec, ITEM_NAME_OFF, ITEM_NAME_LEN),
            source=source,
            slot_raw=struct.unpack_from('<I', rec, 8)[0],
            gender_raw=rec[35],
            period_mask_raw=struct.unpack_from('<I', rec, 36)[0],
            tiers=tiers,
        ))
    return items


def read_groups(path: str, names=None) -> list[tuple[str, bytes]]:
    """[(nome, dados)] dos grupos do XFS (todos ou só os de names), em qualquer versão do cliente:
    WC S1: avatar.xfs zlib (leitor deste arquivo).
    v531+ (v548, S2): GunBound.xfs SolFS cifrado com o avatar.xfs dentro; senha em GB_SOLFS_PASSWORD (gbedit/solfs.py).
    TH: avatar.xfs LZHUF (gbedit/xfs_th.py).
    Os .dat com cada registro comprimido (TH; v548 com 259 bytes) voltam abertos (gbedit/dat.py th_unpack)."""
    import io
    want = {n.lower() for n in names} if names else None
    with open(path, 'rb') as f:
        data = f.read()
    # gbedit é outro projeto: GBEDIT_PATH aponta a pasta que contém o pacote gbedit (padrão: ../tools/gbedit fora do server)
    gbedit = os.environ.get('GBEDIT_PATH') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tools', 'gbedit'))
    if gbedit not in sys.path:
        sys.path.insert(0, gbedit)
    from gbedit import dat, solfs, xfs_th
    if solfs.looks_like(data):
        try:
            sf = solfs.Solfs.open(path)
            inner = next((n for n in sf.entries() if n.lower() == 'avatar.xfs'), None)
            if inner is None:
                raise XfsError(f'avatar.xfs não está dentro de {path}')
            data = sf.read_file(inner)
        except solfs.SolfsError as e:
            raise SystemExit(f'{path} é SolFS cifrado (S2): {e}. Defina a senha em GB_SOLFS_PASSWORD.') from None
    def opened(name, g):  # .dat com registros comprimidos (TH, v548) volta aberto (148/188 ou 644/684 bytes)
        stride = dat.th_stride(g)
        return dat.th_unpack(g, stride, dat.th_size(g, stride, name)) if stride else g

    if xfs_th.looks_like(data):
        arc = xfs_th.ThXfs.open_bytes(data)
        return [(e.name, opened(e.name, arc.data_of(e))) for e in arc.entries if want is None or e.name.lower() in want]
    f = io.BytesIO(data)
    _, entries = read_trailer(f)
    return [(e.name, opened(e.name, read_entry(f, e))) for e in entries if want is None or e.name.lower() in want]


def extract_records(path: str) -> list[ItemRecord]:
    """Lê todas as tabelas de itens (644 bytes no WC, 148 no TH) do XFS, sem consolidar códigos repetidos."""
    records = []
    for name, data in read_groups(path):
        records += parse_item_table(data, name)
    return records
