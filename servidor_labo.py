import socket
import threading
import semaphore
from collections import deque
skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# FALTA CONTROLAR ERRORES
# FALTA CAMBIAR LAS VARIABLES INTS A STRING PARA CONCATENAR, AHORA ESTÁ MAL.
# FALTA LOS LOOP PARA LOS MENSAJES
clave = "naciorol"
tamano = 256
clientes_comun = {}
clientes_admin = {}
id_actual_comun = 0
id_actual_admin = 0
s_clientes_admin = threading.Semaphore(1) #uno a la vez
s_clientes_comun = threading.Semaphore(1)

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
    msj, clave_ = datos_texto.split()
    if clave_ != clave :
        skt_tcp.close()
        return
    
    if "Register" in msj : # es cliente normal
        s_clientes_comun.acquire()
        pila = deque()
        clientes_comun[id_actual_comun] = (adress[0], adress[1], pila , client) # ip y puerto
        id_actual_comun+=1
        s_clientes_comun.release()
        client.sendAll("REG_RESP")
        cli_comun(client)
    else :
        s_clientes_admin.acquire()
        clientes_admin[id_actual_admin] = (adress[0], adress[1], client) # ip y puerto, será necesario para los admin??
        id_actual_admin+=1
        s_clientes_admin.release()
        client.sendAll("ADMIN_RESP")
        cli_admin(client)
    
    return

def cli_comun(client) :
    while True:
        m = (client.recv(tamano)).decode("utf-8")
        tipoMensaje, *datos = m.split()
        match tipoMensaje:
        case "LIST AGENTS": 
            s_clientes_comun.acquire()
            cantidad = 0
            respuesta = ""
            for id in clientes_comun:
                cantidad += cantidad
                respuesta = respuesta + id
            s_clientes_comun.acquire()
            respuesta = "AGENTS" + cantidad + respuesta
            client.sendAll(respuesta)
        case "GET PROC":
            procesos = pedirProcs(datos[0])
            respuesta = "PROC" + datos[0] + procesos
            client.sendAll(respuesta)
        case "GET METRIC":
            valores = obtenerValores(datos[0])
            respuesta = "MEASURMENTS" + datos[0] + datos[1] + valores
            client.sendAll(respuesta)
        case ERROR: # caso en el que da error.

    


return

def cli_admin(client) :

    return


def obtenerValores(idAgente):
    s_clientes_comun.acquire()
    socket = clientes_comun[idAgente][-2] # obtengo pila
    cantidad = 0
    respuesta = ""
    for metrica in reversed(pila):
        cantidad += cantidad
        respuesta = respuesta + metrica
    s_clientes_comun.release()
    respuesta = cantidad + respuesta     
return respuesta





def pedirProcs(idAgente):
    s_clientes_comun.acquire()
    socket = clientes_comun[idAgente][-1]
    s_clientes_comun.release()
    socket.sendall("GET_PROC")
    respuesta = (socket.recv(tamano)).decode("utf-8")
    tipoMensaje, datos = respuesta.split(maxsplit=1)
return datos
