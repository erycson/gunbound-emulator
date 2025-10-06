from enum import IntEnum

class ClientPacket(IntEnum):
    # Solicita a lista de servidores de jogo, ordenada por algum critério.
    CLI_KEEPALIVE = 0x0000

    # Solicita a lista de servidores de jogo, ordenada por algum critério.
    CLI_GET_SESSION_ID = 0x1000

    CLI_LOGIN = 0x1010
    CLI_USER_ID = 0x1020
    CLI_CHANNEL_JOIN = 0x2000
    CLI_ROOM_SORTED_LIST = 0x2100
    CLI_ROOM_DETAIL = 0x2104
    CLI_ROOM_JOIN = 0x2110
    CLI_CHANNEL_CHAT = 0x2010           # Recebe uma mensagem de chat do canal
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

    CLI_CLIENT_DATA = 0x1090
    CLI_ITEM = 0x6000
    CLI_ITEM_GIFT_MSG = 0x6004
    CLI_CASH = 0x6100
    CLI_GOLD = 0x6104

"""
Enums para pacotes enviados pelo broker ao cliente.
"""
class ServerPacket(IntEnum):
    # Envia o ID da sessão para o cliente.
    SRV_SESSION_ID = 0x1001

    # Autentica o cliente no gameserver
    SRV_LOGIN = 0x1012
    SRV_LOGIN_RECORD = 0x1013
    SRV_LOGIN_TOKEN = 0x1015

    SRV_CHANNEL_JOIN = 0x2001           # Resposta ao pedido de entrada no canal
    SRV_CHANNEL_JOIN_UPDATE = 0x200E    # Notifica os outros usuários que um usuário entrou no canal
    SRV_CHANNEL_JOIN_REMOVE = 0x200F    # Notifica os outros usuários que um usuário saiu do canal

    SRV_CHANNEL_CHAT = 0x201F           # Envia a mensagem de chat do canal
    
    SRV_ROOM_SORTED_LIST = 0x2103
    SRV_ROOM_CREATE = 0x2121
    SRV_ROOM_SELECT_TANK = 0x3201

    SRV_ITEM = 0x6001
    SRV_ITEM_GIFT_MSG = 0x6004
    SRV_CASH = 0x6101
    SRV_GOLD = 0x6105
    SRV_CLIENT_DATA = 0x1091

    SRV_ERROR_UNKNOWN_1090 = 0x1090
    SRV_ERROR_UNKNOWN_1FFF = 0x1FFF
    SRV_ERROR_UNKNOWN_200F = 0x200F
    SRV_ERROR_UNKNOWN_5001 = 0x5001
    SRV_ERROR_UNKNOWN_5011 = 0x5011
    SRV_ERROR_UNKNOWN_6004 = 0x6004

class ServerCode(IntEnum):
    # Genéricos (podem aparecer em múltiplos replies)
    SRV_OK = 0x00
    SRV_UPDATED = 0x01
    SRV_WRONG_VERSION = 0x60

class Feature(IntEnum):
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

class Tank(IntEnum):
    ARMOR = 0x0003
    MAGE = 0x0103
    NAK = 0x0203
    TRICO = 0x0303
    BIGFOOT = 0x0403
    BOOMER = 0x0503
    RAONLAUNCHER = 0x0603
    LIGHTENING = 0x0703
    JD = 0x0803
    A_SATE = 0x0903
    ICE = 0x0A03
    TURTLE = 0x0B03
    GRUB = 0x0C03
    ADUKA = 0x0D03
    KALSIDDON = 0x0E03
    J_FROG = 0x0F03
    RANDOM = 0xFF03

class RoomStatus(IntEnum):
    DESTROYING = -1
    WAITING = 0
    IN_GAME = 1
    FINISHED = 2

class RoomMode(IntEnum):
    SOLO = 0x6200
    SCORE = 0x6244
    TAG = 0x6208
    JEWEL = 0x620C

class RoomSize(IntEnum):
    X1 = 0x0200
    X2 = 0x0400
    X3 = 0x0600
    X4 = 0x0800

class RoomMap(IntEnum):
    RAMDOM = 0x00B2
    MIRAMO_TOWN = 0x01B2
    NIRVANA = 0x02B2
    METROPOLIS = 0x03B2
    SEA_OF_HERO = 0x04B2
    ADIUM_ROOT = 0x05B2
    DRAGON = 0x06B2
    COZY_TOWER = 0x07B2
    DUMMY_SLOPE = 0x08B2
    STGAR_DUST = 0x09B2
    META_MINE = 0x0AB2

class RoomSortList(IntEnum):
    ALL = 0x01
    WAITING = 0x02

    SOLO = 0x03
    SCORE = 0x04
    TAG = 0x05
    JEWEL = 0x06