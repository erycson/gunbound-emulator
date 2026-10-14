from datetime import datetime

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

def to_datetime(value) -> datetime | None:
    """Normaliza datas vindas do banco: SQLite devolve texto e o MySQL antigo usa '0000-00-00 00:00:00' como vazio."""
    if value is None or isinstance(value, datetime):
        return value
    value = str(value)
    return None if value.startswith('0000') else datetime.fromisoformat(value)


def seconds_until(value) -> int | None:
    """Segundos até a data (negativo se já passou), ou None se não houver data."""
    value = to_datetime(value)
    return None if value is None else int((value - datetime.now()).total_seconds())
