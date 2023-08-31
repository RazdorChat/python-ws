# TODO: maybe switch to jsonc


# Websites domain name. This is NEEDED if you are hosting publicly on a website. You will need to setup your domain/nginx correctly to match this.
# If you are hosting locally, just set this to the IP.
hostname = "ws.razdor.chat" 

# The IP given to the WS server to host on.
ip = "0.0.0.0"

# I recommend sequentially doing ports. If this is the first WS node, you would use 42044 for the second one, and going upwards.
port = 42043 

# The URL used to communicate with the API. The endpoint is required.
api_url = "http://localhost:42042/api/nodes"