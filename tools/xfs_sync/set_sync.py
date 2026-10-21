"""
Importa os SETS e pacotes da loja (ex1.dat e ex2.dat do avatar.xfs) para a tabela Menu (INSERT, sem apagar nada).

Uso:
    python -I set_sync.py                 # dry-run (padrão)
    python -I set_sync.py --apply         # faz backup gbwc.db.bak-<timestamp>-sets e grava

Formato do registro de set (684 bytes, count = (len-4)/684; decodificado de ex1.dat):
  @0   u32 código do menu (= Menu.No), ex.: 0x30001 = 196609 = "Golden Armor Set(M)"
  @20  nome (cstring)
  @48..103 (gold, cash) por período W,T,M,Y,I (gbedit PRICE_ROWS_684); @104/@105 u8 vende gold/cash
  @112 até 5 triplas u32 (código do item, volume, período); período 0xFFFFFFFF = não usado,
       código 0 ou 0xFFFFFFFF = slot vazio. Os códigos são as chaves dos itens únicos (mesmo formato de item_sync).

S2 (GunBound.xfs do v548/v584): também lê ex3.dat/ex4.dat quando existem (selos, tickets e outros itens 700xxx).
Fora do ex1, registro sem itens é o próprio item (Item1 = código, como os Power User do seed).

Regras:
  - Período dos itens do set segue as linhas de item existentes (Period 86400); o volume vem da tripla
    (0 ou 0xFFFFFFFF vira 1).
  - Preço por período e moeda, como o cliente mostra: o S2 vende selos só por semana e outros itens com W/M/I
    diferentes. Período ou moeda com preço 0 fica NULL (a compra é recusada). O TH (188) tem preço único.
  - Set já existente em Menu não é tocado. Sentinela no ilimitado (9999990 gold / 999999 cash, ou os mesmos com 30%
    de desconto: 6999993 / 699999) = sem venda: não entra. Em outro período, a sentinela vira NULL.
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
S2_GROUPS = ('ex3.dat', 'ex4.dat')    # vazios ("1111") no WC S1; no S2 trazem os itens 700xxx (selos, tickets)
PRICE_SENTINEL_CASH = 999999
# 9999990 / 999999 com 30% de desconto (S1 "Clown Set", S2 prêmios de GP e o placeholder 0x32000): também é "sem venda"
SENTINEL_GOLD_DC, SENTINEL_CASH_DC = 6999993, 699999
FLAGS_684 = (56, 68, 80, 92)   # u32 "habilita" de T, M, Y, I (gbedit PRICE_ROWS_684); a semana não tem
TIERS_684 = [(48, 52), (60, 64), (72, 76), (84, 88), (96, 100)]   # gold/cash W,T,M,Y,I (gbedit PRICE_ROWS_684)
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


def parse_sets(data: bytes, own_item: bool = False):
    """Retorna lista de dicts {code, name, gold, cash, items: [(item_code, volume)], tiers} dos registros com itens.
    own_item: registro sem itens vira o próprio item (volume 1) em vez de ser ignorado."""
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
                items.append((code, vol if vol not in EMPTY_CODES else 1))
        code = struct.unpack_from('<I', rec, 0)[0]
        if not items:
            if not own_item:
                continue  # ex.: registro "Standard" (sem itens)
            items = [(code, 1)]
        gold, cash = struct.unpack_from('<I', rec, gold_off)[0], struct.unpack_from('<I', rec, cash_off)[0]
        sets.append({
            'code': code,
            'name': xfs_reader.read_cstring(rec, SET_NAME_OFF, SET_NAME_LEN)[:item_sync.MENU_NAME_MAX],
            'gold': gold,
            'cash': cash,
            'items': items,
            # (gold, cash) de W,T,M,Y,I; o TH tem um preço só
            'tiers': [struct.unpack_from('<II', rec, g) for g, _ in TIERS_684] if stride == SET_STRIDE
            else [(gold, cash)] * len(item_sync.PERIODS),
            'sells': tuple(rec[104:106]) if stride == SET_STRIDE else (),  # vende gold/cash: só para o relatório
            'flags': tuple(struct.unpack_from('<I', rec, f)[0] for f in FLAGS_684) if stride == SET_STRIDE else (),
        })
    return sets


def load_sets(xfs_path: str):
    groups = {name.lower(): data for name, data in xfs_reader.read_groups(xfs_path, SET_GROUPS + S2_GROUPS)}
    out = []
    for name in SET_GROUPS + S2_GROUPS:
        if name not in groups:
            if name in S2_GROUPS:
                continue
            raise SystemExit(f'grupo {name} não encontrado em {xfs_path}')
        out += parse_sets(groups[name], own_item=name != 'ex1.dat')
    print(f'Grupos lidos: {", ".join(n for n in SET_GROUPS + S2_GROUPS if n in groups)}')
    return out


def prices(s) -> tuple:
    """Gold W,T,M,Y,I + cash W,T,M,Y,I para o Menu; None = não vende naquele período/moeda.
    Sentinela no ilimitado = registro sem venda (placeholders do S1/S2 têm preço nos outros períodos)."""
    i_gold, i_cash = s['tiers'][-1]
    if i_gold >= SENTINEL_GOLD_DC or i_cash >= SENTINEL_CASH_DC:
        return (None,) * 10
    return (tuple(g if 0 < g < SENTINEL_GOLD_DC else None for g, _ in s['tiers'])
            + tuple(c if 0 < c < SENTINEL_CASH_DC else None for _, c in s['tiers']))


def plan_sets(con, sets):
    existing = {row[0] for row in con.execute('SELECT No FROM Menu')}
    sellable = [s for s in sets if any(p is not None for p in prices(s))]
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
            cols += [f'PriceByGoldFor{p}' for p in item_sync.PERIODS] + [f'PriceByCashFor{p}' for p in item_sync.PERIODS]
            vals += prices(s)
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
        items = ','.join(f'{c:#x}x{v}' for c, v in s['items'])
        p = prices(s)
        print(f'  {s["code"]} ({s["code"]:#x}) {s["name"]!r} gold(W,T,M,Y,I)={list(p[:5])} '
              f'cash={list(p[5:])} itens=[{items}] vende g/c={s["sells"]} habilita T,M,Y,I={s["flags"]}')

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
