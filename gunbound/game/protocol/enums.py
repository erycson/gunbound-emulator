from enum import IntEnum

class ClientPacket(IntEnum):
    # Solicita a lista de servidores de jogo, ordenada por algum critério.
    CLI_KEEPALIVE = 0x0000

    # Solicita a lista de servidores de jogo, ordenada por algum critério.
    CLI_GET_SESSION_ID = 0x1000

    CLI_USER_ID = 0x1020
    CLI_CHANNEL_JOIN = 0x2000
    CLI_ROOM_SORTED_LIST = 0x2100
    CLI_ROOM_DETAIL = 0x2104
    CLI_ROOM_JOIN = 0x2110
    CLI_CHANNEL_CHAT = 0x2010
    CLI_ROOM_CREATE = 0x2120
    CLI_ROOM_CHANGE_STAGE = 0x3100
    CLI_ROOM_CHANGE_OPTION = 0x3101
    CLI_ROOM_CHANGE_TITLE = 0x3102
    CLI_ROOM_CHANGE_MAXMEN = 0x3103
    CLI_ROOM_CHANGE_USEITEM = 0x3104
    CLI_ROOM_SELECT_TANK = 0x3200
    CLI_ROOM_SELECT_TEAM = 0x3210
    CLI_ROOM_USER_READY = 0x3230
    CLI_ROOM_RETURN_RESULT = 0x3232
    CLI_START_GAME = 0x3430

"""
Enums para pacotes enviados pelo broker ao cliente.
"""
class ServerPacket(IntEnum):
    # Envia o ID da sessão para o cliente.
    SRV_SESSION_ID = 0x1001

    # Autentica o cliente no gameserver
    SRV_LOGIN = 0x1012

class ServerCode(IntEnum):
    # Genéricos (podem aparecer em múltiplos replies)
    SRV_OK = 0x00


class Features(IntEnum):
    AVATAR_ENABLED = 1 << 4
    EFFECT_FORCE = 1 << 13
    EFFECT_TORNADO = 1 << 14
    EFFECT_LIGHTNING = 1 << 15
    EFFECT_WIND = 1 << 16
    EFFECT_THOR = 1 << 17
    EFFECT_MOON = 1 << 18
    EFFECT_ECLIPSE = 1 << 19
    EVENT1_ENABLE = 1 << 20
    EVENT2_ENABLE = 1 << 21
    EVENT3_ENABLE = 1 << 22
    EVENT4_ENABLE = 1 << 23