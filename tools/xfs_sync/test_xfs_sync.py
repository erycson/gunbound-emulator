"""
Testes pequenos do xfs_sync. Não dependem dos arquivos do jogo nem do gbwc.db real.

Rodar: python -I test_xfs_sync.py
"""
import os
import sqlite3
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xfs_reader  # noqa: E402
import item_sync  # noqa: E402
import set_sync  # noqa: E402


def make_item(code, name, gold, cash):
    """Registro de 644 bytes no layout decodificado (ver xfs_reader). code é a chave u32 completa."""
    rec = bytearray(xfs_reader.ITEM_STRIDE)
    struct.pack_into('<I', rec, 0, code)
    rec[12:12 + len(name)] = name.encode('latin-1')
    for g_off, c_off, f_off in xfs_reader.PRICE_TIERS:
        struct.pack_into('<I', rec, g_off, gold)
        struct.pack_into('<I', rec, c_off, cash)
        struct.pack_into('<I', rec, f_off, 1)
    return bytes(rec)


def make_group(records):
    return struct.pack('<I', len(records)) + b''.join(records)


def make_container(groups):
    """Monta um XFS2 mínimo: grupos com bloco final, trailer com cabeçalho e tabela de 128 bytes por entrada."""
    body = bytearray(4)
    entries = []
    for name, data in groups:
        off = len(body)
        comp = zlib.compress(data)
        body += struct.pack('<HBH', len(data), 0x80, len(comp)) + b'\0' * 3 + comp
        entries.append((name, off, len(data)))
    ptr = len(body)
    header = b'XFS2' + struct.pack('<I', 0) + struct.pack('<I', len(entries)) + b'\0' * 48
    body += b'\x41' + zlib.compress(header) + b'\0' * 3
    table = bytearray()
    for name, off, dec in entries:
        e = bytearray(128)
        e[:len(name)] = name.encode()
        struct.pack_into('<I', e, 112, off)
        struct.pack_into('<I', e, 116, 1)
        struct.pack_into('<I', e, 120, dec)
        table += e
    body += zlib.compress(bytes(table))
    body[0:4] = struct.pack('<I', ptr)
    return bytes(body)


class ReaderTest(unittest.TestCase):
    def test_extract_records_from_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'mini.xfs')
            data = make_container([
                ('mb.dat', make_group([make_item(0x8001, 'Space Marine', 20000, 2000)])),
                ('fb.dat', make_group([make_item(5, 'Cat Eyes', 9000, 300), make_item(6, 'Hat', 0, 0)])),
                ('ex1.dat', b'11111'),  # grupo que não é tabela de itens: deve ser ignorado
            ])
            with open(path, 'wb') as f:
                f.write(data)
            recs = xfs_reader.extract_records(path)
        self.assertEqual([r.code for r in recs], [0x8001, 5, 6])
        self.assertEqual(recs[0].name, 'Space Marine')
        self.assertEqual(recs[0].source, 'mb.dat')
        self.assertEqual(recs[0].tiers[4].gold, 20000)
        self.assertEqual(recs[1].tiers[4].cash, 300)


class CatalogTest(unittest.TestCase):
    def test_conflict_is_excluded_and_sentinel_not_sellable(self):
        P = xfs_reader.PriceTier
        recs = [
            xfs_reader.ItemRecord(0x8001, 'A', 'mb.dat', 10, 1, 0, [P(1, 1, True)] * 5),
            xfs_reader.ItemRecord(0x8001, 'B', 'mb.dat', 10, 1, 0, [P(1, 1, True)] * 5),  # mesmo código, nome diferente
            xfs_reader.ItemRecord(0x18002, 'C', 'mh.dat', 10, 1, 0, [P(0, 0, True)] * 4 + [P(9999990, 999999, True)]),
            xfs_reader.ItemRecord(0x3800F, 'D', 'mf.dat', 10, 1, 0, [P(5000, 500, True)] * 5),
            xfs_reader.ItemRecord(0x0000F, 'E', 'mf.dat', 10, 1, 0, [P(5000, 500, True)] * 5),  # chave não bate com o arquivo
        ]
        catalog, conflicts, inconsistent = item_sync.build_catalog(recs)
        self.assertNotIn(0x8001, catalog)
        self.assertEqual(conflicts[0]['code'], 0x8001)
        self.assertEqual([x['code'] for x in inconsistent], [0x0000F])
        self.assertFalse(catalog[0x18002].sellable)
        self.assertTrue(catalog[0x3800F].sellable)
        self.assertEqual(catalog[0x3800F].genders, 'M')
        self.assertEqual(catalog[0x3800F].slots, 'Etc')


class SyncTest(unittest.TestCase):
    def test_upsert_never_deletes_and_fills_only_empty_names(self):
        con = sqlite3.connect(':memory:')
        price_cols = ', '.join(f'PriceByGoldFor{p} INT, PriceByCashFor{p} INT' for p in item_sync.PERIODS)
        con.execute(f'CREATE TABLE Menu (No INT PRIMARY KEY, Name TEXT, Item1 INT, Period1 INT, Volume1 INT, '
                    f'{price_cols})')
        con.execute("INSERT INTO Menu (No, Name, Item1, Period1, Volume1) VALUES (100, NULL, 100, 86400, 1)")
        con.execute("INSERT INTO Menu (No, Name, Item1, Period1, Volume1) VALUES (200, 'Antigo', 200, 86400, 1)")
        catalog = {
            100: item_sync.CatalogItem(100, 'Novo', 6000, 200, sellable=True),
            300: item_sync.CatalogItem(300, 'Item Novo', 9000, 300, sellable=True),
        }
        plan = item_sync.plan_sync(con, catalog, update_prices=False)
        self.assertEqual([i.code for i in plan['insert']], [300])
        self.assertEqual([i.code for i in plan['fill_name']], [100])
        item_sync.apply_sync(con, plan, update_prices=False)
        rows = dict((r[0], r[1]) for r in con.execute('SELECT No, Name FROM Menu'))
        self.assertEqual(rows, {100: 'Novo', 200: 'Antigo', 300: 'Item Novo'})
        self.assertEqual(con.execute('SELECT PriceByGoldForW FROM Menu WHERE No=300').fetchone()[0], 9000)
        self.assertEqual(con.execute('SELECT PriceByGoldForW FROM Menu WHERE No=100').fetchone()[0], None)


class SetSyncTest(unittest.TestCase):
    def test_parse_and_insert_set_with_items(self):
        rec = bytearray(set_sync.SET_STRIDE)
        struct.pack_into('<I', rec, 0, 0x30001)
        rec[20:20 + 19] = b'Golden Armor Set(M)'
        struct.pack_into('<I', rec, 96, 630000)
        struct.pack_into('<I', rec, 100, 63000)
        for k, (code, vol) in enumerate([(0x18029, 1), (0x8027, 1), (0x28001, 1)]):
            struct.pack_into('<III', rec, 112 + k * 12, code, vol, 0xFFFFFFFF)
        for k in range(3, 5):
            struct.pack_into('<III', rec, 112 + k * 12, 0, 1, 0xFFFFFFFF)
        empty = bytearray(set_sync.SET_STRIDE)
        struct.pack_into('<I', empty, 112, 0)
        data = struct.pack('<I', 2) + bytes(rec) + bytes(empty)
        sets = set_sync.parse_sets(data)
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0]['code'], 0x30001)
        self.assertEqual(sets[0]['name'], 'Golden Armor Set(M)')
        self.assertEqual([c for c, _ in sets[0]['items']], [0x18029, 0x8027, 0x28001])

        con = sqlite3.connect(':memory:')
        price_cols = ', '.join(f'PriceByGoldFor{p} INT, PriceByCashFor{p} INT' for p in item_sync.PERIODS)
        item_cols = ', '.join(f'Item{n} INT, Period{n} INT, Volume{n} INT' for n in range(1, 6))
        con.execute(f'CREATE TABLE Menu (No INT PRIMARY KEY, Name TEXT, {item_cols}, {price_cols})')
        plan = set_sync.plan_sets(con, sets)
        self.assertEqual(len(plan['insert']), 1)
        sets[0]['gold'] = item_sync.PRICE_SENTINEL_GOLD
        self.assertEqual(set_sync.plan_sets(con, sets)['insert'], [])  # sentinela = sem venda
        sets[0]['gold'] = 630000
        set_sync.apply_sets(con, plan)
        row = con.execute('SELECT Item1, Item2, Item3, Item4, Item5, Volume1, PriceByGoldForW, PriceByCashForI '
                          'FROM Menu WHERE No=196609').fetchone()
        self.assertEqual(row, (0x18029, 0x8027, 0x28001, None, None, 1, 630000, 63000))
        self.assertEqual(set_sync.plan_sets(con, sets)['insert'], [])  # idempotente

    def test_ex2_sellable_power_user_and_sentinel_skipped(self):
        def rec(code, name, gold, item):
            r = bytearray(set_sync.SET_STRIDE)
            struct.pack_into('<I', r, 0, code)
            r[20:20 + len(name)] = name.encode('latin-1')
            struct.pack_into('<I', r, 96, gold)
            struct.pack_into('<I', r, 100, gold // 10)
            struct.pack_into('<III', r, 112, item, 1, 0xFFFFFFFF)
            return bytes(r)
        data = struct.pack('<I', 2) + rec(0x32002, 'Power User (1wk)', 35000, 0x32001)             + rec(0x32020, 'Power User (2wk)', 9999990, 0x32001)
        sets = set_sync.parse_sets(data)
        self.assertEqual([s['code'] for s in sets], [0x32002, 0x32020])
        con = sqlite3.connect(':memory:')
        con.execute('CREATE TABLE Menu (No INT PRIMARY KEY, Name TEXT, Item1 INT, Item2 INT, Item3 INT, Item4 INT, '
                    'Item5 INT, Period1 INT, Period2 INT, Period3 INT, Period4 INT, Period5 INT, Volume1 INT, '
                    'Volume2 INT, Volume3 INT, Volume4 INT, Volume5 INT, '
                    + ', '.join(f'PriceByGoldFor{p} INT, PriceByCashFor{p} INT' for p in item_sync.PERIODS) + ')')
        plan = set_sync.plan_sets(con, sets)
        self.assertEqual([s['code'] for s in plan['insert']], [0x32002])
        self.assertEqual(len(plan['not_sellable']), 1)


TH_AVATAR = r'D:\GBWCProject\clientes\TH-v404\avatar.xfs'


class ThTest(unittest.TestCase):
    def test_th_item_e_set(self):  # registros abertos do TH: item 148 (preço único @40/@44, vende @48), set 188
        it = bytearray(148)
        struct.pack_into('<II', it, 0, 0x18072, 114)
        it[12:12 + 6] = b'Wizard'
        struct.pack_into('<IIB', it, 40, 70000, 7000, 1)
        recs = xfs_reader.parse_item_table(struct.pack('<I', 1) + bytes(it), 'mb.dat')
        self.assertEqual((recs[0].code, recs[0].name), (0x18072, 'Wizard'))
        self.assertEqual({(t.gold, t.cash, t.enabled) for t in recs[0].tiers}, {(70000, 7000, True)})
        st = bytearray(188)
        struct.pack_into('<I', st, 0, 0x30001)
        st[20:20 + 4] = b'Gold'
        struct.pack_into('<II', st, 48, 630000, 63000)
        struct.pack_into('<III', st, 64, 0x18029, 1, 0xFFFFFFFF)
        sets = set_sync.parse_sets(struct.pack('<I', 1) + bytes(st))
        self.assertEqual((sets[0]['gold'], sets[0]['cash'], sets[0]['items']), (630000, 63000, [(0x18029, 1)]))

    @unittest.skipUnless(os.path.exists(TH_AVATAR), 'cliente TH não encontrado')
    def test_th_avatar_real(self):
        recs = xfs_reader.extract_records(TH_AVATAR)
        self.assertEqual(next(r for r in recs if r.name == 'Apprentice Wizard').tiers[4].gold, 70000)
        self.assertTrue(any(s['name'] == 'Golden Armor Set(M)' for s in set_sync.load_sets(TH_AVATAR)))


if __name__ == '__main__':
    unittest.main()
