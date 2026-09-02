import socket
import threading
import semaphore
skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# FALTA LOS LOOP PARA LOS MENSAJES
clave = "naciorol"
tamano = 256
clientes = {}
id_actual = 0
s_clientes = threading.Semaphore(1) #uno a la vez

ip = skt.getsockname()
skt.bind((ip, 6082))
msj, adress = skt.recvfrom(tamano)

threading.Thread(target=lobby_atender, args=(skt, adress, ip)).start()

def lobby_atender(skt, adress, ip) :
    skt_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
    skt_tcp.listen()

    skt_tcp.bind(ip, 0)
    puerto = skt_tcp.getSocketname()
    client, adress = skt_tcp.accept()
    msj = "SERVER 50 50" + puerto

    skt.sendto(adress[0], 6082, msj) # vamos a tener que hacer un loop
    respuesta = client.recv(tamano)
    datos_texto = respuesta.decode('utf-8')
    msj, clave_ = datos_texto.split(' ')
    if clave_ != clave :
        skt_tcp.close()
        return
    
    s_clientes.acquire()
    clientes[id_actual] = (adress[0], adress[1]) # ip y puerto
    id_actual+=1
    s_clientes.release()
    client.sendAll(REG_RESP)
    
    if "Register" in msj : # es cliente normal
        cli_comun(skt_tcp)
    else :
        cli_admin(skt_tcp)
    
    return

def cli_comun(skt_tcp) :

    return

def cli_admin(skt_tcp) :

    return