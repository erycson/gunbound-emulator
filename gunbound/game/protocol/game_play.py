"""
Partida: início (0x3430), morte (0x4100), ressurreição (0x4104), fim por jóia (0x4200), resultado (0x4412),
túnel (0x4500) e volta para a sala (0x3232). Turno, tiro e dano são UDP entre clientes (Protocolo-Salas.md 6.6).
"""
from __future__ import annotations
import asyncio
import json
import time
from dependency_injector.wiring import Provide, inject
from gunbound.base.enums import RoomMode
from gunbound.bot import match, room as bots
from gunbound.game import phase, room_packets as rp
from gunbound.game.protocol.gm_commands import start_game
from gunbound.game.protocol.base import GameRecv, Packet, EncryptedPacket, decrypt_blocks, handler
from gunbound.game.protocol.enums import ClientPacket, ServerPacket
from gunbound.util.binary_buffer import PacketError

WINNER_DELAY = 0.3      # F3: 0x4410 300 ms depois da última morte
JEWEL_DELAY = 2.0       # F3: rebroadcast do 0x4200 2 s depois
MAX_TUNNEL = 1024
# Limites ANU_* do original (2006/2007, 0x41bb10), por registro e sobre os valores crus do 0x4412 (config `anu`).
# Acima de WRITELOG: grava AbnormalUpdate. Acima de DROP ou abaixo de DROP_*_NEG: grava, derruba o mestre e descarta o
# resultado inteiro. Não há teto nem fator no servidor (os fatores vão ao cliente no 0x1012).
ANU = {'writelog_gold': 3000, 'writelog_gp': 30, 'drop_gold': 6000, 'drop_gp': 50, 'drop_gold_neg': -2500, 'drop_gp_neg': -100}
RESULT_BLOCK = 18   # u8 slot, i32 gold, i16 pontos de evento, i16 GP, i32 tiros, i32 dano, u8 vitória


def anu_verdict(gold: int, gp: int, config) -> str:
    """'ok', 'log' ou 'drop' para um registro (mesma ordem de testes do original)."""
    a = {**ANU, **(config.get('anu') or {})}
    if gp > a['writelog_gp'] or gold > a['writelog_gold']:
        return 'drop' if gp > a['drop_gp'] or gold > a['drop_gold'] else 'log'
    if gp < a['drop_gp_neg'] or gold < a['drop_gold_neg']:
        return 'drop'
    return 'ok'


def log_tunnel(path: str, room, me, slots: bytes, data: bytes) -> None:
    """`tunnel_log` do game server: uma linha JSON por 0x4500 para mapear o P2P da partida (docs/Bots.md)."""
    line = {'t': round(time.time(), 3), 'room': room.id, 'playing': room.game is not None, 'from': me.slot,
            'nick': me.conn.data['profile']['Nickname'], 'to': list(slots), 'len': len(data), 'hex': data.hex()}
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(line) + '\n')


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
        await announce_death(room, player, winner)


async def announce_death(room, player, winner: int) -> None:
    """0x4102 para a sala e, se acabou, 0x4410. Também a morte do bot (gunbound/bot/match.py)."""
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
    Cifrado. u16 qtd (<= 8) + qtd x 18 bytes (u8 slot, i32 gold, i16 evento, i16 GP, i32 tiros, i32 dano, u8 vitória),
    como o original (2007 0x41bb10). Processa uma vez por partida, aplica os limites ANU, credita no banco e manda
    0x4413 para a sala; a sala volta a aguardar.
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
        rewards = []
        if phase.of(self.conn).result_v584:
            await self.v584(room, body, rewards)
        count = min(body.read_uint16(), 8) if body.remaining() >= 2 else 0   # 2007: u16 n (<= 8)
        for _ in range(count):
            if body.remaining() < RESULT_BLOCK:
                break
            slot, gold, _event, gp = body.read_uint8(), body.read_int32(), body.read_int16(), body.read_int16()
            body.read_bytes(RESULT_BLOCK - 9)
            player = room.player_by_slot(slot)
            if player is not None and (paid := bots.reward(room, player, gold, gp, self.conn.server.config)):
                rewards.append((player, *paid))
        if not await self.anu(rewards, user_repository):
            return
        await asyncio.gather(*(self.credit(p.conn, g, s, inventory_repository, user_repository) for p, g, s in rewards))
        if phase.of(self.conn).result_v584:
            await self.game_points(rewards, user_repository)
        for hook in room.result_hooks:
            await hook(room, room.game.winner)
        room.finish()
        await room.broadcast(Packet.new(ServerPacket.SRV_GAME_RESULT))

    async def anu(self, rewards, user_repository) -> bool:
        """ANU_* do original: registra os excessos; um DROP derruba o mestre (quem mandou o 0x4412) e descarta tudo."""
        master = self.conn.data['profile']['Id']
        dropped = False
        for player, gold, gp in rewards:
            verdict = anu_verdict(gold, gp, self.conn.server.config)
            if verdict == 'ok':
                continue
            print(f"[{self.conn.addr}] ANU {verdict}: {player.conn.data['profile']['Id']} gold={gold} gp={gp} (mestre {master})")
            await user_repository.insert_abnormal_update(master, player.conn.data['profile']['Id'], gp, gold)
            dropped |= verdict == 'drop'
        if dropped:
            await self.conn.close()
        return not dropped

    async def v584(self, room, body, rewards):
        """v584: o 0x4412 só traz contagens; calcula gold/GP aqui e mostra no 0x4415 (wcs2/result.py)."""
        from gunbound.game.protocol.wcs2 import result
        from gunbound.game.protocol.wcs2.bonus import BONUS
        shown = []
        for row in result.parse(body, room.options.stage is not None):
            player = room.player_by_slot(row['slot'])
            if player is None:
                continue
            paid = bots.reward(room, player, *result.reward(row, self.conn.server.config), self.conn.server.config)
            if paid is None:
                continue
            gold, gp = paid
            rewards.append((player, gold, gp))
            bonus = BONUS.get(room.game.bonus_event, (0, 0)) if player.slot in room.game.bonus_paid else (0, 0)
            shown.append((player.slot, gold, bonus[0], gp, bonus[1]))
        await room.broadcast(result.reward_packet(shown, result.mvp(shown, self.conn.server.config)))

    async def game_points(self, rewards, user_repository):
        """v584: pontos de Rena/desconto por partida (wcs2/result.py, config `game_points`)."""
        from gunbound.game.protocol.wcs2.result import DEFAULT_GAME_POINTS
        points = self.conn.server.config.get('game_points')
        for column, n in (DEFAULT_GAME_POINTS if points is None else points).items():
            for player, *_ in rewards:
                if n:
                    await user_repository.add_points(player.conn.data['profile']['Id'], column, int(n))

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
        match.later(room, None, 1.0, bots.announce_ready(room))  # depois que o cliente entra na sala


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
        if path := self.conn.server.config.get('tunnel_log'):
            log_tunnel(path, room, me, slots, data)
        packet = rp.tunnel(me.slot, data)
        for dest in filter(None, (room.player_by_slot(s) for s in slots)):
            if bots.is_bot(dest.conn):
                if room.game is not None:
                    await match.on_frame(room, dest, me, data)
                continue
            await dest.conn.on_send(packet.clone())  # on_send altera o buffer (tamanho/checksum)
