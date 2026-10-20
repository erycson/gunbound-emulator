from enum import IntEnum

# Nomes oficiais (SVC_*) extraídos via REA do servidor original (GunBoundServ3.exe): cada handler loga
# "Service Request: SVC_<NOME>(%08X)". A resposta padrão do original é o opcode do pedido + 1 (função 0x428040).
# Ver docs/Opcodes do servidor original.md.

class ClientPacket(IntEnum):
    CLI_KEEPALIVE = 0x0000

    # Sessão / login
    CLI_GET_SESSION_ID = 0x1000
    CLI_UNKNOWN_1004 = 0x1004           # ? não existe no despachante do original (investigar)
    CLI_LOGIN = 0x1010                  # SVC_LOGIN
    CLI_ADMIN_LOGIN = 0x1011            # SVC_LOGIN/ADMIN: mesmo handler do 0x1010 + marca a sessão como console admin
    CLI_REP_AUTHDWORD = 0x1016          # SVC_REP_AUTHDWORD: resposta do anti-hack (12 bytes cifrados) -> 0x1017
    CLI_UNKNOWN_1019 = 0x1019           # ? não existe no despachante do original (investigar)
    CLI_UNKNOWN_101C = 0x101C           # ? não existe no despachante do original (investigar)
    CLI_USER_ID = 0x1020                # SVC_USER_ID
    CLI_USER_NICK = 0x1021              # SVC_USER_NICK: lista de Ids (16 bytes) -> Id + Nickname em 0x1022
    CLI_CLIENT_DATA = 0x1090
    CLI_GRANDPRIX_LIST = 0x1100         # SVC_GRANDPRIX_LIST: ranking do Grand Prix -> 0x1101

    # Canal
    CLI_CHANNEL_JOIN = 0x2000           # SVC_CHANNEL_JOIN
    CLI_CHANNEL_CHAT = 0x2010           # SVC_CHANNEL_CHAT
    CLI_CHANNEL_MONITOR = 0x2020        # SVC_CHANNEL_MONITOR (GM >= 98): passa a ver o chat de todos os canais
    CLI_CHANNEL_MONITOR_STOP = 0x2022   # SVC_CHANNEL_MONITOR_STOP

    # Lista / entrada em salas
    CLI_ROOM_SORTED_LIST = 0x2100       # SVC_ROOM_SORTED_LIST
    CLI_ROOM_SPECIFIC_LIST = 0x2101     # SVC_ROOM_SPECIFIC_LIST
    CLI_ROOM_DETAIL = 0x2104            # SVC_ROOM_DETAIL
    CLI_ROOM_JOIN = 0x2110              # SVC_ROOM_JOIN
    CLI_ROOM_CREATE = 0x2120            # SVC_ROOM_CREATE
    CLI_ROOM_QUICK_START = 0x2130       # SVC_QUICKSTART
    CLI_ROOM_GRANDPRIX_BEGIN = 0x2140   # SVC_ROOM_GRANDPRIX_BEGIN
    CLI_ROOM_GRANDPRIX_CANCEL = 0x2141  # SVC_ROOM_GRANDPRIX_CANCEL

    # Sala de espera
    CLI_ROOM_LEAVE = 0x3001             # SVC_LEAVE_WAIT_GAMEROOM
    CLI_ROOM_CHANGE_STAGE = 0x3100      # SVC_ROOM_CHANGE_STAGE
    CLI_ROOM_CHANGE_OPTION = 0x3101     # SVC_ROOM_CHANGE_OPTION
    CLI_ROOM_CHANGE_USEITEM = 0x3102    # SVC_ROOM_CHANGE_USEITEM
    CLI_ROOM_CHANGE_MAXMEN = 0x3103     # SVC_ROOM_CHANGE_MAXMEN
    CLI_ROOM_CHANGE_TITLE = 0x3104      # SVC_ROOM_CHANGE_TITLE
    CLI_ROOM_KICK = 0x3150              # SVC_ROOM_KICK_USER
    CLI_ROOM_SELECT_TANK = 0x3200       # SVC_ROOM_SELECT_TANK
    CLI_ROOM_SELECT_TEAM = 0x3210       # SVC_ROOM_SELECT_TEAM
    CLI_ROOM_USER_READY = 0x3230        # SVC_ROOM_USER_READY
    CLI_ROOM_RETURN_RESULT = 0x3232     # SVC_ROOM_RETURN_RESULT
    CLI_START_GAME = 0x3430             # SVC_START_GAME

    # Partida
    CLI_PLAY_DROP_USER = 0x4000         # SVC_PLAY_DROP_USER (cifrado): derruba o jogador do slot -> 0x400F para ele
    CLI_GAME_DEAD = 0x4100              # SVC_PLAY_USER_DEAD
    CLI_GAME_RESURRECT = 0x4104         # SVC_PLAY_RESURRECT (cifrado)
    CLI_GAME_JEWEL_END = 0x4200         # SVC_PLAY_END_JEWEL (cifrado)
    CLI_GAME_RESULT = 0x4412            # SVC_PLAY_RESULT (cifrado)
    CLI_GAME_TUNNEL = 0x4500            # SVC_TUNNEL

    # Denúncia / comandos de GM
    CLI_POLICE_ACCUSE = 0x5000          # SVC_POLICE_ACCUSE (cifrado): denúncia -> 0x5001
    CLI_BCM = 0x5010                    # SVC_BCM (cifrado, GM): mensagem para todos em 0x5101
    CLI_COMMAND = 0x5100                # SVC_COMMAND: texto cru de comando GM ("/bcm ..."), resposta 0x5101

    # Console de administração (corpo em claro; autoridade >= 98 no STATUS/MOTD/BCM, >= 99 nos demais)
    CLI_CMD_STATUS = 0x5110             # SVC_CMD_STATUS -> 0x5111
    CLI_CMD_MOTD = 0x5112               # SVC_CMD_MOTD -> 0x5113
    CLI_CMD_BCM = 0x5114                # SVC_CMD_BCM -> 0x5115
    CLI_CMD_SETVERSION = 0x5116         # SVC_CMD_SETVERSION -> 0x5117
    CLI_CMD_GRADELIMIT = 0x5120         # SVC_CMD_GRADELIMIT -> 0x5121
    CLI_CMD_GUILDLIMIT = 0x5122         # SVC_CMD_GUILDLIMIT -> 0x5123
    CLI_CMD_FUNCTION_RESTRICT = 0x5124  # SVC_CMD_FUNCTION_RESTRICT -> 0x5125
    CLI_CMD_SET_ALLOWEDGUILD = 0x5126   # SVC_CMD_SET_ALLOWEDGUILD -> 0x5127
    CLI_CMD_SET_EVENTACTPROB = 0x5128   # SVC_CMD_SET_EVENTACTPROB -> 0x5129
    CLI_CMD_SET_PASSABLE_AUTH = 0x512A  # SVC_CMD_SET_PASSABLE_AUTH -> 0x512B
    CLI_CMD_SET_FACTOR = 0x512C         # SVC_CMD_SET_FACTOR -> 0x512D

    # Loja / baú
    CLI_ITEM = 0x6000                   # SVC_ITEM
    CLI_ITEM_GIFT_MSG = 0x6004          # SVC_ITEM_GIFT_MSG
    CLI_ITEM_GIFT_CONFIRM = 0x6008      # SVC_ITEM_GIFT_CONFIRM
    CLI_ITEM_LOCATION = 0x600A          # SVC_ITEM_LOCATION: u16 qtd + qtd x (chest u32, posição u32) -> 0x600B
    CLI_ITEM_WEAR = 0x600E              # SVC_ITEM_WEAR -> 0x600F
    CLI_ITEM_BUY = 0x6020               # SVC_ITEM_BUY
    CLI_ITEM_CONSUME = 0x6024           # SVC_ITEM_CONSUME
    CLI_ITEM_GIFT = 0x6028              # SVC_ITEM_GIFT (cifrado): dá um item do próprio baú -> 0x6029
    CLI_ITEM_GIFT_BUY = 0x6030          # SVC_ITEM_GIFT_BUY
    CLI_CASH = 0x6100                   # SVC_CASH
    CLI_GOLD = 0x6104                   # SVC_GOLD


class ServerPacket(IntEnum):
    """
    Pacotes enviados pelo servidor ao cliente.
    """

    # Sessão / login
    SRV_SESSION_ID = 0x1001
    SRV_LOGIN = 0x1012
    SRV_LOGIN_RECORD = 0x1013
    SRV_LOGIN_TOKEN = 0x1015
    SRV_CHAT_MUTE = 0x1040             # u32 segundos de mordaça no chat (0 tira); só pelo /mute de GM
    SRV_UDP_ADDRESS = 0x101F           # IP/porta UDP observados (NAT) quando diferem do 0x1010 (original 0x42b670)
    SRV_REP_AUTHDWORD = 0x1017
    SRV_GRANDPRIX_LIST = 0x1101         # u16 rtc + grupos + pessoas + meu grupo + eu (docs/Grand Prix.md)
    SRV_USER_NICK = 0x1022              # resposta do 0x1020/0x1021 no original
    SRV_CLIENT_DATA = 0x1091
    SRV_UNKNOWN_1031 = 0x1031
    SRV_UNKNOWN_1032 = 0x1032           # cifrado (F4)
    SRV_UNKNOWN_1033 = 0x1033

    # Canal
    SRV_CHANNEL_JOIN = 0x2001           # Resposta ao pedido de entrada no canal
    SRV_CHANNEL_JOIN_UPDATE = 0x200E    # Notifica os outros usuários que um usuário entrou no canal
    SRV_CHANNEL_JOIN_REMOVE = 0x200F    # Notifica os outros usuários que um usuário saiu do canal
    SRV_CHANNEL_CHAT = 0x201F           # Envia a mensagem de chat do canal
    SRV_CHANNEL_MONITOR = 0x2021
    SRV_CHANNEL_MONITOR_STOP = 0x2023
    SRV_UNKNOWN_2005 = 0x2005
    SRV_UNKNOWN_2007 = 0x2007
    SRV_UNKNOWN_2008 = 0x2008
    SRV_UNKNOWN_2012 = 0x2012
    SRV_UNKNOWN_2031 = 0x2031

    # Salas
    SRV_ROOM_SORTED_LIST = 0x2103
    SRV_ROOM_DETAIL = 0x2105
    SRV_ROOM_JOIN = 0x2111              # estado completo da sala (ou erro no RTC)
    # Lista de salas ao vivo para quem está no lobby (0x414890); u16 id da sala + campo
    SRV_LOBBY_ROOM_CREATED = 0x21F0     # entrada igual à do 0x2103 (0x413e60)
    SRV_LOBBY_ROOM_DESTROYED = 0x21F1   # só o id (0x4145fb)
    SRV_LOBBY_ROOM_TITLE = 0x21F2       # título cru, sem tamanho nem 00 (0x416ac3)
    SRV_LOBBY_ROOM_MAP = 0x21F3         # mapa u8 (0x416777)
    SRV_LOBBY_ROOM_SETTINGS = 0x21F4    # settings u32 (0x416864)
    SRV_LOBBY_ROOM_PLAYERS = 0x21F5     # nº de jogadores u8 (0x414266 entrar, 0x41463a sair)
    SRV_LOBBY_ROOM_MAXMEN = 0x21F6      # máx. de jogadores u8 (0x416994)
    SRV_LOBBY_ROOM_STATE = 0x21F7       # 1 em jogo (0x41669d), 0 aguardando (0x4199ef)
    SRV_ROOM_CREATE = 0x2121
    SRV_ROOM_QUICK_FAIL = 0x2131        # u16 RTC 8: quick start falhou (original 0x4293f3; TH não trata)
    SRV_ROOM_QUICK_CREATE = 0x2132      # quick start sem sala: criou QuickStartRoom (original 0x413e68)
    SRV_ROOM_QUICK_START = 0x2133
    SRV_ROOM_UNKNOWN_3007 = 0x3007
    SRV_ROOM_LEAVE = 0x3001             # [INCERTO] confirmação de saída (o cliente compara 0x3001)
    SRV_ROOM_PLAYER_JOIN = 0x3010       # para os outros da sala
    SRV_ROOM_PLAYER_LEAVE = 0x3020      # slot u16
    SRV_ROOM_UPDATE = 0x3105
    SRV_ROOM_KICK = 0x315F
    SRV_ROOM_KICK_TH = 0x3151           # TH: RTC 0 + u8 slot (cliente TH 0x4c2c23)
    SRV_ROOM_KICKED = 0x3FFF            # para o expulso
    SRV_ROOM_SELECT_TANK = 0x3201
    SRV_ROOM_SELECT_TEAM = 0x3211
    SRV_ROOM_USER_READY = 0x3231
    SRV_ROOM_RETURN_RESULT = 0x3233
    SRV_ROOM_HOST_CHANGE = 0x3400
    SRV_START_GAME_ACK = 0x3431         # só em erro no original (RTC 0x2005/0x3001/0x3002/0x3003/8)
    SRV_START_GAME = 0x3432             # cifrado

    # Partida
    SRV_GAME_EVENT_4001 = 0x4001
    SRV_GAME_EVENT_4002 = 0x4002
    SRV_GAME_EVENT_4003 = 0x4003
    SRV_GAME_EVENT_4004 = 0x4004
    SRV_PLAY_DROP_USER = 0x400F         # para o jogador derrubado pelo SVC_PLAY_DROP_USER (sem corpo)
    SRV_GAME_DEAD_ACK = 0x4101
    SRV_GAME_DEAD = 0x4102              # cifrado
    SRV_GAME_UNKNOWN_4106 = 0x4106      # cifrado
    SRV_GAME_UNKNOWN_4201 = 0x4201
    SRV_GAME_UNKNOWN_4202 = 0x4202
    SRV_GAME_UNKNOWN_4203 = 0x4203
    SRV_GAME_WINNER = 0x4410            # cifrado
    SRV_GAME_RESULT = 0x4413
    SRV_GAME_TUNNEL = 0x4501

    # Denúncia / comandos
    SRV_POLICE_ACCUSE = 0x5001
    SRV_BCM = 0x5011
    SRV_COMMAND = 0x5101                # texto cru (resposta de comando GM / BCM)
    SRV_CMD_STATUS = 0x5111
    SRV_CMD_MOTD = 0x5113
    SRV_CMD_BCM = 0x5115
    SRV_CMD_SETVERSION = 0x5117
    SRV_CMD_GRADELIMIT = 0x5121
    SRV_CMD_GUILDLIMIT = 0x5123
    SRV_CMD_FUNCTION_RESTRICT = 0x5125
    SRV_CMD_SET_ALLOWEDGUILD = 0x5127
    SRV_CMD_SET_EVENTACTPROB = 0x5129
    SRV_CMD_SET_PASSABLE_AUTH = 0x512B
    SRV_CMD_SET_FACTOR = 0x512D

    # Loja / baú
    SRV_ITEM = 0x6001
    SRV_ITEM_GIFT_MSG = 0x6004
    SRV_ITEM_GIFT_CONFIRM = 0x6009
    SRV_ITEM_LOCATION = 0x600B
    SRV_SHOP_UNKNOWN_6002 = 0x6002
    SRV_SHOP_UNKNOWN_6003 = 0x6003
    SRV_SHOP_UNKNOWN_6007 = 0x6007
    SRV_ITEM_WEAR = 0x600F              # sem corpo; RTC 0 ok, 4 erro (FUN_0042e140)
    SRV_SHOP_UNKNOWN_6032 = 0x6032
    SRV_ITEM_BUY = 0x6021
    SRV_ITEM_CONSUME = 0x6025
    SRV_ITEM_GIFT = 0x6029
    SRV_ITEM_GIFT_BUY = 0x6031
    SRV_CASH = 0x6101
    SRV_GOLD = 0x6105

    SRV_ERROR_UNKNOWN_1090 = 0x1090
    SRV_ERROR_UNKNOWN_1FFF = 0x1FFF
    SRV_ERROR_UNKNOWN_200F = 0x200F
    SRV_ERROR_UNKNOWN_6004 = 0x6004


class ServerCode(IntEnum):
    # Genéricos (podem aparecer em múltiplos replies)
    SRV_OK = 0x00
    SRV_UPDATED = 0x01
    SRV_WRONG_VERSION = 0x60
    SRV_WRONG_GENDER = 0x2101
    SRV_DENIED = 0x1D                   # recusa genérica do original (monitor, motd, room detail)
    SRV_INVALID_ARG = 0x1B              # argumento inválido (SET_ALLOWEDGUILD)

    # Sala / loja (F3, [INCERTO] para WC; ver Protocolo-Salas.md 5.3)
    SRV_ROOM_NOT_FOUND = 0x0011         # sala inexistente ou senha errada
    SRV_ROOM_FULL = 0x2001              # sala cheia
    SRV_ROOM_CREATE_FAIL = 0x2002       # 0x2121: criação recusada (modo inválido, limite de salas; original 0x4294bc)
    # Códigos internos (o cliente ainda não confirma um valor próprio): reaproveitam 0x0011
    SRV_ROOM_IN_GAME = 0x0011
    SRV_WRONG_PASSWORD = 0x0011
    SRV_CHANNEL_FULL = 0x1001
