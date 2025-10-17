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
    CLI_ITEM_GIFT_CONFIRM = 0x6008
    CLI_ITEM_LOCATION = 0x600A # ???
    CLI_ITEM_BUY = 0x6020
    CLI_ITEM_CONSUME = 0x6024
    CLI_ITEM_GIFT_BUY = 0x6030
    CLI_CASH = 0x6100
    CLI_GOLD = 0x6104


class ServerPacket(IntEnum):
    """
    Enums para pacotes enviados pelo broker ao cliente.
    """

    # Envia o ID da sessão para o cliente.
    SRV_SESSION_ID = 0x1001

    # Autentica o cliente no gameserver
    SRV_LOGIN = 0x1012
    SRV_LOGIN_RECORD = 0x1013
    SRV_LOGIN_TOKEN = 0x1015
    SRV_USER_ID = 0x1020
    SRV_CLIENT_DATA = 0x1091

    SRV_CHANNEL_JOIN = 0x2001           # Resposta ao pedido de entrada no canal
    SRV_CHANNEL_JOIN_UPDATE = 0x200E    # Notifica os outros usuários que um usuário entrou no canal
    SRV_CHANNEL_JOIN_REMOVE = 0x200F    # Notifica os outros usuários que um usuário saiu do canal

    SRV_CHANNEL_CHAT = 0x201F           # Envia a mensagem de chat do canal
    
    SRV_ROOM_SORTED_LIST = 0x2103
    SRV_ROOM_CREATE = 0x2121
    SRV_ROOM_SELECT_TANK = 0x3201

    SRV_ITEM = 0x6001
    SRV_ITEM_GIFT_MSG = 0x6004
    SRV_ITEM_GIFT_CONFIRM = 0x6009
    SRV_ITEM_LOCATION = 0x600A  # ???
    SRV_ITEM_BUY = 0x6021
    SRV_CASH = 0x6101
    SRV_GOLD = 0x6105
    SRV_ITEM_GIFT_BUY = 0x6031
    SRV_ITEM_CONSUME = 0x6025

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
    SRV_WRONG_GENDER = 0x2101
