import websockets

import sys
from pathlib import Path
# Allow usage of API's code
sys.path.append(str(Path(__file__).parent / '../../'))

from ws import connection, logic
from asyncio import Queue
from utils import checks


class Node:
	def __init__(self, id: int, db: object, hostname: str, name: str = None):
		self.id = id # Nodes ID
		self.db = db
		self.hostname = hostname
		self.__name = name
		self.connections = connection.Connections()

	@property
	def name(self):
		return self.__name if self.__name != None else self.id


	async def forward_to_other_node(self, reference, data, secret, node_addr: str = "localhost:8001"):
		_connection = connection.ForwardConnection(reference, self.db, node_addr, secret, data)
		await _connection.forward()


	async def get_correct_connections(self, destination, destination_type, sending_conn_ref):
		""" This gets the correct connections to send the event to, that way we arent sending events to people who should not be getting them, for example: someone receiving a message for a server they arent in at all. """

		match destination_type: # Since the destination is where the event is happening, we can just grab all users from the destination.
			case "guild":
				connections = self.db.db.query("SELECT user_id FROM guildusers WHERE parent_id = ?", destination)
			case "dmchannel":
				connections = self.db.db.query("SELECT user_id FROM dmchannelusers WHERE parent_id = ?", destination)
			case "user":
				connections = self.db.db.query("SELECT id FROM users WHERE id = ?", destination)
			case _:
				raise Exception("Something went wrong matching the correct destination.")
		print(f"Destination: {destination}")
		print(f"Possible destination connections: {connections}")
		to_return = []
		for reference in connections:
			for reference, conn in self.connections.connections.items():
				to_return.append(conn) if reference != sending_conn_ref else None
		print(f"Online Connections: {to_return}")
		return to_return


	async def broadcast(self, data, event, reference) -> None:
		""" Send received events"""
		conns = await self.get_correct_connections(event.destination, event.destination_type, reference)
		if len(conns) == 0:
			return False
		websockets.broadcast(conns, data)
		return True


	async def conn_recv_handler(self, _connection, reference, db_conn: logic.DBConn, secret: str = None) -> None:
		""" Receive incoming events """
		while _connection.closed != True:
			try:
				data = await _connection.recv()

				if checks.is_valid_event(data):
					event = logic.format_event(data, reference)
					error, msg = await db_conn.callables[event.event](event) # Process event
					if error == True:
						await _connection.send('event: error\ndata: {"error": "REPLACETHIS"}'.replace("REPLACETHIS", msg, 1))
						pass
					else:
						# TODO: appropriate logic for handling DB changes
						print(f"\nBroadcasting incoming event ({event.event})\n")
						if await self.broadcast(data, event, reference) == False: # Client connection wasnt found, forward to other node(s) TODO: logic for using exact reference ID for getting correct node
							await self.forward_to_other_node(reference, data, secret)
						del event
						pass
				else:
					print("Invalid event")
					pass
			except websockets.exceptions.ConnectionClosedError or websockets.exceptions.ConnectionClosedOK:
				pass