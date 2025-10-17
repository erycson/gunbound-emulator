
def dump_handler(port):
    async def loop(reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"[{port}] Dump server: conexão de {addr}")

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                dump(data)
        except Exception as e:
            print(f"Erro no dump server: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    return loop