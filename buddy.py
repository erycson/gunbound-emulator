"""BuddyServ (amigos): TCP + UDP na mesma porta (buddy_server.port, 8352). Protocolo em gunbound/buddy/server.py."""
from gunbound.util import filelog
filelog.start('buddy')
import asyncio
import yaml
from gunbound.base.database import Database
from gunbound.buddy.server import BuddyServer, BuddyUdp
from gunbound.repository.buddy_repository import BuddyRepository

with open("config.yml", "r", encoding="utf-8") as f:
    CONFIG = yaml.load(f, Loader=yaml.FullLoader)


async def main():
    cfg = CONFIG['buddy_server']
    database = Database(CONFIG['database']['uri'])
    await database.connect()
    buddy = BuddyServer(BuddyRepository(database), notice=cfg.get('notice'))
    server = await asyncio.start_server(buddy.handle, cfg['host'], cfg['port'])
    transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: BuddyUdp(buddy), local_addr=(cfg['host'], cfg['port']))
    print(f"BuddyServ iniciado em {cfg['host']}:{cfg['port']} (TCP e UDP)")
    try:
        async with server:
            await server.serve_forever()
    finally:
        transport.close()
        await database.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("BuddyServ parado")
