from enum import IntEnum, StrEnum

class ExpireType(StrEnum):
    Week = "W"
    Month = "M"
    Ten = "T"
    Year = "Y"
    Infinite = "I"
    
    @classmethod
    def try_parse(cls, value: str):
        try:
            return cls(value)
        except ValueError:
            return None
        
    @classmethod
    def try_parse_int(cls, value: int):
        if chr(value) in 'WTMYI':  # o original monta o nome da coluna com o byte cru (PriceBy...For%c)
            return cls(chr(value))
        match value:
            case 1:
                return cls.Week
            case 3:
                return cls.Month
            case 7:
                return cls.Infinite
            case _:
                return None
        
class AcquisitionType(StrEnum):
    Cash = "C"
    Gold = "G"
    Gift = "T"
    
    @classmethod
    def try_parse(cls, value: str):
        try:
            return cls(value)
        except ValueError:
            return None
        
    @classmethod
    def try_parse_int(cls, value: int):
        match value:
            case 0:
                return cls.Gold
            case _:  # original: byte != 0 usa PriceByCashFor
                return cls.Cash

class ReceiptBuyType(StrEnum):
    Self = "S"
    Gift = "G"
    
    @classmethod
    def try_parse(cls, value: str):
        try:
            return cls(value)
        except ValueError:
            return None

class MessageType(StrEnum):
    Self = "S"
    Gift = "G"
    
    @classmethod
    def try_parse(cls, value):
        try:
            return cls(value)
        except ValueError:
            return None

class GiftMsgType(StrEnum):
    Gift = "G"
    Accepted = "A"
    Denied = "D"
    
    @classmethod
    def try_parse(cls, value):
        try:
            return cls(value)
        except ValueError:
            return None
        
class ReceiptGiftResult(StrEnum):
    Requested = "R"
    Accepted = "A"
    Denied = "D"
    
    @classmethod
    def try_parse(cls, value):
        try:
            return cls(value)
        except ValueError:
            return None

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
    """Modo de jogo: u16 nos bytes 2-3 do campo settings (0x2120/0x3101). Valores de F2/F3."""
    SOLO = 0x00
    SCORE = 0x44
    TAG = 0x08
    JEWEL = 0x0C

    @classmethod
    def parse(cls, value: int) -> 'RoomMode | None':
        return cls._value2member_map_.get(value)

    @classmethod
    def of_settings(cls, settings: int) -> 'RoomMode':
        """Modo pelos bits 18-19 do settings (TH 0x4c4e89: Solo 0, Score 0x40000 (+bit 22), Tag 0x80000, Jewel 0xC0000)."""
        return MODE_BITS[settings & 0xC0000]


MODE_BITS = {0: RoomMode.SOLO, 0x40000: RoomMode.SCORE, 0x80000: RoomMode.TAG, 0xC0000: RoomMode.JEWEL}

RANDOM_MAP = 0      # mapa 0 = aleatório
MAP_COUNT = 11      # mapas 1..10 (docs/Play/Maps.md); usado no sorteio
ROOM_SIZES = (2, 4, 6, 8)
STAGE_SIZES = (1, 2)  # canal Stage do v584: capacidade = MaxMan da missão
TANK_RANDOM = 0xFF
TANK_COUNT = 16     # índices 0..15 (docs/Play/Tanks e Itens.md)
HIDDEN_TANKS = (0x11, 0x12)  # ocultos do original: só no aleatório (Tank.Hidden.Ratio) ou escolhidos por Authority >= 98


class RoomSortList(IntEnum):
    ALL = 0x01
    WAITING = 0x02

    SOLO = 0x03
    SCORE = 0x04
    TAG = 0x05
    JEWEL = 0x06

class RoomOptions:
    MIN_PLAYERS = 2
    MAX_PLAYERS = 8
    MAX_TITLE = 23              # criação (0x2120: corpo de 10 a 0x4A bytes)
    MAX_RENAME = 64             # 0x3104 aceita de 1 a 0x40 bytes no servidor original
    ALL_ITEMS = b'\xFF' * 8     # 0x3102: 8 bytes de máscara de itens, repetidos em 0x2111/0x3400
    DEFAULT_SETTINGS = 0x62B2   # bytes 0-1 do settings (fixos B2 62)
    # settings u32, guardado cru como o original (+0x54 da sala): bits 0-3 posições (0 EvsW, 1 Mix, 2+ Rand), 16-17 lado
    # do mapa, 18-19 modo, 20-23 vidas do Score (o servidor grava no início), 24-31 evento (/evento do cliente)

    def __init__(self, name: str, mode: RoomMode, size: int, password: str | None, map: int = RANDOM_MAP,
                 settings: int = DEFAULT_SETTINGS, item_bytes: bytes = b'\xFF' * 8, stage: tuple | None = None):
        self.name = name[:self.MAX_TITLE]
        self.settings = settings & 0xFFFFFFFF
        self.mode = mode
        self.stage = stage  # canal Stage: (StageNum-1, GameMode) do 0x2120; None fora dele
        self.size = size if size in ROOM_SIZES or (stage is not None and size in STAGE_SIZES) else self.MAX_PLAYERS
        self.password = password or None
        self.map = map
        self.item_bytes = bytes(item_bytes)  # 0x3102: máscara de itens permitidos (8 bytes crus)

    @property
    def mode(self) -> RoomMode:
        return RoomMode.of_settings(self.settings)

    @mode.setter
    def mode(self, mode: RoomMode) -> None:
        """Troca só os bits 18-19 (como o /qsopt do original); Score sem vidas ganha o bit 22 que o cliente põe."""
        self.settings = (self.settings & ~0xC0000) | ((int(mode) << 16) & 0xC0000)
        if mode == RoomMode.SCORE and not self.settings & 0xF00000:
            self.settings |= 0x400000

    @property
    def side(self) -> int:
        return (self.settings >> 16) & 3

    @property
    def layout(self) -> int:
        """0 EvsW, 1 Mix, 2 Rand (original: settings & 0xF, acima de 2 vale 2)."""
        return min(self.settings & 0xF, 2)

    def max_players(self) -> int:
        return self.size

    def sizes(self) -> tuple:
        """Capacidades aceitas na troca (0x3103/0x6220): 1/2 nas salas do canal Stage."""
        return STAGE_SIZES if self.stage is not None else ROOM_SIZES

    def use_item(self) -> bool:
        return any(self.item_bytes)

    def check_password(self, password: str | None) -> bool:
        return self.password is None or self.password == (password or None)

    def is_protected(self) -> bool:
        return self.password is not None
