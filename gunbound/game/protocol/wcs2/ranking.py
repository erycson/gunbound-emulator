"""
Janela Ranking (CPopup_Ranking, vtable 0x6100b4) do cliente v584. Endereços VA do GunBound.gme.

Estado da janela: +0x9c sub-aba (0/1, botões 0x1713/0x1714), +0x9d aba (0/2/4/6), +0x9e filtro de mobile (0 = todos),
+0x9f flag. Tipo = +0x9c + +0x9d (0..7).
0x7040 C->S (0x5230e0): u8 tipo, u8 mobile, u8 flag. Flag 1 = lista normal; flag 0 = "My Rank" (o botão só funciona
  depois de uma resposta com minha posição != 0, global+0x6f5a0). O cliente guarda a resposta por (tipo | mobile<<8)
  em global+0x6f57c (flag 1) / +0x6f588 (flag 0) e não pede de novo o que já tem.
0x7041 S->C (switch 0x40f740, case 0x4133d0; sem RTC): u8 tipo, u8 mobile, u8 flag, u16 minha posição (0 = fora),
  16 bytes texto da minha 3a coluna, u8 n, n x [u16 posição, u16 grade (sprite 0x66), apelido 12, guild 8, texto 16].
  A linha "eu" usa meu apelido/guild/grade do login (0x413629). Desenho em 0x522ab0: posição "%d", grade, apelido,
  guild e o texto de 16 bytes.
shortcut: aba 2 (+0x9d=2) = guild e 4 = ladder (GrandPrix_Personal) pela ordem dos botões; as outras = jogadores.
  Sub-aba 1 = MONTH (SeasonScore), 0 = TOTAL. Os nomes das abas são imagem, não conferi a ordem no jogo.
shortcut: filtro de mobile ignorado (mesma lista para todos); MobileRecords tem os dados se precisar.
shortcut: lê a tabela toda e ordena em Python; trocar por LIMIT/OFFSET se a base crescer muito.
"""
from dependency_injector.wiring import Provide, inject
from gunbound.game.protocol.base import GameRecv, Packet, handler

CLI_RANKING, SRV_RANKING = 0x7040, 0x7041
PAGE = 100  # u8 no pacote
GM_GRADE = 0  # admin na escala do S2
TAB_GUILD, TAB_LADDER = 2, 4

PLAYERS = ("SELECT Id, Nickname, Guild, {grade} AS Grade, {score} AS Score FROM Game "
           f"WHERE {{grade}} <> {GM_GRADE} ORDER BY {{score}} DESC, Nickname")
GUILDS = ("SELECT Guild AS Id, Guild AS Nickname, '' AS Guild, 0 AS Grade, SUM(TotalScore) AS Score FROM Game "
          f"WHERE Guild <> '' AND TotalGrade <> {GM_GRADE} GROUP BY Guild ORDER BY Score DESC, Guild")
LADDER = ("SELECT u.Id, u.Nickname, u.Guild, u.TotalGrade AS Grade, g.Score FROM GrandPrix_Personal AS g "
          "INNER JOIN Game AS u ON g.User=u.Id ORDER BY g.Score DESC, u.Nickname")


def query(kind: int) -> str:
    tab, month = kind & 6, kind & 1
    if tab == TAB_GUILD:
        return GUILDS
    if tab == TAB_LADDER:
        return LADDER
    return PLAYERS.format(grade='SeasonGrade' if month else 'TotalGrade', score='SeasonScore' if month else 'TotalScore')


def page(rows: list, me: str, mine: bool) -> tuple[int, list]:
    """(minha posição, [(posição, linha)]): top PAGE, ou PAGE em volta de mim no My Rank."""
    pos = next((i + 1 for i, r in enumerate(rows) if r['Id'] == me), 0)
    start = max(0, pos - 1 - PAGE // 2) if mine and pos else 0
    return pos, [(start + i + 1, r) for i, r in enumerate(rows[start:start + PAGE])]


def ranking_resp(kind: int, mobile: int, flag: int, pos: int, my_score, entries: list) -> Packet:
    pkt = (Packet.new(SRV_RANKING).u8(kind).u8(mobile).u8(flag).u16(min(pos, 0xFFFF))
           .fixed(str(my_score) if pos else '', 16).u8(len(entries)))
    for n, r in entries:
        pkt.u16(min(n, 0xFFFF)).u16(int(r['Grade'] or 0)).fixed(r['Nickname'], 12).fixed(r['Guild'], 8).fixed(str(int(r['Score'] or 0)), 16)
    return pkt


@handler(CLI_RANKING, register=False)
class RankingRecv(GameRecv):

    @inject
    async def handle(self, db=Provide['database']):
        buf = self.buf.require(3)
        kind, mobile, flag = buf.read_uint8(), buf.read_uint8(), buf.read_uint8()
        if kind > 7:
            return
        rows = await db.fetch_all(query(kind))
        game = self.conn.data['game']
        me = game['Guild'] if kind & 6 == TAB_GUILD else self.user_id()
        pos, entries = page(rows, me, flag == 0)
        my_score = int(rows[pos - 1]['Score'] or 0) if pos else 0
        await self.conn.on_send(ranking_resp(kind, mobile, flag, pos, my_score, entries))
