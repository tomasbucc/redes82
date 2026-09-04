import socket

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
    print(f"Error conexion UDP: {e}")
finally:
    skt.close()

if dirServer and puertoTCP:
    sktTCP = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sktTCP.connect((dirServer, puertoTCP))
        sktTCP.sendall(b"ADMIN naciorol\n")
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
        if b"\n" not in bufferRespServ:
            print("No se recibio una respuesta valida del servidor al registrarse")
        else:
            respServidor, bufferRespServ = bufferRespServ.split(b"\n", 1)
            respServidor = respServidor.decode('utf-8').strip()
            if respServidor == "ADMIN_RESP":
                buffer = b""
                while True:
                    msj = input("Conectado al Servidor: ")
                    sktTCP.sendall(f"{msj}\n".encode('utf-8'))
                    if msj == "END":
                        break
                    try:
                        while b"\n" not in buffer:
                            data = sktTCP.recv(256)
                            if not data:
                                break
                            buffer += data
                        mensaje, buffer = buffer.split(b"\n", 1)
                        mensaje = mensaje.decode('utf-8').strip()
                        if mensaje != '':
                            partes = mensaje.split()
                            match partes[0]:
                                case "AGENTS":
                                    print(mensaje)
                                case "PROC":
                                    print(mensaje)
                                case "MEASUREMENTS":
                                    print(mensaje)
                                case "ERROR":
                                    print("Hubo un error, repetir mensaje")
                                case _:
                                    print("Error mensaje respuesta no reconocido, cerrando conexion")
                                    break
                    except Exception as e:
                        print(f"Error en loop de mensajes: {e}")
                        break
            else:
                print(f"Registro como admin fallido, respuesta del servidor: {respServidor}")
    except Exception as e:
        print(f"Error en conexion TCP: {e}")

if sktTCP:
    sktTCP.close()
