"""
Importa os mapas (.lnd) dos clientes para server/maps/ (fora do git), para a mira dos bots (gunbound/bot/aim.py).
O TH v404, o v440 e o v495 têm os mesmos .lnd byte a byte; o que muda por versão é o stage.dat (mapa + lado -> arquivo).
Então cada .lnd vai uma vez (maps/<prefixo>.lnd.gz) e cada versão ganha a tabela maps/stages-<versão>.txt
("mapa lado prefixo"):
  s1    graphics.xfs do WC S1: stage.dat de 32 registros de 484, prefixo em +128, índice = mapa + lado * 11 (A/B)
  v584  graphics.xfs de dentro do GunBound.xfs SolFS: stage.dat de 0x270 por registro (carga em 0x423cdf), prefixo
        em +128, índice = mapa + lado * 18 (G+0x2799c + G+0x279a0 * 0x12). Só há lados A/B (36 registros): o cliente
        grava lado = (settings >> 16) % 2 (0x509716), então C/D do servidor usam o terreno de A/B. Senha só por
        GB_SOLFS_PASSWORD.
Os dois stage.dat são LZHUF depois de 4 bytes de versão (gbedit/lzhuf.py).
  python tools/import_maps.py [--s1 graphics.xfs] [--v584 GunBound.xfs] [--out maps]
"""
from __future__ import annotations
import argparse
import gzip
import importlib.util
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# (tamanho aberto do stage.dat, registro, offset do prefixo, mapas por lado, lados)
LAYOUTS = {'s1': (0x3C80, 484, 128, 11, 2), 'v584': (0x9C00, 0x270, 128, 18, 2)}
DEFAULTS = {'s1': ROOT.parent / 'clientes' / 'WC-S1-v495' / 'graphics.xfs',
            'v584': ROOT.parent / 'clientes' / 'WC-S2-v584' / 'GunBound.xfs'}


def _xfs_reader():
    spec = importlib.util.spec_from_file_location('_xfs_reader', ROOT / 'tools' / 'xfs_sync' / 'xfs_reader.py')
    xr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(xr)
    return xr


def _gbedit():
    """gbedit (SolFS, LZHUF) é outro projeto: GBEDIT_PATH ou ../tools/gbedit, como tools/xfs_sync/xfs_reader.py."""
    path = os.environ.get('GBEDIT_PATH') or str(ROOT.parent / 'tools' / 'gbedit')
    if path not in sys.path:
        sys.path.insert(0, path)
    from gbedit import lzhuf, solfs
    return lzhuf, solfs


def graphics(path: Path) -> io.BytesIO:
    """O graphics.xfs: o próprio arquivo (S1) ou o de dentro do SolFS (S2)."""
    _, solfs = _gbedit()
    if not solfs.looks_like_file(path):
        return io.BytesIO(path.read_bytes())
    if not solfs.resolve_password():
        raise SystemExit(f'{path.name} é SolFS cifrado: defina GB_SOLFS_PASSWORD no ambiente')
    try:
        import Crypto  # noqa: F401  (o AES do SolFS)
    except ImportError:
        raise SystemExit('falta o pycryptodome: rode com o .venv do servidor (.venv\\Scripts\\python.exe) '
                         'ou pip install -r requirements.txt') from None
    sf = solfs.Solfs.open(str(path))
    inner = next((n for n in sf.entries() if n.lower() == 'graphics.xfs'), None)
    if inner is None:
        raise SystemExit(f'graphics.xfs não está dentro de {path}: {sf.entries()}')
    return io.BytesIO(sf.read_file(inner))


def stages(stage: bytes, version: str) -> dict[tuple[int, int], str]:
    """{(mapa, lado): prefixo} do stage.dat aberto (registro vazio = mapa que não existe)."""
    _, rec, off, per_side, sides = LAYOUTS[version]
    out = {}
    for side in range(sides):
        for m in range(per_side):
            i = (m + side * per_side) * rec
            name = stage[i + off:i + rec].split(b'\x00')[0].decode('latin-1').lower()
            if name:
                out[m, side] = name
    return out


def read(path: Path, version: str) -> tuple[dict[tuple[int, int], str], dict[str, bytes]]:
    """(tabela, {prefixo: .lnd}) de um cliente."""
    xr, (lzhuf, _) = _xfs_reader(), _gbedit()
    f = graphics(path)
    entries = {e.name.lower(): e for e in xr.read_trailer(f)[1]}
    table = stages(lzhuf.decode(xr.read_entry(f, entries['stage.dat'])[4:], LAYOUTS[version][0]), version)
    lnds = {}
    for name in sorted(set(table.values())):
        entry = entries.get(name + '.lnd')
        if entry is None:
            print(f'  {version}: {name}.lnd não está no graphics.xfs')
            continue
        try:
            lnds[name] = xr.read_entry(f, entry)
        except Exception as e:  # bloco que o xfs_reader não lê: o bot passa a vez nesse mapa
            print(f'  {version}: {name}.lnd ilegível ({e})')
    return {k: v for k, v in table.items() if v in lnds}, lnds


def save(out: Path, version: str, table: dict, lnds: dict[str, bytes]) -> list[str]:
    """Grava os .lnd e a tabela; devolve os prefixos que já existiam com outro conteúdo (mapa mudou entre versões)."""
    out.mkdir(parents=True, exist_ok=True)
    changed = []
    for name, data in lnds.items():
        path = out / f'{name}.lnd.gz'
        if path.is_file():
            if gzip.decompress(path.read_bytes()) == data:
                continue
            changed.append(name)
            path = out / f'{name}.{version}.lnd.gz'
            for key in [k for k, v in table.items() if v == name]:
                table[key] = f'{name}.{version}'
        path.write_bytes(gzip.compress(data, mtime=0))
    lines = [f'{m} {side} {name}' for (m, side), name in sorted(table.items())]
    (out / f'stages-{version}.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return changed


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--s1', type=Path, default=DEFAULTS['s1'])
    ap.add_argument('--v584', type=Path, default=DEFAULTS['v584'])
    ap.add_argument('--out', type=Path, default=ROOT / 'maps')
    args = ap.parse_args(argv)
    for version in ('s1', 'v584'):  # o s1 primeiro: os .lnd iguais do v584 só ganham a tabela
        path = getattr(args, version)
        if not path.is_file():
            print(f'{version}: {path} não existe, pulado')
            continue
        table, lnds = read(path, version)
        known = {n for n in lnds if (args.out / f'{n}.lnd.gz').is_file()}
        changed = save(args.out, version, table, lnds)
        sides = sorted({side for _, side in table})
        print(f'{version}: {len(table)} mapas em {len(sides)} lado(s), {len(lnds)} arquivos .lnd '
              f'({len(known) - len(changed)} iguais aos já importados, {len(changed)} diferentes, '
              f'{len(lnds) - len(known)} novos)')
        for side in sides:
            row = ', '.join(f'{m}={table[m, side]}' for m in range(LAYOUTS[version][3]) if (m, side) in table)
            print(f'  lado {"ABCD"[side]}: {row}')
        if changed:
            print(f'  mudaram nesta versão (gravados como <nome>.{version}): {", ".join(changed)}')
    print(f'pronto: {args.out}')


if __name__ == '__main__':
    main()
