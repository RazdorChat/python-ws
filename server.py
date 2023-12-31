import asyncio
import websockets
import sys
from pathlib import Path
# Allow usage of API's code, you need to put this code in a folder *in* the API's directory.
sys.path.append(str(Path(__file__).parent / '../../'))

from ws import node, logic, connection
from utils import db
from ws import config

print("-----    Starting WS Server    -----.\n")

print("Reading secret.txt")
try:
	secret = open("secret.txt", "r").read()
except FileNotFoundError:
	print("File not found, please start the API first and let it generate secret.txt")
	exit(0)

print("Connecting to DB")
_db = logic.DBConn(db, secret) # Create the connection to the DB
print("Connected")

current_node = node.Node(f"{config.ip}:{config.port}", db=_db, hostname=config.hostname) # TODO: redirect to another node at limit.
api = connection.ApiConnection(_db, config.api_url, secret, current_node)
print(f"{api.get_node_addrs()} other nodes running")

async def handler(connection):
	""" Handles a single WS connection. """
	print(f">>> Incoming Connection")
	global AT_LIMIT
	forwarding = False
	try:
		reference = await _db.auth_handshake(connection)
	except websockets.exceptions.ConnectionClosedError or websockets.exceptions.ConnectionClosedOK:
		return
	if reference == None:
		await connection.close()
	elif len(current_node.connections.connections) >= current_node.connections.limit:
		AT_LIMIT = True

	if AT_LIMIT and reference != secret: # Accept other node connections even if at limit
		print("<<< Auto-Closing ")
		return
	elif reference == secret:
		forwarding = True

	print(f"<<< Accepting Connection")
	await connection.send("event: confirmed\ndata: None")

	if not forwarding:
		current_node.connections.register(reference, connection) # Register connection
	elif forwarding:
		print(">>> Forwarding from other Node")
		reference == await connection.recv() # Get actual reference from forwarding Node
		data = await connection.recv()
		event = logic.format_event(data, reference)
		await current_node.broadcast(data, event, reference) # Forward the event to all connections
		return # Close the connection
	try:
		asyncio.create_task(current_node.conn_recv_handler(connection, reference, _db, secret)) # Receive events
		await connection.wait_closed() # Wait until connection closes
	except websockets.exceptions.ConnectionClosedError or websockets.exceptions.ConnectionClosedOK:
		current_node.connections.unregister(reference) # Unregister connection

	current_node.connections.unregister(reference) # Unregister connection
	print(f">>> Closed connection ({reference})\n")
	if len(current_node.connections.connections) <= current_node.connections.limit:
		AT_LIMIT = False
	return

async def main():
	print("\n-----    Started WS Server    -----.\n")
	print("Registering to API")
	if api.register_to_api(config.hostname, config.port, config.hostname) == True:
		print("Registered.")
	else:
		print("Error registering to API...")
	print("Starting API cache loop\n")
	global cache_loop
	cache_loop = asyncio.create_task(api.refresh_nodes())
	print(f"Current info: {current_node.name}")														 # NOTE: May be too low, if so: set to 524288
	async with websockets.serve(handler, config.ip, config.port, compression=None, ping_interval=30, max_size=262144): # Disable compression at cost of network bandwidth
		await asyncio.Future()  # run forever

def cleanup_before_exit():
	print("\n----    Exiting    -----\n")
	print("Closing DB connection...")
	_db.db.pool.close()
	print("Unregistering from API...")
	api.unregister_from_api()
	print("Closing cache task...")
	cache_loop.cancel()
	print("Done.")


if __name__ == "__main__":
	global AT_LIMIT
	AT_LIMIT = False
	try:
		try:
			asyncio.run(main())
		except KeyboardInterrupt:
			cleanup_before_exit()
	except KeyboardInterrupt:
		print("Stop trying to force exit, attemping cleaning again...")
		cleanup_before_exit()
