"""
Partida: início (0x3430), morte (0x4100), ressurreição (0x4104), fim por jóia (0x4200), resultado (0x4412),
túnel (0x4500) e volta para a sala (0x3232). Turno, tiro e dano são UDP entre clientes (Protocolo-Salas.md 6.6).
"""
from __future__ import annotations
import asyncio
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import RoomMode
from gunbound.game import phase, room_packets as rp
from gunbound.game.protocol.gm_commands import start_game
from gunbound.game.protocol.base import GameRecv, Packet, EncryptedPacket, decrypt_blocks, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket
from gunbound.util.binary_buffer import PacketError

WINNER_DELAY = 0.3      # F3: 0x4410 300 ms depois da última morte
JEWEL_DELAY = 2.0       # F3: rebroadcast do 0x4200 2 s depois
MAX_TUNNEL = 1024
# Limites por partida contra resultado forjado (o 0x4412 vem do cliente). shortcut: valores sem fonte WC.
MAX_GOLD = 3000  # teto antes do multiplicador
MAX_GP = 200


def reward_caps(config) -> tuple[int, int]:
    """O cliente já aplica GoldFactor/ScoreFactor (enviados no login) no 0x4412; só o teto escala, sem multiplicar de novo."""
    return MAX_GOLD * int(config['gold_factor']) // 100, MAX_GP * int(config['score_factor']) // 100
RESULT_BLOCK = 18


async def announce_winner(room, team: int, delay: float = WINNER_DELAY):
    await asyncio.sleep(delay)
    if room.game is not None:
        await room.broadcast(rp.winner(team))


@handler(ClientPacket.CLI_START_GAME, master=True, waiting=True)
class StartGameRecv(GameRecv):
    """Corpo opaco devolvido como eco no fim do 0x3432 (cifrado, para todos)."""

    async def handle(self):
        room = self.room
        reason = room.start_check(self.conn)
        if reason:
            print(f"[{self.conn.addr}] Iniciar partida recusado: {reason}")
            return
        await start_game(room, self.conn, self.buf.read_bytes()[:64])


@handler(ClientPacket.CLI_GAME_DEAD, in_game=True)
class GameDeadRecv(GameRecv):
    """cause u8. 0x4101 para quem morreu, 0x4102 (cifrado) para a sala e, se acabou, 0x4410."""

    async def handle(self):
        room = self.room
        player = room.player(self.conn)
        if player is None or not player.alive:
            return
        winner = room.on_dead(self.conn)
        await self.conn.on_send(Packet.new(ServerPacket.SRV_GAME_DEAD_ACK))
        await room.broadcast(rp.player_dead(player.slot, player.team))
        if winner != -1:
            asyncio.create_task(announce_winner(room, winner))


@handler(ClientPacket.CLI_GAME_RESURRECT, in_game=True)
class GameResurrectRecv(GameRecv):
    """Cifrado, corpo sem layout conhecido. Só vale no Score e se o time ainda tiver vidas."""

    async def handle(self):
        try:
            decrypt_blocks(self.conn, self.buf.read_bytes(), self.command)
        except PacketError as e:
            print(f"[{self.conn.addr}] 0x4104 inválido: {e}")
            return
        self.room.on_resurrect(self.conn)


@handler(ClientPacket.CLI_GAME_JEWEL_END, in_game=True)
class GameJewelEndRecv(GameRecv):
    """Só no Jewel: o texto claro vira o 0x4410 (cifrado) para a sala inteira, 2 s depois."""

    async def handle(self):
        room = self.room
        if room.options.mode != RoomMode.JEWEL or room.game.winner != -1:
            return
        try:
            plain = decrypt_blocks(self.conn, self.buf.read_bytes(), self.command).read_bytes()
        except PacketError as e:
            print(f"[{self.conn.addr}] 0x4200 inválido: {e}")
            return
        room.game.winner = plain[0] if plain and plain[0] in (0, 1) else room.player(self.conn).team
        asyncio.create_task(self.rebroadcast(room, plain))

    async def rebroadcast(self, room, plain: bytes):
        await asyncio.sleep(JEWEL_DELAY)
        if room.game is not None:
            await room.broadcast(EncryptedPacket.build(ServerPacket.SRV_GAME_WINNER, plain))


@handler(ClientPacket.CLI_GAME_RESULT, in_game=True)
class GameResultRecv(GameRecv):
    """
    Cifrado. qtd u8 + qtd blocos de 18 bytes (ignorado u8, slot u8, gold, bonus, evento, gp, hits, -, dano, -).
    Processa uma vez por partida, limita gold/gp, credita no banco e manda 0x4413 para a sala; a sala volta a aguardar.
    """

    @inject
    async def handle(self, inventory_repository=Provide['inventory_repository'], user_repository=Provide['user_repository']):
        room = self.room
        if room.game.result_sent:
            return
        try:
            body = decrypt_blocks(self.conn, self.buf.read_bytes(), self.command)
        except PacketError as e:
            print(f"[{self.conn.addr}] 0x4412 inválido: {e}")
            return
        room.game.result_sent = True
        max_gold, max_gp = reward_caps(self.conn.server.config)
        rewards = []
        if phase.of(self.conn).result_v584:
            await self.v584(room, body, max_gold, max_gp, rewards)
        count = min(body.read_uint8(), room.player_count()) if body.remaining() else 0
        for _ in range(count):
            if body.remaining() < RESULT_BLOCK:
                break
            body.read_uint8()
            slot = body.read_uint8()
            gold, bonus, _event, gp = (body.read_uint16() for _ in range(4))
            body.read_bytes(RESULT_BLOCK - 10)
            player = room.player_by_slot(slot)
            if player is not None:
                rewards.append((player, min(gold + bonus, max_gold), min(gp, max_gp)))
        await asyncio.gather(*(self.credit(p.conn, g, s, inventory_repository, user_repository) for p, g, s in rewards))
        for hook in room.result_hooks:
            await hook(room, room.game.winner)
        room.finish()
        await room.broadcast(Packet.new(ServerPacket.SRV_GAME_RESULT))

    async def v584(self, room, body, max_gold, max_gp, rewards):
        """v584: o 0x4412 só traz contagens; calcula gold/GP aqui e mostra no 0x4415 (wcs2/result.py)."""
        from gunbound.game.protocol.wcs2 import result
        from gunbound.game.protocol.wcs2.bonus import BONUS
        shown = []
        for row in result.parse(body):
            player = room.player_by_slot(row['slot'])
            if player is None:
                continue
            gold, gp = result.reward(row, self.conn.server.config)
            gold, gp = max(0, min(gold, max_gold)), max(-max_gp, min(gp, max_gp))
            rewards.append((player, gold, gp))
            bonus = BONUS.get(room.game.bonus_event, (0, 0)) if player.slot in room.game.bonus_paid else (0, 0)
            shown.append((player.slot, gold, bonus[0], gp, bonus[1]))
        await room.broadcast(result.reward_packet(shown))

    @staticmethod
    async def credit(conn, gold: int, gp: int, inventory_repository, user_repository):
        user_id = conn.data['profile']['Id']
        if gold:
            await inventory_repository.update_money(user_id, gold)
        if gp:
            await user_repository.add_score(user_id, gp)
        game = conn.data['game']
        game['Money'] = (game.get('Money') or 0) + gold
        game['TotalScore'] = (game.get('TotalScore') or 0) + gp
        game['SeasonScore'] = (game.get('SeasonScore') or 0) + gp


@handler(ClientPacket.CLI_ROOM_RETURN_RESULT, room=True)
class RoomReturnResultRecv(GameRecv):
    """
    Volta para a sala depois do resultado -> 0x3233. Se a partida acabou (vencedor definido) mas o 0x4412 nunca
    chegou, o primeiro retorno fecha a partida para a sala não ficar presa "em jogo".
    """

    async def handle(self):
        room = self.room
        player = room.player(self.conn)
        if player is None:
            return
        player.returned = True
        if room.game is not None and room.game.winner != -1 and not room.game.result_sent:
            room.finish()
        await self.conn.on_send(rp.ack(ServerPacket.SRV_ROOM_RETURN_RESULT))


@handler(ClientPacket.CLI_GAME_TUNNEL, room=True)
class GameTunnelRecv(GameRecv):
    """
    Original (0x429f38 / FUN_00418650): qtd u8 (1..8) + u8 ignorado + slots[qtd] + dados.
    Entrega 0x4501 (origin_slot + dados) a cada slot listado, inclusive o próprio remetente (necessário no jogo solo).
    """

    async def handle(self):
        room = self.room
        count = self.buf.require(2).read_uint8()
        self.buf.read_uint8()
        if not 1 <= count <= 8:
            return
        slots = self.buf.require(count).read_bytes(count)
        me = room.player(self.conn)
        data = self.buf.read_bytes()
        if me is None or len(data) > MAX_TUNNEL:
            return
        packet = rp.tunnel(me.slot, data)
        for dest in filter(None, (room.player_by_slot(s) for s in slots)):
            await dest.conn.on_send(packet.clone())  # on_send altera o buffer (tamanho/checksum)
