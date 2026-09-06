import socket
import threading
import time
import sys

import servidor_labo as servidor

PUERTO_UDP = servidor.PUERTO_UDP
HOST = "127.0.0.1"
TIMEOUT = 5

resultados = []


def check(nombre, condicion, detalle=""):
    estado = "OK" if condicion else "FALLO"
    resultados.append((nombre, condicion))
    linea = f"[{estado}] {nombre}"
    if detalle and not condicion:
        linea += f" -- {detalle}"
    print(linea)
    return condicion


def recibir_linea(sock, buffer):
    while b"\n" not in buffer:
        datos = sock.recv(256)
        if not datos:
            return None, buffer
        buffer += datos
    linea, buffer = buffer.split(b"\n", 1)
    return linea, buffer


def descubrir_servidor():
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    skt.settimeout(TIMEOUT)
    try:
        skt.sendto(b"DISCOVER\n", (HOST, PUERTO_UDP))
        resp, _ = skt.recvfrom(256)
    finally:
        skt.close()
    partes = resp.decode('utf-8').split()
    if len(partes) != 4 or partes[0] != "SERVER":
        return None
    return {
        "umbralCPU": int(partes[1]),
        "umbralMEM": int(partes[2]),
        "puertoTCP": int(partes[3]),
    }


def conectar_y_registrar(puertoTCP, tipo):
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    skt.settimeout(TIMEOUT)
    skt.connect((HOST, puertoTCP))
    skt.sendall(f"{tipo} naciorol\n".encode('utf-8'))
    buffer = b""
    linea, buffer = recibir_linea(skt, buffer)
    resp = linea.decode('utf-8').strip() if linea else None
    return skt, buffer, resp


def test_discovery():
    print("\n== Discovery UDP ==")
    info = descubrir_servidor()
    ok = check("El servidor responde al DISCOVER con formato SERVER valido",
               info is not None, "no se recibio 'SERVER <cpu> <mem> <puerto>'")
    if ok:
        check("Los umbrales recibidos coinciden con los configurados en el servidor",
              info["umbralCPU"] == servidor.UMBRAL_CPU and info["umbralMEM"] == servidor.UMBRAL_MEM,
              f"recibido: {info}")
    return info


def test_registro_comun(info):
    print("\n== Registro de cliente comun ==")
    skt, buffer, resp = conectar_y_registrar(info["puertoTCP"], "REGISTER")
    ok = check("El servidor responde REG_RESP a REGISTER",
               resp == "REG_RESP", f"respuesta recibida: {resp!r}")
    if not ok:
        skt.close()
        return None, None
    return skt, buffer


def test_registro_admin(info):
    print("\n== Registro de cliente admin ==")
    skt, buffer, resp = conectar_y_registrar(info["puertoTCP"], "ADMIN")
    ok = check("El servidor responde ADMIN_RESP a ADMIN",
               resp == "ADMIN_RESP", f"respuesta recibida: {resp!r}")
    if not ok:
        skt.close()
        return None, None
    return skt, buffer


def test_registro_clave_invalida(info):
    print("\n== Registro con clave incorrecta ==")
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    skt.settimeout(TIMEOUT)
    skt.connect((HOST, info["puertoTCP"]))
    skt.sendall(b"REGISTER claveMala\n")
    skt.settimeout(2)
    try:
        datos = skt.recv(256)
        cerro = (datos == b"")
    except socket.timeout:
        cerro = False
    check("El servidor cierra la conexion si la clave es incorrecta",
          cerro, "el servidor no cerro la conexion (o mando datos inesperados)")
    skt.close()


def test_metricas_y_alertas(skt_comun):
    print("\n== Envio de METRIC y ALERT desde cliente comun ==")
    try:
        skt_comun.sendall(b"METRIC CPU 42\n")
        skt_comun.sendall(b"METRIC MEM 33\n")
        skt_comun.sendall(b"ALERT CPU 95\n")
        check("El cliente comun puede enviar METRIC/ALERT sin excepciones", True)
    except Exception as e:
        check("El cliente comun puede enviar METRIC/ALERT sin excepciones", False, str(e))


def test_listar_agentes(skt_admin, buffer_admin, id_esperado):
    print("\n== LIST AGENTS ==")
    skt_admin.sendall(b"LIST AGENTS\n")
    linea, buffer_admin = recibir_linea(skt_admin, buffer_admin)
    texto = linea.decode('utf-8').strip() if linea else None
    ok = check("La respuesta a LIST AGENTS empieza con 'AGENTS'",
               texto is not None and texto.startswith("AGENTS"),
               f"respuesta recibida: {texto!r}")
    if ok:
        check(f"El cliente comun registrado (id {id_esperado}) aparece en la lista",
              str(id_esperado) in texto.split(),
              f"respuesta recibida: {texto!r}")
    return buffer_admin


def test_get_metric(skt_admin, buffer_admin, id_comun):
    print("\n== GET METRIC ==")
    skt_admin.sendall(f"GET METRIC {id_comun} CPU\n".encode('utf-8'))
    linea, buffer_admin = recibir_linea(skt_admin, buffer_admin)
    texto = linea.decode('utf-8').strip() if linea else None
    ok = check("La respuesta a GET METRIC empieza con 'MEASUREMENTS'",
               texto is not None and texto.startswith("MEASUREMENTS"),
               f"respuesta recibida: {texto!r}")
    if ok:
        check("El valor de CPU enviado antes (42) aparece en la respuesta",
              "42" in texto.split(), f"respuesta recibida: {texto!r}")
    return buffer_admin


def test_get_proc(skt_admin, buffer_admin, skt_comun, buffer_comun, id_comun):
    print("\n== GET PROC (coordinacion admin <-> comun) ==")
    resultado_hilo = {}

    def responder_get_proc():
        nonlocal buffer_comun
        linea, buffer_comun = recibir_linea(skt_comun, buffer_comun)
        if linea and linea.decode('utf-8').strip() == "GET_PROC":
            skt_comun.sendall(b"PROC 1234:python, 5678:bash, \n")
            resultado_hilo["ok"] = True
        else:
            resultado_hilo["ok"] = False

    hilo = threading.Thread(target=responder_get_proc, daemon=True)
    hilo.start()

    skt_admin.sendall(f"GET PROC {id_comun}\n".encode('utf-8'))
    linea, buffer_admin = recibir_linea(skt_admin, buffer_admin)
    hilo.join(timeout=TIMEOUT)

    texto = linea.decode('utf-8').strip() if linea else None
    check("El cliente comun recibio el pedido GET_PROC del servidor",
          resultado_hilo.get("ok") is True)
    ok = check("La respuesta a GET PROC empieza con 'PROC'",
               texto is not None and texto.startswith("PROC"),
               f"respuesta recibida: {texto!r}")
    if ok:
        check("La lista de procesos llega completa en la respuesta",
              "1234:python" in texto, f"respuesta recibida: {texto!r}")
    return buffer_admin


def test_comando_invalido(skt_admin, buffer_admin):
    print("\n== Comando no reconocido ==")
    skt_admin.sendall(b"COMANDO_INEXISTENTE\n")
    linea, buffer_admin = recibir_linea(skt_admin, buffer_admin)
    texto = linea.decode('utf-8').strip() if linea else None
    check("El servidor responde 'ERROR' ante un comando invalido",
          texto == "ERROR", f"respuesta recibida: {texto!r}")
    return buffer_admin


def test_cierre(skt, nombre):
    print(f"\n== Cierre de conexion ({nombre}) ==")
    try:
        skt.sendall(b"END\n")
        skt.settimeout(3)
        datos = skt.recv(256)
        cerro = (datos == b"")
    except (socket.timeout, ConnectionError, OSError):
        cerro = False
    check(f"El servidor cierra la conexion del {nombre} tras END",
          cerro, "no se detecto cierre ordenado")
    skt.close()


def main():
    print("Iniciando servidor_labo en un hilo de fondo...")
    hilo_servidor = threading.Thread(target=servidor.server_main, daemon=True)
    hilo_servidor.start()
    time.sleep(0.5)

    info = test_discovery()
    if info is None:
        print("\nNo se pudo continuar: el servidor no respondio al discovery.")
        resumen()
        return

    info_clave = descubrir_servidor()
    if info_clave:
        test_registro_clave_invalida(info_clave)
    else:
        check("Discovery para prueba de clave invalida", False)

    info_comun = descubrir_servidor()
    skt_comun, buffer_comun = (test_registro_comun(info_comun) if info_comun
                                else (None, None))

    info_admin = descubrir_servidor()
    skt_admin, buffer_admin = (test_registro_admin(info_admin) if info_admin
                                else (None, None))

    if skt_comun and skt_admin:
        id_comun = 0  # primer y unico cliente comun de esta corrida

        test_metricas_y_alertas(skt_comun)
        time.sleep(0.5)  # dar tiempo a que el servidor procese las METRIC

        buffer_admin = test_listar_agentes(skt_admin, buffer_admin, id_comun)
        buffer_admin = test_get_metric(skt_admin, buffer_admin, id_comun)
        buffer_admin = test_get_proc(skt_admin, buffer_admin, skt_comun, buffer_comun, id_comun)
        buffer_admin = test_comando_invalido(skt_admin, buffer_admin)

        test_cierre(skt_admin, "cliente admin")
        test_cierre(skt_comun, "cliente comun")
    else:
        if skt_comun:
            skt_comun.close()
        if skt_admin:
            skt_admin.close()

    resumen()


def resumen():
    exitosos = sum(1 for _, ok in resultados if ok)
    total = len(resultados)
    print(f"\n{'='*50}")
    print(f"Resultado: {exitosos}/{total} pruebas pasaron")
    if exitosos < total:
        print("Pruebas que fallaron:")
        for nombre, ok in resultados:
            if not ok:
                print(f"  - {nombre}")
    print(f"{'='*50}")
    sys.exit(0 if exitosos == total else 1)


if __name__ == "__main__":
    main()
