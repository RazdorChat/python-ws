import requests
import sys
from pathlib import Path
# Allow usage of API's code
sys.path.append(str(Path(__file__).parent / '../../'))

from datetime import datetime
from utils import id_generator, checks, redis
from json import loads
from models.events import Event

def get_redis():
	return redis.RDB

class FormatError(Exception):
	def __init__(self, message):            
		super().__init__(message)
		self.message = message

def format_event(raw_event_data, conn_ref: int, delim: str = "\n"): # This code is wacky...
	split = raw_event_data.split(delim) # Split the data by '\n', seperating the event and the data.
	loaded_json =  loads(split[1].split(":", 1)[1]) # Seperate the data tag from the actual json needed.
	if 'destination' in loaded_json.keys(): 
		try:
			destination = loaded_json['destination'].split(":", 1) # dest:destID
		except Exception as e:
			raise FormatError("Destination type (or ID) not specified") # One of the above was not there.
		if len(destination) != 2: # This shouldnt run, but i want to explicitly check anyways.
			raise FormatError("Destination type (or ID) not specified.")
		elif not checks.is_valid_destination(destination[0]): # Check if the event destination is valid.
			raise FormatError("Invalid Destination.")
	elif 'destination' not in loaded_json.keys(): # No destination.
		destination = [None, None]
	return Event(split[0].split(":", 1)[1].strip(), conn_ref, destination[1], destination[0], loaded_json)

def format_auth_handshake(raw_data, delim: str = ":"):
	split = raw_data.split(delim)
	if len(split) != 2:
		return False, None
	return split[0], split[1]


class DBConn:
	def __init__(self, db, secret):
		self.redis = get_redis()
		db.DB_CONFIG_PATH = f"../{db.DB_CONFIG_PATH}"
		self.db = db.DB(db.mariadb_pool(0)) # Create the connection to the DB

		self.callables = { # Easy way out for calling the correct code for the correct event
			"new_message": self.save_new_message
		}
		self.secret = secret

	async def auth_handshake(self, connection):
		await connection.send("event: identify\ndata: None")
		data = await connection.recv()
		_id, _auth = format_auth_handshake(data) # userID:access_token
		del data
		if str(_id) == str(self.secret): # Another Node
			return _id
		if _id == False or _auth == None:
			await connection.send("Bad token.")
			return None
		elif checks.authenticated(_auth, self.redis.get(_id)) != True:
			await connection.send("Bad token.")
			return None
		return _id

	async def save_new_message(self, event: Event):
		dmID = None
		if event.destination_type == "dmchannel":
			query = "INSERT INTO DMChannelmessages (id, authorID, DMChannelID, content, sent_timestamp) VALUES (?,?,?,?,?)"
			check = dmID = self.db.query_row("SELECT id FROM DMchannels WHERE id = ?", event.destination)
			if not check:
				return True, "Channel doesnt exist."
		elif event.destination_type == "user":
			dmID = self.db.query_row("SELECT id FROM DMs WHERE (UserOneID = ? AND UserTwoID = ?) or (UserTwoID = ? AND UserOneID = ?)", event.destination, event.conn_ref,  event.destination, event.conn_ref)
			if not dmID: # Dms dont exist
				self.db.execute("INSERT INTO DMs (id, UserOneID, UserTwoID) VALUES (?,?,?)", id_generator.generate_dm_id(self.db), event.conn_ref, event.destination)

			query = "INSERT INTO DMmessages (id, authorID, DmID, content, sent_timestamp) VALUES (?,?,?,?,?)"
		elif event.destination_type == "guild":
			check = dmID = self.db.query_row("SELECT id FROM channels WHERE id = ?", event.destination)
			if not check:
				return True, "Channel or guild doesnt exist."
			query = "INSERT INTO messages (id, authorID, channelID, content, sent_timestamp) VALUES (?,?,?,?,?)"

		_id = id_generator.generate_message_id(self.db) # Generate the UID 
		timestamp = datetime.now().timestamp()

		self.db.execute(query, _id, event.conn_ref, dmID if dmID != None else event.destination, event.data["content"], timestamp)
		return None, None