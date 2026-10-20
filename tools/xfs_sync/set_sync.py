"""
Importa os SETS e pacotes da loja (ex1.dat e ex2.dat do avatar.xfs) para a tabela Menu (INSERT, sem apagar nada).

Uso:
    python -I set_sync.py                 # dry-run (padrão)
    python -I set_sync.py --apply         # faz backup gbwc.db.bak-<timestamp>-sets e grava

Formato do registro de set (684 bytes, count = (len-4)/684; decodificado de ex1.dat):
  @0   u32 código do menu (= Menu.No), ex.: 0x30001 = 196609 = "Golden Armor Set(M)"
  @20  nome (cstring)
  @96  u32 gold do tier 4 (mesmo tier usado por item_sync)   @100 u32 cash do tier 4
  @112 até 5 triplas u32 (código do item, volume, período); período 0xFFFFFFFF = não usado,
       código 0 ou 0xFFFFFFFF = slot vazio. Os códigos são as chaves dos itens únicos (mesmo formato de item_sync).

Regras:
  - Período e volume dos itens do set seguem as linhas de item existentes (Period 86400, Volume 1).
  - Set já existente em Menu não é tocado. Preço sentinela (9999990 gold) = sem venda: não entra.
"""
import argparse
import os
import shutil
import sqlite3
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xfs_reader  # noqa: E402
import item_sync  # noqa: E402

SET_GROUPS = ('ex1.dat', 'ex2.dat')   # ex1 = sets; ex2 = power user/mapas/eventos (mesmo layout)
SET_STRIDE = 684
SET_HEAD = 4
SET_NAME_OFF = 20
SET_NAME_LEN = 20
SET_GOLD_OFF = 96
SET_CASH_OFF = 100
SET_ITEMS_OFF = 112
SET_MAX_ITEMS = 5
EMPTY_CODES = (0, 0xFFFFFFFF)
# stride -> (gold, cash, itens); TH (registro aberto de 188 bytes, gbedit/dat.py pacote-th-188): preço único
LAYOUTS = {SET_STRIDE: (SET_GOLD_OFF, SET_CASH_OFF, SET_ITEMS_OFF), 188: (48, 52, 64)}


def parse_sets(data: bytes):
    """Retorna lista de dicts {code, name, gold, cash, items: [(item_code, volume)]} dos registros com itens."""
    if len(data) < SET_HEAD:
        return []
    count = struct.unpack_from('<I', data, 0)[0]
    stride = next((s for s in LAYOUTS if count and len(data) - SET_HEAD == count * s), None)
    if stride is None:
        return []
    gold_off, cash_off, items_off = LAYOUTS[stride]
    sets = []
    for i in range(count):
        rec = data[SET_HEAD + i * stride:SET_HEAD + (i + 1) * stride]
        items = []
        for k in range(SET_MAX_ITEMS):
            code, vol, _period = struct.unpack_from('<III', rec, items_off + k * 12)
            if code not in EMPTY_CODES:
                items.append((code, vol))
        if not items:
            continue  # ex.: registro "Standard" (sem itens)
        sets.append({
            'code': struct.unpack_from('<I', rec, 0)[0],
            'name': xfs_reader.read_cstring(rec, SET_NAME_OFF, SET_NAME_LEN)[:item_sync.MENU_NAME_MAX],
            'gold': struct.unpack_from('<I', rec, gold_off)[0],
            'cash': struct.unpack_from('<I', rec, cash_off)[0],
            'items': items,
        })
    return sets


def load_sets(xfs_path: str):
    groups = dict(xfs_reader.read_groups(xfs_path, SET_GROUPS))
    out = []
    for name in SET_GROUPS:
        if name not in groups:
            raise SystemExit(f'grupo {name} não encontrado em {xfs_path}')
        out += parse_sets(groups[name])
    return out


def plan_sets(con, sets):
    existing = {row[0] for row in con.execute('SELECT No FROM Menu')}
    sellable = [s for s in sets if 0 < s['gold'] < item_sync.PRICE_SENTINEL_GOLD]
    return {'insert': [s for s in sellable if s['code'] not in existing],
            'skip_existing': [s for s in sellable if s['code'] in existing],
            'not_sellable': [s for s in sets if s not in sellable]}


def apply_sets(con, plan):
    """Grava os sets novos em uma transação. Itens não usados ficam NULL."""
    with con:
        for s in plan['insert']:
            items = s['items']
            cols, vals = ['No', 'Name'], [s['code'], s['name']]
            for k in range(SET_MAX_ITEMS):
                n = k + 1
                cols += [f'Item{n}', f'Period{n}', f'Volume{n}']
                vals += [items[k][0], item_sync.DEFAULT_PERIOD_SECONDS, items[k][1]] if k < len(items) \
                    else [None, None, None]
            for p in item_sync.PERIODS:
                cols.append(f'PriceByGoldFor{p}')
                vals.append(s['gold'])
            for p in item_sync.PERIODS:
                cols.append(f'PriceByCashFor{p}')
                vals.append(s['cash'])
            con.execute(f'INSERT INTO Menu ({", ".join(cols)}) VALUES ({", ".join("?" * len(vals))})', vals)


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Importa os sets de ex1.dat (avatar.xfs) para a tabela Menu.')
    ap.add_argument('--xfs', default=item_sync.DEFAULT_XFS)
    ap.add_argument('--db', default=item_sync.DEFAULT_DB)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args(argv)
    if args.apply and args.dry_run:
        ap.error('use só um: --dry-run ou --apply')

    sets = load_sets(args.xfs)
    db_path = item_sync.sqlite_path(args.db)
    if not os.path.exists(db_path):
        raise SystemExit(f'banco não encontrado: {db_path}')
    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    try:
        plan = plan_sets(con, sets)
    finally:
        con.close()

    print(f'Modo: {"APLICADO" if args.apply else "DRY-RUN (nada gravado)"}')
    print(f'Sets lidos: {len(sets)}  a inserir: {len(plan["insert"])}  já existentes: {len(plan["skip_existing"])}'
          f'  sem venda (preço sentinela, ignorados): {len(plan["not_sellable"])}')
    for s in plan['insert']:
        items = ','.join(f'{c:#x}' for c, _ in s['items'])
        print(f'  {s["code"]} ({s["code"]:#x}) {s["name"]!r} gold={s["gold"]} cash={s["cash"]} itens=[{items}]')

    if args.apply and plan['insert']:
        ts = time.strftime('%Y%m%d-%H%M%S')
        backup = f'{db_path}.bak-{ts}-sets'
        shutil.copy2(db_path, backup)
        print(f'Backup: {backup}')
        con = sqlite3.connect(f'file:{db_path}?mode=rw', uri=True)
        try:
            apply_sets(con, plan)
        finally:
            con.close()
        print('Gravado.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
