import socket
import threading
skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
skt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
skt.settimeout()

try:
    skt.sendto(b"DISCOVER", ("255.255.255.255", 6082))
    resp, dirServer = skt.recvfrom(256)
    dirServer = dirServer[0]
    respServidor = resp.decode('utf-8')
    respPartes = respServidor.split()
    if respPartes[0] == "SERVER":
        umbralCPU = int(respPartes[1])
        umbralMEM = int(respPartes[2])
        puertoTCP = int(respPartes[3])
finally:
    skt.close()

if dirServer and puertoTCP:
    sktTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sktTCP.connect((dirServer, puertoTCP))
        sktTCP.send(b"REGISTER naciorol")
        resp = sktTCP.recv(256)
        respServidor = resp.decode('utf-8')
        if(respServidor != "REG_RESP"):
            #ERROR??
        else:
            while(1):


#IAIAIAIAIAIAIIAIAIAIAIIAIAIAIAIAIAIIAIAIAIAI
import socket
import threading
import time
import psutil

ultCPU = 0
ultMEM = 0
ultPROC = ""
lock = threading.Lock()  #SEMAFORO

def tareaMEDIDAS(sktTCP, umbralCPU, umbralMEM):
    global cpu, mem, proc
    cant = 0
    while True:
        cpu = 85   # Ejemplo
        mem = 40   # Ejemplo
        proc = "python,bash"
        
        with lock:
            ultCPU = cpu
            ultMEM = mem
            ultPROC = proc

        if cpu > umbralCPU:
            alerta = f"ALERTA CPU {cpu}"
            sktTCP.send(alerta.encode('utf-8'))
        if mem > umbralMEM:
            alerta = f"ALERTA MEM {mem}"
            sktTCP.send(alerta.encode('utf-8'))            
        time.sleep(5)
        cant = cant+1
        if cant == 3:
            cant = 0
            sktTCP.send(b"METRIC CPU {cpu}")
            sktTCP.send(b"METRIC MEM {mem}")


def tareaLeoSERVER(sktTCP):
    while True:
        sktTCP.recv(256)
        
sktTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sktTCP.connect((ip_server, puertoTCP))
sktTCP.send(b"REGISTER naciorol")

resp = sktTCP.recv(256).decode('utf-8').strip()

if resp == "REG_RESP":
    print("Registro exitoso. Iniciando hilos...")

    # Creamos e iniciamos los hilos secundarios
    # daemon=True garantiza que si el programa principal se cierra, estos hilos también mueren
    hilo_alertas = threading.Thread(target=tarea_muestreo_y_alertas, args=(sktTCP, umbralCPU, umbralMEM), daemon=True)
    hilo_reportes = threading.Thread(target=tarea_reporte_rutinario, args=(sktTCP,), daemon=True)
    
    hilo_alertas.start()
    hilo_reportes.start()

    # --- TAREA 3: El hilo principal solo escucha peticiones del Servidor ---
    while True:
        try:
            data = sktTCP.recv(256)
            if not data:
                print("Conexión cerrada por el servidor.")
                break
                
            mensaje = data.decode('utf-8').strip()
            
            if mensaje == "GET_PROC":
                with lock:
                    proc_lista = ult_proc
                sktTCP.send(f"PROC_LIST {proc_lista}".encode('utf-8'))
                
        except Exception as e:
            print(f"Error en recepción: {e}")
            break

sktTCP.close()

