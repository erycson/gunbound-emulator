"""
Resultado da partida no v584. Layouts lidos do GunBound.gme (VA).

0x4412 (C->S, cifrado, só o dono da sala, montador 0x4fff30): u16 jogadores + registros de 23 bytes até acabar o corpo
    (o laço pula quem saiu, então pode haver menos registros que o u16; no canal Stage +7 bytes, RECORD_STAGE):
    u8 slot, 9 x u8 contagens de eventos de tiro já limitadas pelo cliente (ordem em EVENTS), u8 joia/tempo,
    u16 evento, u32 joias, u32 (sempre 0), u8 vitória (1 venceu, 0 perdeu, 2 sem vencedor), u8 ganhou o bônus 0x4300.
    Não traz gold nem GP: o servidor calcula, aplica GoldFactor/ScoreFactor (o v584 não aplica) e devolve no 0x4415.
0x4415 (S->C, claro, PlayMode 0x5018f0, enche a tela de resultado): i16 n + n x (u8 slot, u32 gold, u32 gold bônus,
    i16 GP, i16 GP bônus, u8, u8, u8) + u8. shortcut: os 3 u8 e o u8 final vão em 0 (uso não fechado).

Valor de cada evento: regra do servidor (o cliente não tem a tabela). Chave de config `result_rewards`, com os
padrões em DEFAULT_REWARDS: {evento: [gold, gp]}.
MVP (u8 final, < 9 destaca o slot na tela, 0x560670): sem fonte da regra do original; aqui é quem fez mais gold base
(desempate: mais GP), só se alguém fez gold > 0. `mvp: false` no config volta a 0xFF (nenhum).
Pontos por partida (Rena/desconto, sem fonte no jogo): config `game_points`, padrão DEFAULT_GAME_POINTS, para cada
jogador com registro no 0x4412.
"""
from __future__ import annotations
from gunbound.game.protocol.base import Packet

SRV_GAME_REWARD = 0x4415
NO_MVP = 0xFF
RECORD = 23
RECORD_STAGE = 30  # canal Stage (0x500c6c): + u16 StageNum-1, u8 GameMode, u32 pontuação da missão (0 se falhou)
# ordem dos 9 bytes depois do slot (estatísticas 0x14, 2, 5, 0x13, 0x12, 0x11, 0xD, 6, 4 do cliente)
EVENTS = ('event_628', 'bunge', 'kill', 'damage_3000', 'damage_2000', 'damage_1000',
          'team_damage', 'team_kill', 'suicide')
# shortcut: valores próprios (sem fonte do original); ajuste por config['result_rewards']
DEFAULT_REWARDS = {
    'event_628': [50, 1], 'bunge': [100, 1], 'kill': [50, 1],
    'damage_3000': [300, 1], 'damage_2000': [200, 1], 'damage_1000': [100, 0],
    'team_damage': [-50, -1], 'team_kill': [-100, -2], 'suicide': [-50, -1],
    'win': [100, 2], 'lose': [30, 0],
}
DEFAULT_GAME_POINTS = {'RenaPoints': 10, 'DiscountPoints': 5}


def mvp(rows: list[tuple], config) -> int:
    """rows como no reward_packet; slot do MVP ou NO_MVP."""
    if config.get('mvp') is False or not rows:
        return NO_MVP
    slot, gold, _, gp, _ = max(rows, key=lambda r: (r[1], r[3]))
    return slot if gold > 0 else NO_MVP


def parse(body, stage: bool = False) -> list[dict]:
    """Registros do 0x4412 v584 (corpo já decifrado)."""
    body.read_uint16()
    rows = []
    while body.remaining() >= (RECORD_STAGE if stage else RECORD):
        slot = body.read_uint8()
        counts = dict(zip(EVENTS, (body.read_uint8() for _ in EVENTS)))
        body.read_uint8()
        body.read_uint16()
        jewels = body.read_uint32()
        body.read_uint32()
        win, bonus = body.read_uint8(), body.read_uint8()
        rows.append({'slot': slot, 'counts': counts, 'jewels': jewels, 'win': win, 'bonus': bonus})
        if stage:
            body.read_uint16()
            body.read_uint8()
            rows[-1]['stage_score'] = body.read_uint32()
    return rows


def reward(row: dict, config) -> tuple[int, int]:
    """Gold e GP base (sem o bônus do 0x4300, que já foi pago), com os fatores do servidor."""
    table = {**DEFAULT_REWARDS, **(config.get('result_rewards') or {})}
    gold = gp = 0
    for name, n in row['counts'].items():
        gold, gp = gold + n * table[name][0], gp + n * table[name][1]
    if row['win'] in (0, 1):
        g, s = table['win' if row['win'] == 1 else 'lose']
        gold, gp = gold + g, gp + s
    return gold * int(config['gold_factor']) // 100, gp * int(config['score_factor']) // 100


def reward_packet(rows: list[tuple], mvp_slot: int = NO_MVP) -> Packet:
    """rows: (slot, gold, gold_bonus, gp, gp_bonus)."""
    pkt = Packet.new(SRV_GAME_REWARD).u16(len(rows))
    for slot, gold, gold_bonus, gp, gp_bonus in rows:
        pkt.u8(slot).u32(gold).u32(gold_bonus).u16(gp & 0xFFFF).u16(gp_bonus & 0xFFFF).u8(0).u8(0).u8(0)
    return pkt.u8(mvp_slot)
