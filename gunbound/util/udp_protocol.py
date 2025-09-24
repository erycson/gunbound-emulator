import asyncio

class UDPFutureProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport = None
        self.response_future = asyncio.Future()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if not self.response_future.done():
            self.response_future.set_result(data)