"""
Sincroniza os itens do avatar.xfs do cliente com a tabela Menu do banco do servidor (upsert).

Uso:
    python -I item_sync.py                      # dry-run (padrão, não grava nada)
    python -I item_sync.py --apply              # grava no banco
    python -I item_sync.py --apply --update-prices   # também atualiza preços de linhas já existentes
    python -I item_sync.py --xfs <caminho> --db <caminho ou sqlite+aiosqlite:///gbwc.db>

--xfs aceita o avatar.xfs do WC S1 ou do TH, ou o GunBound.xfs do S2 (SolFS cifrado: a senha vem da variável
de ambiente GB_SOLFS_PASSWORD e nunca vai para arquivo). TH e S2 são lidos pelos leitores do tools/gbedit.

Regras:
  - Nunca apaga linhas. Itens novos entram com INSERT; itens existentes só recebem Name se estiverem vazios.
  - Preço: o preço base do item (tier 4 do registro XFS, o mesmo valor de Prop_Price do seed avatar_table)
    vale para os 5 períodos (W, T, M, Y, I), como no seed.
  - Código repetido com nome ou preço diferentes entre tabelas é conflito: fica de fora e é listado.
  - Duração (Menu.Period1) e tipo/slot/gênero não têm colunas decodificadas com segurança: o tipo e o
    gênero são mostrados no relatório, e Period1 usa o padrão do schema (86400) para linhas novas.

Só usa a biblioteca padrão. Veja docs no topo de xfs_reader.py para o formato do container.
"""
import argparse
import os
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xfs_reader  # noqa: E402

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEFAULT_XFS = r'D:\GBWCProject\OnGame\GunboundWC\avatar.xfs'
DEFAULT_DB = os.path.join(SERVER_DIR, 'gbwc.db')
PERIODS = ['W', 'T', 'M', 'Y', 'I']
DEFAULT_PERIOD_SECONDS = 86400      # default de Menu.Period1 no schema
MENU_NAME_MAX = 23                  # varchar(23) em Menu.Name
PRICE_SENTINEL_GOLD = 9999990       # preço 9999990/999999 no XFS = sem venda (não sincronizar)
GENDER_BY_PREFIX = {'m': 'M', 'f': 'F'}
SLOT_BY_SUFFIX = {'b': 'corpo', 'h': 'cabeca', 'g': 'olhos', 'f': 'arma'}


@dataclass
class CatalogItem:
    code: int
    name: str
    gold: int
    cash: int
    sources: list = field(default_factory=list)
    genders: str = ''
    slots: str = ''
    slot_raw: set = field(default_factory=set)
    sellable: bool = False


SLOT_NAME_BY_CODE = {0: 'Clothes', 1: 'Cap', 2: 'Glasses', 3: 'Etc'}


def build_catalog(records):
    """Consolida registros pela chave completa (u32). Retorna (catálogo, conflitos, chaves_inconsistentes)."""
    by_code = defaultdict(list)
    inconsistent = []
    for r in records:
        if not xfs_reader.key_matches_source(r.code, r.source):
            inconsistent.append({'code': r.code, 'source': r.source, 'name': r.name})
            continue
        by_code[r.code].append(r)
    catalog, conflicts = {}, []
    for code in sorted(by_code):
        recs = by_code[code]
        names = sorted({r.name for r in recs})
        prices = sorted({(r.tiers[4].gold, r.tiers[4].cash) for r in recs})
        if len(names) > 1 or len(prices) > 1:
            conflicts.append({'code': code, 'names': names, 'sources': sorted({r.source for r in recs})})
            continue
        r0 = recs[0]
        sources = sorted({r.source for r in recs})
        slot = (code >> 16) & 0xF
        catalog[code] = CatalogItem(
            code=code,
            name=r0.name[:MENU_NAME_MAX],
            gold=r0.tiers[4].gold,
            cash=r0.tiers[4].cash,
            sources=sources,
            genders='M' if code & xfs_reader.MALE_BIT else 'F',
            slots=SLOT_NAME_BY_CODE.get(slot, str(slot)),
            slot_raw={r.slot_raw for r in recs},
            sellable=any(r.tiers[4].enabled for r in recs) and 0 < r0.tiers[4].gold < PRICE_SENTINEL_GOLD,
        )
    return catalog, conflicts, inconsistent


def sqlite_path(db: str) -> str:
    """Aceita caminho simples ou URI SQLAlchemy sqlite (ex.: sqlite+aiosqlite:///gbwc.db)."""
    if db.startswith('sqlite'):
        path = db.split(':///', 1)[1]
    else:
        path = db
    if not os.path.isabs(path):
        path = os.path.join(SERVER_DIR, path)
    return path


def plan_sync(con, catalog, update_prices=False):
    """Calcula o que seria feito na tabela Menu sem gravar. Retorna dict com listas de ações."""
    cols = {row[1] for row in con.execute('PRAGMA table_info(Menu)')}
    if 'Name' not in cols:
        raise SystemExit('Tabela Menu sem coluna Name: schema inesperado')
    existing = {row[0]: row for row in con.execute('SELECT No, Name FROM Menu')}
    price_cols = [f'PriceByGoldFor{p}' for p in PERIODS] + [f'PriceByCashFor{p}' for p in PERIODS]
    cur_prices = {}
    if all(c in cols for c in price_cols):
        for row in con.execute(f'SELECT No, {", ".join(price_cols)} FROM Menu'):
            cur_prices[row[0]] = row[1:]
    plan = {'insert': [], 'fill_name': [], 'update_price': [], 'price_differs_kept': [], 'unchanged': 0,
            'not_sellable': []}
    for code, item in sorted(catalog.items()):
        if not item.sellable:
            plan['not_sellable'].append(item)
            continue
        if code not in existing:
            plan['insert'].append(item)
            continue
        if not (existing[code][1] or '').strip():
            plan['fill_name'].append(item)
        want = (item.gold,) * 5 + (item.cash,) * 5
        if code in cur_prices and tuple(cur_prices[code]) != want:
            (plan['update_price'] if update_prices else plan['price_differs_kept']).append(item)
        elif not (existing[code][1] or '').strip():
            pass
        else:
            plan['unchanged'] += 1
    return plan


def apply_sync(con, plan, update_prices=False):
    """Grava o plano. Tudo em uma transação; nada é apagado."""
    price_cols = [f'PriceByGoldFor{p}' for p in PERIODS] + [f'PriceByCashFor{p}' for p in PERIODS]
    set_prices = ', '.join(f'{c} = ?' for c in price_cols)
    with con:
        for it in plan['insert']:
            con.execute(
                f'INSERT INTO Menu (No, Name, Item1, Period1, Volume1, {", ".join(price_cols)}) '
                f'VALUES (?, ?, ?, ?, 1, {", ".join("?" * 10)})',
                (it.code, it.name, it.code, DEFAULT_PERIOD_SECONDS) + (it.gold,) * 5 + (it.cash,) * 5)
        for it in plan['fill_name']:
            con.execute("UPDATE Menu SET Name = ? WHERE No = ? AND (Name IS NULL OR TRIM(Name) = '')",
                        (it.name, it.code))
        if update_prices:
            for it in plan['update_price']:
                con.execute(f'UPDATE Menu SET {set_prices} WHERE No = ?',
                            (it.gold,) * 5 + (it.cash,) * 5 + (it.code,))


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Sincroniza itens do avatar.xfs com a tabela Menu (upsert).')
    ap.add_argument('--xfs', default=DEFAULT_XFS, help='avatar.xfs (WC S1/TH) ou GunBound.xfs (S2)')
    ap.add_argument('--db', default=DEFAULT_DB, help='arquivo SQLite ou URI sqlite+aiosqlite:///...')
    ap.add_argument('--dry-run', action='store_true', help='só mostra o plano (padrão)')
    ap.add_argument('--apply', action='store_true', help='grava no banco')
    ap.add_argument('--update-prices', action='store_true', help='atualiza preços de linhas existentes')
    ap.add_argument('--show', type=int, default=10, help='quantas linhas de exemplo mostrar')
    args = ap.parse_args(argv)
    if args.apply and args.dry_run:
        ap.error('use só um: --dry-run ou --apply')

    records = xfs_reader.extract_records(args.xfs)
    catalog, conflicts, inconsistent = build_catalog(records)
    db_path = sqlite_path(args.db)
    if not os.path.exists(db_path):
        raise SystemExit(f'banco não encontrado: {db_path}')
    con = sqlite3.connect(f'file:{db_path}?mode={"rw" if args.apply else "ro"}', uri=True)
    try:
        plan = plan_sync(con, catalog, args.update_prices)
        if args.apply:
            apply_sync(con, plan, args.update_prices)
    finally:
        con.close()

    mode = 'APLICADO' if args.apply else 'DRY-RUN (nada gravado)'
    print(f'Modo: {mode}')
    print(f'XFS: {args.xfs}')
    print(f'Banco: {db_path}')
    print(f'Registros de item lidos: {len(records)}')
    print(f'Códigos únicos consolidados: {len(catalog)}')
    print(f'Conflitos (chave com nome/preço diferente, ignorados): {len(conflicts)}')
    print(f'Chaves inconsistentes com o arquivo (ignoradas): {len(inconsistent)}')
    print(f'Não vendáveis (tier 4 desligado, preço 0 ou sentinela 9999990, ignorados): {len(plan["not_sellable"])}')
    print(f'Inserções novas (INSERT): {len(plan["insert"])}')
    print(f'Preenchimento de nome em linhas existentes: {len(plan["fill_name"])}')
    print(f'Atualização de preço: {len(plan["update_price"])}'
          f'{"" if args.update_prices else " (use --update-prices; preços diferentes mantidos: " + str(len(plan["price_differs_kept"])) + ")"}')
    print(f'Linhas existentes sem mudança: {plan["unchanged"]}')
    if plan['insert']:
        print('\nExemplos de inserção:')
        for it in plan['insert'][:args.show]:
            print(f'  {it.code:#08x} {it.name:23s} gold={it.gold:<8d} cash={it.cash:<7d} '
                  f'sexo={it.genders} slot={it.slots} arquivos={",".join(it.sources)}')
    if conflicts:
        print('\nExemplos de conflito:')
        for c in conflicts[:args.show]:
            print(f'  {c["code"]:#08x} nomes={c["names"]} arquivos={c["sources"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
