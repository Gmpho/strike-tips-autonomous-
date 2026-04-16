import socket, threading, sys

def handle(c):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 11434))
        def fwd(a, b):
            try:
                while True:
                    data = a.recv(4096)
                    if not data: break
                    b.sendall(data)
            except: pass
            a.close(); b.close()
        threading.Thread(target=fwd, args=(c, s)).start()
        fwd(s, c)
    except: c.close()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 11435))
server.listen(5)
print("Proxy listening on 0.0.0.0:11435")
while True:
    threading.Thread(target=handle, args=(server.accept()[0],)).start()
