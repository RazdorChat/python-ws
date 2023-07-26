import websockets

import sys
from pathlib import Path
# Allow usage of API's code
sys.path.append(str(Path(__file__).parent / '../../'))

from ws import connection, logic
from asyncio import Queue
from utils import checks


class Node:
    def __init__(self, id: int, name: str = None):
        self.id = id # Nodes ID
        self.name = name if name != None else f"Node-{id}"
        self.connections = connection.Connections()
        self.message_queue = Queue()


    async def broadcast(self, data, connections) -> None:
        """ Send received events"""
        websockets.broadcast(connections, data)


    async def conn_recv_handler(self, connection, reference, db_conn: logic.DBConn) -> None:
        """ Receive incoming events """
        while connection.closed != True:
            try:
                data = await connection.recv()

                if checks.is_valid_event(data):
                    event = logic.format_event(data, reference)
                    error, msg = await db_conn.callables[event.event](event)
                    if error == True:
                        await connection.send('event: error\ndata: {"error": "REPLACETHIS"}'.replace("REPLACETHIS", msg, 1))
                        pass
                    else:
                        # TODO: appropriate logic for handling DB changes
                        print(f"\nBroadcasting incoming event ({event.event})\n")
                        del event
                        conns = [value for key,value in self.connections.connections.items()]
                        await self.broadcast(data, conns) # TODO: logic for getting correct connections based on reference
                        pass
                else:
                    print("Invalid event")
                    pass
            except websockets.exceptions.ConnectionClosedError or websockets.exceptions.ConnectionClosedOK:
                pass