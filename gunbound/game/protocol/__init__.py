import os
import importlib
from .enums import ClientPacket, ServerPacket, ServerCode, Feature, Tank, RoomMode, RoomMap, RoomSize, RoomStatus, RoomSortList
current_dir = os.path.dirname(__file__)

for filename in os.listdir(current_dir):
    if filename.endswith('.py') and filename not in ('__init__.py', 'base.py'):
        module_name = f"{__name__}.{filename[:-3]}"
        importlib.import_module(module_name)
