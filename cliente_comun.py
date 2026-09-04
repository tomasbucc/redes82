import socket
import threading
import time
import psutil

ultCPU = psutil.cpu_percent(interval=None, percpu=False)
ultMEM = psutil.virtual_memory()
ultPROC = ""

lock = threading.Lock() #semaforos

def tareaMedidas(sktTCP, umbralCPU, umbralMEM):
    global ultCPU, ultMEM, ultPROC
    cant = 0
    while True:
        cpu = psutil.cpu_percent(interval=None, percpu=False)
        mem = psutil.virtual_memory().percent
        proc = ""
        for p in psutil.process_iter(['pid', 'name']):
            proc = proc + str(p.info['pid']) + ":" + p.info['name'] + ", "
        with lock:
            ultCPU = cpu
            ultMEM = mem
            ultPROC = proc
        if cpu > umbralCPU:
            alerta = f"ALERT CPU {cpu}\n"
            with lock:
                sktTCP.sendall(alerta.encode('utf-8'))
        if mem > umbralMEM:
            alerta = f"ALERT MEM {mem}\n"
            with lock:
                sktTCP.sendall(alerta.encode('utf-8'))
        time.sleep(5)
        if(sktTCP.fileno() != -1):
            cant = cant + 1
            if cant == 3:
                cant = 0
                with lock:
                    try:
                        sktTCP.sendall(f"METRIC CPU {cpu}\n".encode('utf-8'))
                        sktTCP.sendall(f"METRIC MEM {mem}\n".encode('utf-8'))
                    except Exception as e:
                        print(f"Error socket envio: {e}")
        else:
            break

dirServer = None
puertoTCP = None
sktTCP = None 
skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
skt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
skt.settimeout(10)
try:
    skt.sendto(b"DISCOVER\n", ("255.255.255.255", 6082))
    resp, dirServer = skt.recvfrom(256)
    dirServer = dirServer[0]
    respServidor = resp.decode('utf-8')
    respPartes = respServidor.split()
    if len(respPartes) == 4 and respPartes[0] == "SERVER":
        umbralCPU = int(respPartes[1])
        umbralMEM = int(respPartes[2])
        puertoTCP = int(respPartes[3])
except Exception as e:
    print(f"Error conexion UDP: {e}") #ERROR UDP
finally:
    skt.close()

if dirServer and puertoTCP:
    sktTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sktTCP.connect((dirServer, puertoTCP))
        sktTCP.sendall(b"REGISTER naciorol\n")
        bufferRespServ = b""
        while True:
            try:
                if b"\n" not in bufferRespServ:
                    resp = sktTCP.recv(256) 
                    if not resp:
                        break
                    bufferRespServ += resp
                    continue
                break
            except Exception as e:
                print(f"Error en recepcion de ACK: {e}")
                break
        respServidor, bufferRespServ = bufferRespServ.split(b"\n", 1)
        respServidor = respServidor.decode('utf-8').strip()
        if(respServidor == "REG_RESP"):
            hiloTomoMedida = threading.Thread(target = tareaMedidas, args=(sktTCP, umbralCPU, umbralMEM), daemon=True)
            hiloTomoMedida.start()
            buffer = b""
            while True:
                try:
                    if b"\n" not in buffer:
                        data = sktTCP.recv(256)
                        if not data:
                            break  # CERRO CONEXION
                        buffer += data
                        continue
                    mensaje, buffer = buffer.split(b"\n", 1)
                    mensaje = mensaje.decode('utf-8').strip()
                    if mensaje == "GET_PROC":
                        with lock:
                            listaProcs = ultPROC
                            sktTCP.sendall(f"PROC {listaProcs}\n".encode('utf-8'))
                    if mensaje == "ERROR":
                        print("Hubo un error, cerrando cliente")
                        break
                except Exception as e:
                    print(f"Error en loop de mensajes: {e}")
                    break
    except Exception as e:
        #ERROR EN CONEXION
        print(f"Error en conexion TCP: {e}")
if sktTCP:
    sktTCP.sendall("END\n".encode('utf-8'))
    sktTCP.close()

