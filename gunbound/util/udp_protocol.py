from asyncio import DatagramProtocol, Future

class UDPFutureProtocol(DatagramProtocol):
    def __init__(self):
        self.transport = None
        self.response_future = Future()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.response_future.set_result((data, addr))

    # def error_received(self, exc):
    #     print(f"Error received: {exc}")
    #     self.response_future.set_exception(exc)

    # def connection_lost(self, exc):
    #     print(f"Connection lost: {exc}")
    #     self.response_future.set_exception(exc)