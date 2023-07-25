
class Connections:
    def __init__(self):
        self.connections = {}


    def register(self, reference, connection):
        if reference not in self.connections:
            self.connections[reference] = connection

    def unregister(self, reference):
        if reference in self.connections:
            del self.connections[reference]


    