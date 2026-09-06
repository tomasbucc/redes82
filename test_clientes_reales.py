import subprocess
import sys
import os
import time
import threading
import queue

DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

resultados = []
PROMPT = "Conectado al Servidor: "


def check(nombre, condicion, detalle=""):
    estado = "OK" if condicion else "FALLO"
    resultados.append((nombre, condicion))
    linea = f"[{estado}] {nombre}"
    if detalle and not condicion:
        linea += f" -- {detalle}"
    print(linea)
    return condicion


def lanzar(script, stdin_pipe=False):
    return subprocess.Popen(
        [PYTHON, "-u", os.path.join(DIR, script)],
        stdin=subprocess.PIPE if stdin_pipe else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=DIR,
    )


def iniciar_lector(stream):
    q = queue.Queue()

    def _leer():
        for linea in iter(stream.readline, ''):
            q.put(linea)
        q.put(None)

    threading.Thread(target=_leer, daemon=True).start()
    return q


def leer_linea(q, timeout=10):
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return None


def drenar_no_bloqueante(q):
    lineas = []
    while True:
        try:
            l = q.get_nowait()
            if l is None:
                break
            lineas.append(l)
        except queue.Empty:
            break
    return lineas


def enviar_comando_admin(proc, q, comando, timeout=10):
    proc.stdin.write(comando + "\n")
    proc.stdin.flush()
    linea = leer_linea(q, timeout)
    if linea is None:
        return None
    return linea.replace(PROMPT, "").strip()


def main():
    print("Lanzando servidor_labo.py, cliente_comun.py y cliente_admin.py como procesos reales...\n")

    proc_server = lanzar("servidor_labo.py")
    q_server = iniciar_lector(proc_server.stdout)
    time.sleep(1)

    proc_comun = lanzar("cliente_comun.py")
    q_comun = iniciar_lector(proc_comun.stdout)

    proc_admin = lanzar("cliente_admin.py", stdin_pipe=True)
    q_admin = iniciar_lector(proc_admin.stdout)

    print("Esperando a que ambos clientes descubran el servidor y se registren...")
    time.sleep(2)

    errores_comun = [l for l in drenar_no_bloqueante(q_comun) if "Error" in l]
    check("cliente_comun.py arranco sin errores de conexion",
          len(errores_comun) == 0, f"salida: {errores_comun}")

    lineas_admin_iniciales = drenar_no_bloqueante(q_admin)
    fallo_admin = any(("Error" in l or "fallido" in l) for l in lineas_admin_iniciales)
    check("cliente_admin.py se registro sin errores",
          not fallo_admin, f"salida: {lineas_admin_iniciales}")

    resp = enviar_comando_admin(proc_admin, q_admin, "LIST AGENTS")
    ok = check("LIST AGENTS responde con formato 'AGENTS ...'",
               resp is not None and resp.startswith("AGENTS"),
               f"respuesta: {resp!r}")

    id_comun = None
    if ok:
        partes = resp.split()
        if len(partes) >= 3:
            id_comun = partes[2]
        check("cliente_comun aparece registrado en LIST AGENTS",
              id_comun is not None, f"respuesta: {resp!r}")

    if id_comun is not None:
        resp = enviar_comando_admin(proc_admin, q_admin, f"GET PROC {id_comun}", timeout=10)
        check("GET PROC responde con formato 'PROC ...'",
              resp is not None and resp.startswith("PROC"),
              f"respuesta: {resp!r}")

    print("\nEsperando ~16s a que cliente_comun.py reporte metricas (ciclo de 5s x 3)...")
    time.sleep(16)

    if id_comun is not None:
        resp = enviar_comando_admin(proc_admin, q_admin, f"GET METRIC {id_comun} CPU", timeout=10)
        ok = check("GET METRIC responde con formato 'MEASUREMENTS ...'",
                   resp is not None and resp.startswith("MEASUREMENTS"),
                   f"respuesta: {resp!r}")
        if ok:
            partes = resp.split()
            check("La respuesta incluye al menos un valor de CPU reportado",
                  len(partes) >= 4 and partes[3].isdigit() and int(partes[3]) >= 1,
                  f"respuesta: {resp!r}")

    resp = enviar_comando_admin(proc_admin, q_admin, "COMANDO_INEXISTENTE")
    # cliente_admin.py traduce el "ERROR" del servidor a este texto amigable
    # (ver su propio case "ERROR": print("Hubo un error, repetir mensaje"))
    check("Comando invalido dispara el manejo de ERROR del cliente admin",
          resp == "Hubo un error, repetir mensaje", f"respuesta: {resp!r}")

    proc_admin.stdin.write("END\n")
    proc_admin.stdin.flush()
    time.sleep(1)
    check("cliente_admin.py termina tras END", proc_admin.poll() is not None,
          "el proceso admin sigue vivo despues de END")

    errores_comun_final = [l for l in drenar_no_bloqueante(q_comun) if "Error" in l]
    check("cliente_comun.py no reporto errores durante toda la prueba",
          len(errores_comun_final) == 0, f"salida: {errores_comun_final}")

    for p in (proc_admin, proc_comun, proc_server):
        if p.poll() is None:
            p.terminate()
    time.sleep(0.5)
    for p in (proc_admin, proc_comun, proc_server):
        if p.poll() is None:
            p.kill()

    print("\n--- Salida completa del servidor (debug) ---")
    for l in drenar_no_bloqueante(q_server):
        print("  [server]", l.rstrip())

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
