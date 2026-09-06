import socket
import threading
from threading import semaphore
from collections import deque
import logging



clave = "naciorol"
tamano = 256
clientes_comun = {}
clientes_admin = {}
id_actual_comun = 0
id_actual_admin = 0
s_clientes_admin = threading.Semaphore(1) #uno a la vez
s_clientes_comun = threading.Semaphore(1)

def server_main(): 
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
    try: 
        skt.sendto(adress[0], 6082, msj) # vamos a tener que hacer un loop
    except Exception as e:
        print(f"Error socket envio: {e}")
    respuesta = recibirCompleto(client)
    datos_texto = respuesta.decode('utf-8')
    msj, clave_ = datos_texto.split()
    if clave_ != clave :
        skt_tcp.close()
        return
    
    if "Register" in msj : # es cliente normal
        with s_clientes_comun:
            pila_MEM= deque()
            pila_CPU = deque()
            clientes_comun[id_actual_comun] = (adress[0], adress[1], pila_MEM, pila_CPU, client) # ip y puerto
            id_actual_comun+=1
        try:
            client.sendAll(b"REG_RESP")
        except Exception as e:
            print(f"Error socket envio: {e}")
        cli_comun(client)
    else :
        with s_clientes_admin:
            clientes_admin[id_actual_admin] = (adress[0], adress[1], client) # ip y puerto, será necesario para los admin??
            id_actual_admin+=1
        try:
            client.sendAll(b"ADMIN_RESP")
        except Exception as e:
            print(f"Error socket envio: {e}")
        cli_admin(client)
    
    return


logging.basicConfig(
    filename = "server.log",
    level = logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)



def cli_admin(client) :
    while True:
        m = (recibirCompleto(tamano)).decode("utf-8")
        tipoMensaje, *datos = m.split()
        match tipoMensaje:
            case "LIST AGENTS": 
                cantidad = 0
                respuesta = ""
                with s_clientes_comun:
                    for id in clientes_comun:
                        cantidad += cantidad
                        respuesta = respuesta + str(id)
                    respuesta = "AGENTS" + str(cantidad) + respuesta
                    try:
                        client.sendAll(str.encode(respuesta))
                    except Exception as e:
                        print(f"Error socket envio: {e}")
            case "GET PROC":
                procesos = pedirProcs(datos[0])
                respuesta = "PROC" + datos[0] + procesos
                try:
                        client.sendAll(str.encode(respuesta))
                except Exception as e:
                        print(f"Error socket envio: {e}")
            case "GET METRIC":
                valores = obtenerValores(datos[0], datos[1])
                respuesta = "MEASURMENTS" + datos[0] + datos[1] + valores
                try:
                        client.sendAll(str.encode(respuesta))
                except Exception as e:
                        print(f"Error socket envio: {e}")
            case "END":
                client.close()
        try:
            client.sendAll(str.encode("ERROR"))
        except Exception as e:
            print(f"Error socket envio: {e}")


def cli_comun(client) :
    while True:
        m = (recibirCompleto(client)).decode("utf-8")
        tipoMensaje, *datos = m.split()
        match tipoMensaje:
            case "METRIC": 
                if datos[0] == "CPU" :
                    with s_clientes_comun:
                        clientes_comun[3].append(datos[1]) 
                else:
                    with s_clientes_comun:
                        clientes_comun[2].append(datos[1])            
            case "ALERT":
                m_alerta  = "ALERT" + datos[0] + str(datos[1])
                logging.warning(m_alerta)
            case "END":
                client.close()
        #salgo del case == error
        try:
            client.sendAll(str.encode("ERROR"))
        except Exception as e:
            print(f"Error socket envio: {e}")
    return


def obtenerValores(idAgente, nombreMetrica):
    with s_clientes_comun:
        if nombreMetrica == "CPU":
            pila = clientes_comun[idAgente][3] # obtengo pila CPU
        else:
            pila = clientes_comun[idAgente][2] # pila MEM
        cantidad = 0
        respuesta = ""
        for metrica in reversed(pila):
            cantidad += cantidad
            respuesta = respuesta + str(metrica)
    respuesta = str(cantidad) + respuesta     
    return respuesta



def pedirProcs(idAgente):
    with s_clientes_comun:
        socket = clientes_comun[idAgente][-1]
    try:
        socket.sendAll(str.encode("GET_PROC"))
    except Exception as e:
        print(f"Error socket envio: {e}")
    respuesta = (recibirCompleto(socket)).decode("utf-8")
    tipoMensaje, datos = respuesta.split(maxsplit=1)
    return datos

def recibirCompleto(socket):
    completo = b""
    fin = "\n"
    while fin not in completo: 
        mens = socket.recv(tamano)
        if not mens:
            raise ConnectionError("Error en el socket")
        completo += mens
    return completo