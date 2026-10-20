"""Fases do cliente (gunbound/game/phase.py). Uso: python -m unittest tests.test_phase"""
import unittest
from types import SimpleNamespace as N
from gunbound.game import phase
from gunbound.game.protocol.base import Packet

V440, V584 = phase.load('WCS1'), phase.load('WCS2')


def size(pkt):
    return len(pkt.buf.getvalue())


class StrategyTest(unittest.TestCase):
    def test_escolha_pela_config(self):
        self.assertIs(phase.of(N(server=N(config={}))), V440)
        self.assertIs(phase.of(N(server=N(config={'phase': 'WCS2'}))), V584)

    def test_tabela_de_opcodes(self):
        from gunbound.game.protocol.grandprix import GrandPrixListRecv, GrandPrixBeginRecv
        th, wcs1, wcs2 = phase.TH.handlers(), phase.WCS1.handlers(), phase.WCS2.handlers()
        self.assertNotIn(0x1100, th)                        # GP nasce no WCS1
        self.assertIs(wcs1[0x1100], GrandPrixListRecv)      # add
        self.assertIsNot(th[0x2140], GrandPrixBeginRecv)    # TH: só SilentRecv
        self.assertIs(wcs1[0x2140], GrandPrixBeginRecv)     # replace (antes o SilentRecv do misc.py sobrescrevia)
        self.assertTrue(set(wcs1) < set(wcs2))              # WCS2 só acrescenta
        self.assertIn(0x7500, wcs2)
        self.assertIn(0x1010, th)

    def test_regras_add_replace_remove(self):
        class Novo(phase.WCS1): parent, add, replace = phase.WCS1, {0x7777: object}, {}
        class Troca(phase.WCS1): parent, add, replace = phase.WCS1, {}, {0x2010: object}
        class Tira(phase.WCS1): parent, add, replace, remove = phase.WCS1, {}, {}, frozenset({0x2010})
        self.assertIs(Novo.handlers()[0x7777], object)
        self.assertIs(Troca.handlers()[0x2010], object)
        self.assertNotIn(0x2010, Tira.handlers())
        class AddRepetido(phase.WCS1): parent, add, replace = phase.WCS1, {0x2010: object}, {}
        class ReplaceInexistente(phase.WCS1): parent, add, replace = phase.WCS1, {}, {0x7777: object}
        class RemoveInexistente(phase.WCS1): parent, add, replace, remove = phase.WCS1, {}, {}, frozenset({0x7777})
        for bad in (AddRepetido, ReplaceInexistente, RemoveInexistente):
            with self.assertRaises(AssertionError):
                bad.handlers()

    def test_avatar(self):  # 0x2111/0x3010: 4 -> 10 bytes por item
        self.assertEqual(size(V584.write_avatar(Packet.new(1), [7, 8])) - size(V440.write_avatar(Packet.new(1), [7, 8])), 12)

    def test_detalhe_da_sala(self):  # 0x2105: 0x1E bytes no v440 (guild em +0xE, grade em +0x16), 0x22 no v584
        p = N(team=1, conn=N(data={'profile': {'Nickname': 'abc'}, 'game': {'Guild': 'g', 'TotalGrade': 5}}))
        base = size(Packet.new(1))
        old = V440.write_detail_player(Packet.new(1), p).buf.getvalue()[base:]
        self.assertEqual((len(old), old[0xD], old[0xE:0xF], old[0x16]), (0x1E, 1, b'g', 5))
        self.assertEqual(size(V584.write_detail_player(Packet.new(1), p)) - base, 0x22)

    def test_chat(self):  # 0x201F: tamanho em +15 e texto em +16 no v584
        old, new = V440.chat_body(2, 'nick', 'oi'), V584.chat_body(2, 'nick', 'oi')
        self.assertEqual((old[13], old[14:]), (2, b'oi'))
        self.assertEqual((new[15], new[16:]), (2, b'oi'))

    def test_inicio_da_partida(self):  # 0x3432: seed em +2 no v440 e +3 no v584
        echo = (1234).to_bytes(4, 'little')
        self.assertEqual(V440.game_start_tail(echo)[2:6], echo)
        self.assertEqual(V584.game_start_tail(echo)[3:7], echo)
        self.assertEqual(len(V584.game_start_tail(echo)), 2 + 1 + 4 + 1)  # byte final que o 0x3430 não traz
        self.assertEqual(V584.game_start_tail(echo)[-1], 0xFF)  # sem evento de bônus (0 ligaria o tipo 0)

    def test_grand_prix(self):  # 0x1101: grupo 24 -> 44, pessoa 36 -> 56, eu 24 -> 44
        import struct
        g = V584.gp_group(struct.pack('<6i', 7, 900, 3, -1, 10, 4), 7)  # Category, Pontos, Rank, Diff, Win, Lose
        self.assertEqual(len(g), 44)
        self.assertEqual(struct.unpack_from('<3i', g, 0) + (g[0xC:0xD],) + struct.unpack_from('<3i', g, 0x20), (3, -1, 7, b'7', 900, 10, 4))
        self.assertEqual(V584.gp_person(bytes(24) + b'nick'.ljust(12, b'\x00'))[0x2C:0x30], b'nick')
        self.assertEqual(len(V584.gp_person(bytes(36))), 56)
        self.assertEqual((len(V440.gp_me(bytes(36))), len(V584.gp_me(bytes(36)))), (24, 44))

    def test_grand_prix_wcs1(self):  # 0x1101 v495 (WCS1): mesmo tamanho do v440, grupo reordenado (docs/Cliente v495 x v440.md)
        import struct
        v495 = V440
        g = v495.gp_group(struct.pack('<6i', 7, 900, 3, -1, 10, 4), 7)  # Category, Pontos, Rank, Diff, Win, Lose
        self.assertEqual(struct.unpack('<6i', g), (3, -1, 7, 900, 10, 4))
        self.assertEqual(len(v495.gp_person(bytes(36))), 36)


    def test_th(self):  # docs/Cliente TH v404 x v440.md
        th = phase.load('TH')
        game = {'TotalGrade': 5, 'SeasonGrade': 6, 'CountryGrade': 7, 'Country': 8, 'MemberCount': 1,
                **{k: 0 for k in ('TotalRank', 'SeasonRank', 'GuildRank', 'CountryRank', 'AccumShot', 'AccumDamage',
                                  'TotalScore', 'SeasonScore', 'Money', 'EventScore0', 'EventScore1', 'EventScore2', 'EventScore3')}}
        self.assertEqual((len(th.grades(game)), len(V440.grades(game))), (4, 8))
        self.assertEqual(len(V440.login_stats(game)) - len(th.login_stats(game)), 4)  # sem CountryRank
        p = N(team=1, conn=N(data={'profile': {'Nickname': 'abc'}, 'game': game}))
        self.assertEqual(size(th.write_detail_player(Packet.new(1), p)) - size(Packet.new(1)), 0x19)
        self.assertEqual((th.list_entry_extra(), V440.list_entry_extra()), (b'', b'\x00'))
        self.assertEqual((th.chest_tail({'Recovered': 1}), V440.chest_tail({'Recovered': 1})), (b'', b'\x01'))
        item = {'Recovered': 1, 'EnchantLevel': 7}
        self.assertEqual([V584.chest_tail(item, v) for v in (4, 548, 0)], [b'\x01\x07\x00\x00\x00\x00\x00', b'\x01', b'\x01'])
        self.assertEqual((th.kick_ack, V440.kick_ack), (0x3151, 0x315F))
        self.assertFalse(phase.WC_ONLY & set(phase.TH.handlers()))
        self.assertTrue(phase.WC_ONLY <= set(phase.WCS1.handlers()))
        self.assertIn(0x00628B68, phase.TH.product_versions)

    def test_product_version(self):
        self.assertIn(0x04FCCB1C, V584.product_versions)
        self.assertEqual(V440.product_versions, {0x04FCCB1C})  # v495; o v440 usa config['product_version']
        self.assertNotIn('WCS1GP', phase.PHASES)

    def test_sistemas_por_fase(self):
        self.assertNotIn('grandprix', phase.TH.systems)
        self.assertIn('grandprix', phase.WCS2.systems)               # herdado do WCS1
        gp = {'grandprix': {'enabled': True}}
        with self.assertRaises(ValueError):
            phase.TH.check(gp)
        phase.WCS1.check(gp)
        phase.TH.check({})
