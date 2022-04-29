## What is this?
>This is a personal project, my idea was to learn about sokets, multithreading and selectors in Python.
The main problem arose in my work center, the P2P connection was disabled.
This project allows other user to access servers that the don't have access to via bridge.

### How does it work?
<p style="text-align: center">
<img src="./bridge_picture.png" alt="bridge-picture">
</p>

#### How to start the bridge server
```python
from bridge import Bridge
server_host = ("localhost", 5000)
ctrl_host = ("localhost", 5001)
Bridge().start_server(server_host, ctrl_host)
```

### How to start the bridge client
```python
from bridge import Bridge
ctrl_host = ("localhost", 5001)
destination = ("example.site.com", 80)
Bridge().start_client(destination, ctrl_host)
```

Created with <3 by AngeloHH