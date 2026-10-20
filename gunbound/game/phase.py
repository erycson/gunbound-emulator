"""
Fases do GunBound (TH -> WCS1 -> WCS2 -> WCS3): cada fase herda tudo da anterior e declara só a diferença.
Escolhida por game server em config.yml (`gameservers[].phase`, ex.: WCS1). version_min/max só validam o login.

Pacotes C->S: tabela de opcodes = tabela do pai + `add` (opcode novo) + `replace` (opcode que já existe) - `remove`.
Os handlers com @handler(...) formam o catálogo do TH; handler que nasce numa fase depois usa @handler(..., register=False)
e entra no `add`/`replace` da fase. A montagem confere add/replace/remove e falha na subida do servidor.
Pacotes S->C que mudam de layout: método sobrescrito na fase (write_avatar, write_detail_player...).
Os métodos de Phase são os layouts do TH (v404), a base universal; o WCS1 (v440) sobrescreve o que o WC trouxe.
Por servidor e não por jogador: a sala manda o mesmo pacote para todos.
"""
from __future__ import annotations
import struct
from functools import cache
from typing import TYPE_CHECKING
import gunbound.game.protocol  # noqa: F401 - carrega o catálogo (@handler)
from gunbound.base.protocol import BasePackageFactory
from gunbound.game.protocol.grandprix import GrandPrixListRecv, GrandPrixBeginRecv, GrandPrixCancelRecv
from gunbound.game.protocol.wcs2 import bonus, chat_combo, lobby, enchant, events, jackpot, ranking, room as wcs2_room, shop, slot_machine
if TYPE_CHECKING:
    from gunbound.game.protocol.base import Packet

DEFAULT = 'WCS1'


class Phase:
    parent: type[Phase] | None = None
    add: dict = {}
    replace: dict = {}
    remove: frozenset = frozenset()
    product_versions: frozenset = frozenset()  # aceitos no 0x1010 além de config['product_version']
    systems: frozenset = frozenset()  # sistemas que a fase tem (herda e soma); config que liga um sistema fora da fase não sobe
    quick_create_extra: bytes = b''  # 0x2132: byte a mais depois do room_id no v584 (0x4d660b) [INCERTO: nibble alto por slot]
    result_v584 = False  # 0x4412 com contagens de eventos e resposta 0x4415 (wcs2/result.py)
    login_ready: int | None = None  # opcode S->C (RTC 0) que o cliente espera depois do 0x1012 para pedir o canal (0x2000)

    @classmethod
    def check(cls, config) -> None:
        """Na subida do game server: sistema ligado no config precisa existir na fase."""
        if (config.get('grandprix') or {}).get('enabled') and 'grandprix' not in cls.systems:
            raise ValueError(f"grandprix.enabled, mas a fase {cls.__name__} não tem Grand Prix (só WCS1 em diante)")

    @classmethod
    @cache
    def handlers(cls) -> dict:
        table = dict(cls.parent.handlers()) if cls.parent else {}
        add = cls.__dict__['add'] if 'add' in cls.__dict__ else cls.adds()  # fase que declara `add` usa o dela; TH/WCS1 montam do catálogo
        for op in add:
            assert op not in table, f'{cls.__name__}: add 0x{op:04X} já existe no pai, use replace'
        for op in (*cls.replace, *cls.remove):
            assert op in table, f'{cls.__name__}: replace/remove 0x{op:04X} não existe no pai'
        table.update(add)
        table.update(cls.replace)
        for op in cls.remove:
            del table[op]
        return table

    def write_avatar(self, pkt: 'Packet', items: list) -> 'Packet':
        """Itens do jogador no 0x2111/0x3010: u16 + u32 por item (cliente 0x4cbc29)."""
        pkt.u16(len(items))
        for item in items:
            pkt.u32(int(item))
        return pkt

    def grades(self, game: dict) -> bytes:
        """Patentes depois da guild nos blocos de jogador (0x2001, 0x200E, 0x2111, 0x3010, 0x2105, 0x1012).
        TH: TotalGrade, SeasonGrade (cliente 0x410e20/0x410e36). O país chegou no WC."""
        return struct.pack('<hh', game.get('TotalGrade') or 0, game.get('SeasonGrade') or 0)

    def login_stats(self, game: dict) -> bytes:
        """0x1012 depois das patentes: MemberCount u16 + 8 u32 (o último é o gold) + 4 eventos.
        TH (leitor 0x44bf1b): sem CountryRank; o bloco cifrado começa em +0x51."""
        ranks = ('TotalRank', 'SeasonRank', 'GuildRank', 'AccumShot', 'AccumDamage', 'TotalScore', 'SeasonScore', 'Money')
        return struct.pack('<H8I', game['MemberCount'], *(game[k] for k in ranks)) + self._events(game)

    @staticmethod
    def _events(game: dict) -> bytes:
        return struct.pack('<4I', *(game[f'EventScore{i}'] for i in range(4)))

    def write_detail_player(self, pkt: 'Packet', p) -> 'Packet':
        """Jogador no 0x2105, TH 0x19 bytes (cliente 0x430a18): apelido 12, 1 byte, guild 8 (+0xD), 2 u16 (+0x15).
        shortcut: o byte em +0xC vai como gênero; não confirmei se o TH lê gênero ou time ali."""
        profile, game = p.conn.data['profile'], p.conn.data['game']
        pkt.fixed(profile['Nickname'], 12).u8(profile.get('Gender') or 0).fixed(game.get('Guild') or '', 8)
        return pkt.raw(self.grades(game))

    def list_entry_extra(self) -> bytes:
        """0x2103: bytes entre o power user e a contagem de jogadores. TH: nenhum (cliente 0x4306ef)."""
        return b''

    def chest_tail(self, item: dict, client_version: int = 0) -> bytes:
        """0x6001: o que vem depois do 3º flag de cada item. TH: nada (cliente 0x4119e0)."""
        return b''

    kick_ack = 0x3151  # resposta ao mestre no 0x3150 (TH 0x4c2c23: RTC 0 + u8 slot)

    def chat_body(self, position: int, nickname: str, message: str) -> bytes:
        """0x201F decifrado: tamanho em +13, texto em +14 (cliente 0x42a5f0)."""
        return bytes([position]) + nickname.encode('latin-1')[:12].ljust(12, b'\x00') + bytes([len(message)]) + message.encode('latin-1')

    def game_start_tail(self, echo: bytes, bonus: int = 0xFF) -> bytes:
        """0x3432 depois dos jogadores: u16 evento (FFFF = nenhum) + eco do 0x3430 (seed u32...)."""
        return b'\xFF\xFF' + (echo or b'')

    def gp_group(self, rec: bytes, category: int) -> bytes:
        """0x1101: grupo de 24 bytes [Category, Pontos, Rank, Rank-RankOld, Win, Lose]."""
        return rec

    def gp_person(self, rec: bytes) -> bytes:
        """0x1101: pessoa de 36 bytes [Rank, Rank-RankOld, Category, Score, Win, Lose] + apelido 12."""
        return rec

    def gp_me(self, person: bytes) -> bytes:
        return person[:24]


# opcodes C->S que o TH não manda (docs/Cliente TH v404 x v440.md, seção 2): sair da sala (0x3001; o TH usa 0x2000),
# quick start, CLIENT_DATA, presente do WC (msg/confirmar/comprar) e o 0x101C
WC_ONLY = frozenset({0x3001, 0x2130, 0x1090, 0x6004, 0x6008, 0x6030, 0x101C})


def catalog() -> dict:
    # na hora do uso: phase.py pode ser importado no meio do gunbound/game/protocol/__init__, com o registro incompleto
    return {op: h for op, h in BasePackageFactory.registry.items() if h.__module__.startswith('gunbound.game.')}


class TH(Phase):
    """Cliente TH v404 (2005): a base. Sem Grand Prix e sem país; os layouts são os métodos de Phase."""

    @classmethod
    def adds(cls) -> dict:
        return {op: h for op, h in catalog().items() if op not in WC_ONLY}

    product_versions = frozenset({0x00628B68})  # 0x1010 do TH (cliente 0x44c5a6)


class WCS1(TH):
    """Clientes v440 e v495 (BR, S1). Traz o país, o Grand Prix e o presente; no TH 0x2140/0x2141 só registram atividade (SilentRecv)."""
    parent = TH
    systems = TH.systems | {'grandprix'}

    @classmethod
    def adds(cls) -> dict:
        return {GrandPrixListRecv.command: GrandPrixListRecv, **{op: catalog()[op] for op in WC_ONLY}}

    replace = {GrandPrixBeginRecv.command: GrandPrixBeginRecv, GrandPrixCancelRecv.command: GrandPrixCancelRecv}
    # 0x1010: o v440 manda config['product_version']; o v495 manda o mesmo u32 do v584 com chave Brasil
    product_versions = frozenset({0x04FCCB1C})
    kick_ack = 0x315F  # v440 0x4ec9c3

    def gp_group(self, rec: bytes, category: int) -> bytes:
        """0x1101 v495 (tela 0x50a700): grupo de 24 bytes [Rank, Rank-RankOld, Category, Pontos, Win, Lose].
        +4 o cliente nega ao receber; +8 vira o nome do grupo pela tabela de textos (docs/Cliente v495 x v440.md)."""
        cat, score, rank, diff, win, lose = struct.unpack('<6i', rec)
        return struct.pack('<6i', rank, diff, cat, score, win, lose)

    def grades(self, game: dict) -> bytes:
        """+ CountryGrade, Country (v440 0x40faff–0x40fb39)."""
        return super().grades(game) + struct.pack('<hH', game.get('CountryGrade') or 0, game.get('Country') or 0)

    def login_stats(self, game: dict) -> bytes:
        """0x1012 v440: MemberCount + 9 u32 (com CountryRank) + 4 eventos; bloco cifrado em +0x59."""
        ranks = ('TotalRank', 'SeasonRank', 'GuildRank', 'CountryRank', 'AccumShot', 'AccumDamage', 'TotalScore', 'SeasonScore', 'Money')
        return struct.pack('<H9I', game['MemberCount'], *(game[k] for k in ranks)) + self._events(game)

    def write_detail_player(self, pkt: 'Packet', p) -> 'Packet':
        """Jogador no 0x2105, 0x1E bytes (servidor original 0x42f2b0, cliente lê guild em +0xE e grade em +0x16):
        apelido 12, gênero, byte do slot, guild 8 + 4 u16 (o mesmo bloco de 16 bytes do 0x2111)."""
        profile, game = p.conn.data['profile'], p.conn.data['game']
        pkt.fixed(profile['Nickname'], 12).u8(profile.get('Gender') or 0).u8(p.team).fixed(game.get('Guild') or '', 8)
        return pkt.raw(self.grades(game))

    def list_entry_extra(self) -> bytes:
        """0x2103 v440: um byte a mais (cliente 0x4cb6be grava em +0x23edd; o 0x21F0 em 0x4cddc9 pula)."""
        return b'\x00'

    def chest_tail(self, item: dict, client_version: int = 0) -> bytes:
        """0x6001 v440: Recovered u8 (v440 0x41125f)."""
        return bytes([int(item['Recovered'])])


class WCS2(WCS1):
    """Cliente v584 (BR, 2010): mobiles Tiburon/Frank/Maya/Phoenix/Wolf/Blue Whale; layouts em docs/Cliente v584 - pacotes.md."""
    parent = WCS1
    # opcodes novos do v584; o que ficou de fora (megafone, convite, Pumpkin...) está em docs/Cliente v584 - pacotes.md
    add = {h.command: h for h in (
        chat_combo.ChatComboListRecv,
        wcs2_room.RoomChangeAllRecv, wcs2_room.ReadyItemsGetRecv, wcs2_room.ReadyItemsSetRecv,
        enchant.EnchantRecv, enchant.EnchantC35Recv, enchant.EnchantConfirmRecv, enchant.JewelEnchantRecv,
        slot_machine.SlotMachineRecv, jackpot.JackpotRecv, jackpot.JackpotBombRecv,
        shop.DiscountRecv, shop.RenaRecv, shop.ShopEnterRecv,
        *events.EVENTS.values(),
        bonus.PlayBonusRecv, bonus.StageMissionEndRecv,
        lobby.ChannelInfoRecv, lobby.ItemUseRecv, lobby.InviteListRecv, lobby.InviteSendRecv,
        ranking.RankingRecv,  # depois de events: substitui o stub events.List7040Recv
    )}
    replace = {lobby.BcmV584Recv.command: lobby.BcmV584Recv, shop.GiftMsgRecv.command: shop.GiftMsgRecv}  # 0x5010 do v584 tem tipo/cor antes do tamanho
    # 0x1010 v584 (0x5141c0): o u32 do product_version depende da chave de região do cliente (0x409cb0):
    # Turkey 20090713, Arab 20090618, Brazil 0x04FCCB1C, nenhuma 0x03E524F5
    product_versions = frozenset({20090713, 20090618, 0x04FCCB1C, 0x03E524F5})
    # v584 só manda o 0x2000 ao receber 0x1031 com RTC 0 (switch 0x514263, case 0x514a95); o v440 pede sozinho
    login_ready = 0x1031
    result_v584 = True
    quick_create_extra = b'\x00'

    def write_detail_player(self, pkt: 'Packet', p) -> 'Packet':
        """0x2105 v584: 0x22 bytes (cliente 0x4d5760): os 0x1E do v440 + u32 em +0x1E. shortcut: o u32 em 0 até descobrir o que é."""
        return super().write_detail_player(pkt, p).u32(0)

    def chest_tail(self, item: dict, client_version: int = 0) -> bytes:
        """0x6001 v584 (0x411921): Recovered u8 + u16 nível de encantamento (vai para o 0x5f0 do XPEnchantDlg) + u32.
        O v548 (0x411464) lê só o Recovered; ele manda versão 548 no login e o v584 manda 4.
        Sem o rabo novo o v584 desalinha do 2º item em diante (só o 1º caía na lista certa, memória em 2026-10-19).
        shortcut: o u32 vai em 0 (uso não identificado); versão 0 (login por senha pura, a versão não vem) fica com o
        layout antigo para não quebrar o v548; se o v584 entrar por esse caminho, achar a versão real dele."""
        if not client_version or 500 <= client_version < 584:
            return super().chest_tail(item)
        return super().chest_tail(item) + struct.pack('<HI', int(item.get('EnchantLevel') or 0), 0)

    def chat_body(self, position: int, nickname: str, message: str) -> bytes:
        """v584: 2 bytes novos depois do apelido; tamanho em +15, texto em +16 (byte +13 < 100 vira 0). shortcut: os 2 bytes em 0."""
        body = super().chat_body(position, nickname, message)
        return body[:13] + b'\x00\x00' + body[13:]

    def game_start_tail(self, echo: bytes, bonus: int = 0xFF) -> bytes:
        """v584 (leitor 0x508820): u16 evento, 1 byte não lido, seed u32 em +3, blocos (modo 3: 6x3; modo 4: 3x3) e 1 byte final.
        O 0x3430 do v584 (0x433770) traz seed + blocos, sem o byte final. Byte final = evento de bônus (+0x68474):
        0xFF = nenhum (cliente inicia com 0xFF em 0x422816 e compara em 0x4e5f99); 0..9 liga o bônus 0x4300 daquele tipo."""
        return b'\xFF\xFF\x00' + (echo or b'') + bytes([bonus & 0xFF])

    # 0x1101 v584 (leitura 0x4d5760, tela 0x538bf0/0x538750): grupo 44 bytes, pessoa 56.
    # +0 aparece sozinho em "meu grupo"/"eu" (posição), +4 é negado pelo cliente, +0xC é texto de 20 bytes,
    # +0x20/+0x24/+0x28 são as 3 colunas da lista; na pessoa o apelido fica em +0x2C.
    # shortcut: colunas = Pontos/Win/Lose e +8 = Category por analogia com o v440; os títulos das colunas são imagem, não conferi.
    def gp_group(self, rec: bytes, category: int) -> bytes:
        cat, score, rank, diff, win, lose = struct.unpack('<6i', rec)
        name = str(category).encode('latin-1')[:20].ljust(20, b'\x00')  # o banco não tem nome de grupo
        return struct.pack('<3i', rank, diff, cat) + name + struct.pack('<3i', score, win, lose)

    def gp_person(self, rec: bytes) -> bytes:
        return rec[:12] + b'\x00' * 20 + rec[12:]

    def gp_me(self, person: bytes) -> bytes:
        return self.gp_person(person)[:44]

    def write_avatar(self, pkt: 'Packet', items: list) -> 'Packet':
        """v584: 10 bytes por item (u32 + u16 + u32). shortcut: u16/u32 extras em 0 até descobrir o que são."""
        pkt.u16(len(items))
        for item in items:
            pkt.u32(int(item)).u16(0).u32(0)
        return pkt


PHASES = {c.__name__: c for c in (TH, WCS1, WCS2)}


@cache
def load(name: str) -> Phase:
    return PHASES[name]()


def of(conn) -> Phase:
    return load(conn.server.config.get('phase') or DEFAULT)
