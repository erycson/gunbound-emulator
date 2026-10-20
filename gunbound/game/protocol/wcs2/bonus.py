"""
Bônus de partida do v584 ("+%dGold, +%dGP"). Layouts lidos do GunBound.gme (VA).

0x3432 (S->C): o último byte é o tipo de bônus da partida (G+0x68474); 0xFF = nenhum (phase.WCS2.game_start_tail).
0x4300 (C->S, 0x4fb6c0 e inline no tratador de tiro 0x50496b): u8 tipo. Só o próprio jogador manda, uma vez por partida,
    e só quando o tipo é o da partida. Sem resposta (não existe 0x4301) e sem repasse: cada cliente só mostra o texto.
O cliente não credita nada: o 0x4412 leva só a flag. Aqui o crédito é pelo 0x4300 (o 0x4412 não paga o bônus).

Sorteio: chave de config `bonus_event` = % de chance por partida de sortear um tipo 0..9 (0 ou ausente = desligado).
"""
from __future__ import annotations
import random
from dependency_injector.wiring import Provide, inject
from gunbound.game.protocol.base import GameRecv, handler

CLI_PLAY_BONUS = 0x4300
NO_BONUS = 0xFF
# tipo -> (gold, GP), tabelas 0x4fb83c/0x4fb848 (gold) e 0x4fb854/0x4fb860 (GP) do cliente
BONUS = {0: (100, 1), 1: (200, 0), 2: (500, 0), 3: (100, 0), 4: (200, 1),
         5: (200, 1), 6: (500, 0), 7: (100, 2), 8: (100, 2), 9: (100, 2)}


def roll_bonus(config, rng=random) -> int:
    chance = int(config.get('bonus_event') or 0)
    return rng.randrange(len(BONUS)) if chance > 0 and rng.randrange(100) < chance else NO_BONUS


@handler(CLI_PLAY_BONUS, in_game=True, register=False)
class PlayBonusRecv(GameRecv):
    @inject
    async def handle(self, inventory_repository=Provide['inventory_repository'], user_repository=Provide['user_repository']):
        from gunbound.game.protocol.game_play import GameResultRecv
        game, player = self.room.game, self.room.player(self.conn)
        kind = self.buf.require(1).read_uint8()
        if player is None or kind != game.bonus_event or player.slot in game.bonus_paid:
            print(f"[{self.conn.addr}] 0x4300 recusado: tipo {kind}, partida {game.bonus_event}")
            return
        game.bonus_paid.add(player.slot)
        gold, gp = BONUS[kind]
        await GameResultRecv.credit(self.conn, gold, gp, inventory_repository, user_repository)


@handler(0x4520, in_game=True, register=False)
class StageMissionEndRecv(GameRecv):
    """0x4520 (só o dono, canal Stage tipo 2): u8 0 = meta atingida, 1 = tempo esgotado. Sem resposta (não há 0x4521).
    shortcut: não há canal Stage no emulador; só registra. Com Stage, encerrar como o 0x4200 (0x4410)."""

    async def handle(self):
        print(f"[{self.conn.addr}] 0x4520 fim de missão Stage: {self.buf.read_bytes().hex()}")
