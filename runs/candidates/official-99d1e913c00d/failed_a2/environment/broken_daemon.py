#!/usr/bin/env python3
# Initial deployment placeholder; the reference deployment installs the service.
import socket
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('0.0.0.0',4711)); s.listen()
while True:
 c,_=s.accept(); c.sendall(b'{"ok":false,"error":"not ready"}\n'); c.close()
