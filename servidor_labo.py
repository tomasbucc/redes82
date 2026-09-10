import socket
import threading
from collections import deque
import logging

logging.basicConfig(
    filename="server.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

CLAVE = "naciorol"
TAMANO = 256
UMBRAL_CPU = 50
UMBRAL_MEM = 50
PUERTO_UDP = 6082
clientes_comun = {}
clientes_admin = {}
id_actual_comun = 0
id_actual_admin = 0

s_clientes_admin = threading.Lock()
s_clientes_comun = threading.Lock()


def server_main():
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    skt.bind(("", PUERTO_UDP))
    print(f"Servidor escuchando DISCOVER en puerto UDP {PUERTO_UDP}")

    while True:
        try:
            msj, adress = skt.recvfrom(TAMANO)
        except Exception as e:
            print(f"Error recibiendo discovery: {e}")
            continue
        if msj.strip() == b"DISCOVER":
            threading.Thread(
                target=lobby_atender, args=(skt, adress), daemon=True
            ).start()


def lobby_atender(skt, adress):
    skt_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    skt_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        skt_tcp.bind(("", 0))
        skt_tcp.listen(1)
        puerto = skt_tcp.getsockname()[1]

        msj = f"SERVER {UMBRAL_CPU} {UMBRAL_MEM} {puerto}"
        skt.sendto(msj.encode('utf-8'), adress)

        skt_tcp.settimeout(15)
        client, direccionCliente = skt_tcp.accept()
    except Exception as e:
        print(f"Error preparando conexion TCP para {adress}: {e}")
        skt_tcp.close()
        return

    try:
        registrar_cliente(client, direccionCliente)
    except Exception as e:
        print(f"Error registrando cliente {direccionCliente}: {e}")
        client.close()


def recibirLinea(sock, buffer):
    """
    Recibe hasta completar una linea terminada en '\\n'.
    Devuelve (mensaje, buffer_restante). mensaje es None si el
    socket se cerro del otro lado (recv devolvio vacio).
    """
    while b"\n" not in buffer:
        datos = sock.recv(TAMANO)
        if not datos:
            return None, buffer
        buffer += datos
    mensaje, buffer = buffer.split(b"\n", 1)
    return mensaje, buffer


def enviarSeguro(sock, lock, datos_bytes):
    try:
        with lock:
            sock.sendall(datos_bytes)
    except Exception as e:
        print(f"Error enviando datos: {e}")


def registrar_cliente(client, direccionCliente):
    global id_actual_comun, id_actual_admin

    buffer = b""
    linea, buffer = recibirLinea(client, buffer)
    if linea is None:
        client.close()
        return

    datos_texto = linea.decode('utf-8').strip()
    partes = datos_texto.split()
    if len(partes) != 2:
        client.close()
        return

    tipoRegistro, claveRecibida = partes
    if claveRecibida != CLAVE:
        client.close()
        return

    if tipoRegistro == "REGISTER":
        with s_clientes_comun:
            miId = id_actual_comun
            id_actual_comun += 1  
            clientes_comun[miId] = {
                "ip": direccionCliente[0],
                "puerto": direccionCliente[1],
                "pila_cpu": deque(maxlen=100),
                "pila_mem": deque(maxlen=100),
                "socket": client,
                "send_lock": threading.Lock(),
                "ultimo_proc": "",
                "proc_event": threading.Event(),
            }
        enviarSeguro(client, clientes_comun[miId]["send_lock"], b"REG_RESP\n")
        cli_comun(client, miId, buffer)

    elif tipoRegistro == "ADMIN":
        with s_clientes_admin:
            miId = id_actual_admin
            id_actual_admin += 1
            clientes_admin[miId] = {
                "ip": direccionCliente[0],
                "puerto": direccionCliente[1],
                "socket": client,
                "send_lock": threading.Lock(),
            }
        enviarSeguro(client, clientes_admin[miId]["send_lock"], b"ADMIN_RESP\n")
        cli_admin(client, miId, buffer)

    else:
        client.close()


def cli_comun(client, miId, buffer):
    try:
        while True:
            mensaje, buffer = recibirLinea(client, buffer)
            if mensaje is None:
                break

            texto = mensaje.decode('utf-8').strip()
            if texto == "":
                continue

            partesTodas = texto.split(maxsplit=1)
            tipoMensaje = partesTodas[0]
            resto = partesTodas[1] if len(partesTodas) > 1 else ""

            if tipoMensaje == "METRIC":
                datos = resto.split()
                if len(datos) >= 2:
                    metrica, valor = datos[0], datos[1]
                    with s_clientes_comun:
                        if miId in clientes_comun:
                            if metrica == "CPU":
                                clientes_comun[miId]["pila_cpu"].append(valor)
                            elif metrica == "MEM":
                                clientes_comun[miId]["pila_mem"].append(valor)

            elif tipoMensaje == "ALERT":
                logging.warning(f"ALERT cliente {miId}: {resto}")

            elif tipoMensaje == "PROC":
                with s_clientes_comun:
                    if miId in clientes_comun:
                        clientes_comun[miId]["ultimo_proc"] = resto
                        clientes_comun[miId]["proc_event"].set()

            elif tipoMensaje == "END":
                break 

            else:
                with s_clientes_comun:
                    entrada = clientes_comun.get(miId)
                if entrada:
                    enviarSeguro(client, entrada["send_lock"], b"ERROR\n")
    except Exception as e:
        print(f"Error en cli_comun ({miId}): {e}")
    finally:
        with s_clientes_comun:
            clientes_comun.pop(miId, None)
        client.close()


def cli_admin(client, miId, buffer):
    try:
        while True:
            mensaje, buffer = recibirLinea(client, buffer)
            if mensaje is None:
                break

            texto = mensaje.decode('utf-8').strip()
            if texto == "" or texto == "END":
                break

            partes = texto.split()
            comando = partes[0] if partes else ""

            try:
                if comando == "LIST_AGENTES":
                    respuesta = listar_agentes()
                elif comando == "GET_PROC" and len(partes) >= 2:
                    idAgente = int(partes[1])
                    respuesta = "PROC " + str(idAgente) + " " + pedirProcs(idAgente)
                elif comando == "GET_METRIC" and len(partes) >= 3:
                    idAgente = int(partes[1])
                    nombreMetrica = partes[2]
                    valores = obtenerValores(idAgente, nombreMetrica)
                    respuesta = f"MEASUREMENTS {idAgente} {nombreMetrica} {valores}"
                else:
                    respuesta = "ERROR"
            except (ValueError, KeyError) as e:
                print(f"Comando invalido de admin {miId}: {e}")
                respuesta = "ERROR"

            with s_clientes_admin:
                entrada = clientes_admin.get(miId)
            if entrada:
                enviarSeguro(client, entrada["send_lock"], (respuesta + "\n").encode('utf-8'))
    except Exception as e:
        print(f"Error en cli_admin ({miId}): {e}")
    finally:
        with s_clientes_admin:
            clientes_admin.pop(miId, None)
        client.close()


def listar_agentes():
    with s_clientes_comun:
        ids = list(clientes_comun.keys())
    return "AGENTS " + str(len(ids)) + " " + " ".join(str(i) for i in ids)


def obtenerValores(idAgente, nombreMetrica):
    with s_clientes_comun:
        entrada = clientes_comun.get(idAgente)
        if entrada is None:
            return "0"
        pila = entrada["pila_cpu"] if nombreMetrica == "CPU" else entrada["pila_mem"]
        valores = list(reversed(pila)) 
    return str(len(valores)) + " " + " ".join(valores)


def pedirProcs(idAgente):
    with s_clientes_comun:
        entrada = clientes_comun.get(idAgente)
    if entrada is None:
        return "agente no encontrado"

    entrada["proc_event"].clear()
    enviarSeguro(entrada["socket"], entrada["send_lock"], b"GET_PROC\n")

    if entrada["proc_event"].wait(timeout=10):
        with s_clientes_comun:
            entrada_actual = clientes_comun.get(idAgente)
            return entrada_actual["ultimo_proc"] if entrada_actual else ""
    return "timeout esperando respuesta del agente"


if __name__ == "__main__":
    server_main()