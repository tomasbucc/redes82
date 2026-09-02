import socket
import threading
skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# FALTA LOS LOOP PARA LOS MENSAJES

ip = skt.getsockname()
skt.bind((ip, 6082))
msj, adress = skt.recvfrom(tamano) #tamaño

threading.Thread(target=lobby_atender, args=(skt, adress, ip)).start()

def lobby_atender(skt, adress, ip) :
    skt_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
    skt_tcp.listen()
    skt_tcp.bind(ip, 0)
    puerto = skt_tcp.getSocketname()
    client, adress = skt_tcp.accept()
    msj = "SERVER 50 50" + puerto
    skt.sendto(adress, 6082, msj)
    respuesta = client.recv(tamano)
    if respuesta :

    return