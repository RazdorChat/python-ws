import asyncio
import websockets
import sys
from pathlib import Path
# Allow usage of API's code, you need to put this code in a folder *in* the API's directory.
sys.path.append(str(Path(__file__).parent / '../../'))

from ws import node, logic
from utils import db

print("-----    Starting WS Server    -----.\n")
print("Connecting to DB")
_db = logic.DBConn(db) # Create the connection to the DB

current_node = node.Node(1) # TODO: limit conns to 10k/15k, redirect to another node at limit. 
print(f"Current node: {current_node.name}")

async def handler(connection):
    """ Handles a single WS connection. """
    print(f"\nIncoming Connection")

    reference = await _db.auth_handshake(connection)
    if reference == None:
        await connection.close()

    print(f"Accepting Connection with reference {reference}")
    await connection.send("event: confirmed\ndata: None")

    current_node.connections.register(reference, connection) # Register connection
    
    try:
        await current_node.conn_recv_handler(connection, reference, _db)
        await connection.wait_closed() # Wait until connection closes
    except websockets.exceptions.ConnectionClosedError or websockets.exceptions.ConnectionClosedOK:
        pass

    current_node.connections.unregister(reference) # Unregister connection
    print(f"Unregistered reference {reference}\n")

async def main():
    print("\n-----    Started WS Server    -----.\n")
    async with websockets.serve(handler, "localhost", 8001):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())