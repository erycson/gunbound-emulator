from enum import IntEnum, StrEnum

class ExpireType(StrEnum):
    Week = "W"
    Month = "M"
    Infinite = "I"
    
    @classmethod
    def try_parse(cls, value: str):
        try:
            return cls(value)
        except ValueError:
            return None
        
    @classmethod
    def try_parse_int(cls, value: int):
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
                return cls.Cash
            case 1:
                return cls.Gold
            case _:
                return None

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

class RoomOptions:
    def __init__(self, name: str, map: RoomMap, mode: RoomMode, size: RoomSize, password: str | None):
        self.name = name
        self.map = map
        self.mode = mode
        self.size = size
        self.password = password
        self.max_players: RoomSize = size

    def max_players(self) -> int:
        match self.size:
            case RoomSize.X1: return 2
            case RoomSize.X2: return 4
            case RoomSize.X3: return 6
            case RoomSize.X4: return 8

    def is_protected(self) -> bool:
        return self.password is not None
