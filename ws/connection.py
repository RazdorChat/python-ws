import requests
from asyncio import sleep
import websockets

class ForwardConnection:
	def __init__(self, reference, db: object, addr_port: str, secret: str, msg: str | bytes) -> None:
		self.db = db
		self.url = addr_port
		self.msg = msg
		self.reference = reference
		self.secret = secret

	async def forward(self):
		async with websockets.connect(f"ws://{self.url}") as websocket:
			await websocket.send(f"{self.secret}:None")
			await websocket.send(self.reference)
			await websocket.send(self.msg)
			


class ApiConnection:
	def __init__(self, db, api_url: str, secret: str, node: object):
		self.api_url = api_url
		self.db = db
		self.secret = secret
		self.node = None
		self.redis = db.redis

	def insert_node(self, node_object: object):
		self.node = node_object

	def register_to_api(self, addr: str, port: int):
		""" Adds the Node to the API's node list """
		data = {
			"name": self.node.name,
			"id": self.node.id,
			"addr": addr,
			"port": port,
			"secret": self.secret
		}
		resp = requests.post(f"{self.api_url}/ws/register", json=data)
		if resp.status_code == 200:
			if resp.json()["op"] == "Added":
				return True

	def unregister_from_api(self):
		""" Removes the Node from the API's node list"""
		data = {
			"name":  self.node.name,
			"id": self.node.id,
			"secret": self.secret
		}
		resp = requests.post(f"{self.api_url}/ws/unregister", json=data)
		if resp.status_code == 200:
			if resp.json()["op"] == "Removed":
				return True


	def notify_at_limit(self):
		""" Notifies the API that connection limit has been met (node has stopped accepting WS connections) """
		data = {
			"name":  self.node.name,
			"id": self.node.id,
			"secret": self.secret
		}
		resp = requests.post(f"{self.api_url}/ws/update", json=data)
		if resp.status_code == 200:
			return True


	async def refresh_nodes(self):
		""" Refreshes the internal cache for forwarding events """
		while True:
			resp = requests.get(f"{self.api_url}/ws/nodes")
			if resp.status_code == 200:
				iteration = 0
				data = resp.json()["op"]
				for node in data:
					iteration += 1
					self.redis.set(f"nodes-cache:{iteration}", node)
			await sleep(300) # refresh every 5m

	def get_node_addrs(self):
		resp = requests.get(f"{self.api_url}/ws/nodes")
		if resp.status_code == 200:
			data = resp.json()["op"]
			if data == "void":
				return 0 # No online Nodes
			elif type(data) == str:
				return 1 # 1 other online node
			return len(data)



class Connections:
	def __init__(self):
		self.connections = {}
		self.limit = 1


	def register(self, reference, connection) -> bool:
		if reference not in self.connections:
			self.connections[reference] = connection
			return True

	def unregister(self, reference) -> None:
		if reference in self.connections:
			del self.connections[reference]


