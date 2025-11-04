import os
import time
import threading
import socket
import sys
import MalmoPython

print("TEST.py arrancando (PID=%d)" % os.getpid())

MISSION_FILE = "./fckingMukso2.xml"
try:
    with open(MISSION_FILE, 'r', encoding='utf-8') as f:
        mission_xml = f.read()
except FileNotFoundError:
    print("❌ No se encontró el archivo de misión:", MISSION_FILE)
    sys.exit(1)

try:
    mission_spec = MalmoPython.MissionSpec(mission_xml, True)
except RuntimeError as e:
    print("❌ Error al parsear XML:", e)
    sys.exit(1)

CLIENT_PORTS = [10000, 10001]
START_RETRY_TIMEOUT = 30.0   # segundos para reintentos de startMission
START_RETRY_INTERVAL = 1.5

def tcp_open(host, port, timeout=0.5):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

# ----- MODIFICADO AQUÍ -----
# Añadimos 'experiment_id' como un parámetro separado
def run_agent_idle(role, agent_name, experiment_id, client_ports):
    print(f"[{agent_name}] hilo (role={role}) iniciado")
    agent_host = MalmoPython.AgentHost()
    mr = MalmoPython.MissionRecordSpec()
    pool = MalmoPython.ClientPool()
    for p in client_ports:
        pool.add(MalmoPython.ClientInfo("127.0.0.1", p))

    # Intentar startMission con reintentos
    start_deadline = time.time() + START_RETRY_TIMEOUT
    while True:
        try:
            # El 'agent_name' es solo para los logs
            print(f"[{agent_name}] llamando startMission (role={role}, mission_id='{experiment_id}')...")
            
            # ----- ESTE ES EL ARREGLO -----
            # Pasamos el 'experiment_id' COMPARTIDO, no el 'agent_name'
            agent_host.startMission(mission_spec, pool, mr, role, experiment_id)
            
            print(f"[{agent_name}] startMission retornó OK.")
            break
        except RuntimeError as e:
            # Este error 'Failed to find server' es NORMAL al principio para AgentB
            print(f"[{agent_name}] startMission fallo: {e}")
            if time.time() > start_deadline:
                print(f"[{agent_name}] agotado tiempo de reintentos para startMission.")
                return
            time.sleep(START_RETRY_INTERVAL)

    # Ahora nos quedamos quietos: esperar que la misión realmente comience y luego que termine.
    print(f"[{agent_name}] esperando has_mission_begun...")
    world_state = agent_host.getWorldState()
    begin_deadline = time.time() + 60.0
    while not world_state.has_mission_begun:
        if time.time() > begin_deadline:
            print(f"[{agent_name}] timeout esperando has_mission_begun. Estado: is_mission_running={world_state.is_mission_running}")
            break
        time.sleep(0.2)
        world_state = agent_host.getWorldState()

    if world_state.has_mission_begun:
        print(f"[{agent_name}] misión ha comenzado. Ahora quedo quieto hasta que termine.")
    else:
        print(f"[{agent_name}] no se detectó has_mission_begun; igualmente permanezco conectado si es posible.")

    # permanecer inactivo hasta fin de misión
    while world_state.is_mission_running:
        time.sleep(0.5)
        world_state = agent_host.getWorldState()

    print(f"[{agent_name}] misión finalizada (o desconectado).")

def main():
    # check puertos
    for p in CLIENT_PORTS:
        ok = tcp_open("127.0.0.1", p, timeout=0.5)
        print(f"[CHECK] puerto {p} reachable: {ok}")
        if not ok:
            print(f"→ Asegurate de lanzar launchClient.bat en ese puerto antes de ejecutar este script.")

    # ----- MODIFICADO AQUÍ -----
    # Crear un ID de misión ÚNICO pero COMPARTIDO
    SHARED_MISSION_ID = f"mision_compartida_{int(time.time())}"

    # Preparar ambos hilos
    tA = threading.Thread(target=run_agent_idle, args=(0, "AgentA", SHARED_MISSION_ID, CLIENT_PORTS), daemon=True)
    tB = threading.Thread(target=run_agent_idle, args=(1, "AgentB", SHARED_MISSION_ID, CLIENT_PORTS), daemon=True)

    print(f"Iniciando misión con ID: {SHARED_MISSION_ID}")
    
    print("Lanzando AgentA (role 0)...")
    tA.start()

    # Darle 1-2 segundos al role 0 para que hable con el cliente y empiece a crear el servidor
    print("Esperando 2 segundos para dar ventaja al servidor (A)...")
    time.sleep(2.0) 

    print("Lanzando AgentB (role 1)...")
    tB.start()
    
    # esperar ambos
    print("Ambos hilos lanzados. Esperando que terminen (join)...")
    tA.join()
    tB.join()
    print("Fin del script.")

if __name__ == "__main__":
    main()