import asyncio
import websockets
import sys
from pathlib import Path
# Allow usage of API's code, you need to put this code in a folder *in* the API's directory.
sys.path.append(str(Path(__file__).parent / '../../'))

from ws import node, logic, connection
from utils import db

# TODO: get the API's url
API_URL = "http://localhost:42042/api/nodes"

print("-----    Starting WS Server    -----.\n")

print("Reading secret.txt")
try:
    secret = open("secret.txt", "r").read()
except FileNotFoundError:
    print("File not found, please start the API first and let it generate secret.txt")
    exit(0)

print("Connecting to DB")
_db = logic.DBConn(db) # Create the connection to the DB
print("Connected")

current_node = node.Node(1) # TODO: limit conns to 10k/15k, redirect to another node at limit.
api = connection.ApiConnection(_db, API_URL, secret, current_node)

async def handler(connection):
    """ Handles a single WS connection. """
    global AT_LIMIT
    if AT_LIMIT:
        print("<<< Auto-Closing ")
        return
    
    print(f">>> Incoming Connection")

    if len(current_node.connections.connections) >= current_node.connections.limit:
        AT_LIMIT = True
        api.notify_at_limit()
        print("<<< Closing connection (at limit)")
        return

    reference = await _db.auth_handshake(connection)
    if reference == None:
        await connection.close()

    print(f"<<< Accepting Connection ({reference})")
    await connection.send("event: confirmed\ndata: None")

    current_node.connections.register(reference, connection) # Register connection
    
    asyncio.create_task(current_node.conn_recv_handler(connection, reference, _db))
    await connection.wait_closed() # Wait until connection closes

    current_node.connections.unregister(reference) # Unregister connection
    print(f">>> Closed connection ({reference})\n")

async def main():
    print("\n-----    Started WS Server    -----.\n")
    print("Registering to API")
    if api.register_to_api("localhost", 8001) == True:
        print("Registered.")
    else:
        print("Error registering to API...")
    print("Starting API cache loop\n")
    global cache_loop
    cache_loop = asyncio.create_task(api.refresh_nodes())
    print(f"Current node: {current_node.name}")
    async with websockets.serve(handler, "localhost", 8001):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    global AT_LIMIT
    AT_LIMIT = False
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n----    Exiting    -----\n")
        print("Closing DB connection...")
        _db.db.pool.close()
        print("Unregistering from API...")
        api.unregister_from_api()
        print("Closing cache task...")
        cache_loop.cancel()
        print("Done.")