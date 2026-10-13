import socket,sys
s=socket.create_connection(('127.0.0.1',7070));f=s.makefile('rw')
for line in sys.stdin:
 f.write(line);f.flush();print(f.readline(),end='')
