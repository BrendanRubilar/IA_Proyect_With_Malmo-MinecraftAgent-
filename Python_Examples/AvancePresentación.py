import random
import sys
import time
import threading
import socket
import os
import MalmoPython

print("Script de Agentes Multi-Laberinto arrancando (PID=%d)" % os.getpid())

# ======================================================================
# CONFIGURACIÓN Y LÓGICA DEL LABERINTO
# ======================================================================

# Configuración del laberinto (DEBE ser impar para el DFS)
SIZE = 21 
Y_LEVEL = 228 # Nivel Y donde se construye el suelo de movimiento (agente)

# Las paredes tendrán 2 bloques de alto (Y=228 y Y=229)
WALL_HEIGHT = Y_LEVEL + 1 
START_X, START_Z = 1, 1
END_X, END_Z = SIZE - 2, SIZE - 2

CLIENT_PORTS = [10000, 10001]
START_RETRY_TIMEOUT = 60.0  
START_RETRY_INTERVAL = 1.5

# ----------------------------------------------------------------------
# 1. ALGORITMO DE GENERACIÓN DE LABERINTOS CON DFS
# ----------------------------------------------------------------------

def generar_laberinto_dfs(size):
    """Crea un laberinto usando el algoritmo de Búsqueda en Profundidad (DFS)."""
    
    laberinto = [[1] * size for _ in range(size)]
    pila = [(START_X, START_Z)]
    laberinto[START_Z][START_X] = 0  
    direcciones = [(0, 2), (0, -2), (2, 0), (-2, 0)]

    while pila:
        cx, cz = pila[-1] 
        vecinos_no_visitados = []
        for dx, dz in direcciones:
            nx, nz = cx + dx, cz + dz 
            if 1 <= nx < size - 1 and 1 <= nz < size - 1 and laberinto[nz][nx] == 1:
                vecinos_no_visitados.append((nx, nz, dx, dz))
        if vecinos_no_visitados:
            nx, nz, dx, dz = random.choice(vecinos_no_visitados)
            laberinto[nz][nx] = 0
            laberinto[cz + dz // 2][cx + dx // 2] = 0
            pila.append((nx, nz))
        else:
            pila.pop()
            
    return laberinto

# ----------------------------------------------------------------------
# 2. CONSTRUCCIÓN DEL XML
# ----------------------------------------------------------------------
def generar_xml_laberinto(laberinto):
    """Convierte la matriz del laberinto en comandos DrawBlock XML.
    Dibuja paredes del laberinto, pilares en inicio/meta solo en periferia,
    y añade muros en 'L' adaptativos (altura 3, base Y = Y_LEVEL - 1) alrededor
    de START y END cuando estén en esquinas/perímetro."""
    dibujo_xml = ""
    for z in range(SIZE):
        for x in range(SIZE):
            is_start_area = (START_X - 1 <= x <= START_X + 1) and (START_Z - 1 <= z <= START_Z + 1)
            is_end_area = (END_X - 1 <= x <= END_X + 1) and (END_Z - 1 <= z <= END_Z + 1)
            if laberinto[z][x] == 1 and not is_start_area and not is_end_area:
                dibujo_xml += f'<DrawBlock x="{x}" y="{Y_LEVEL}" z="{z}" type="stonebrick"/>\n'
                dibujo_xml += f'<DrawBlock x="{x}" y="{Y_LEVEL + 1}" z="{z}" type="stonebrick"/>\n'

    # CELDAS DE INICIO Y META (SOLO PILARES EN EL BORDE)
    for coord_x, coord_z, block_type in [(START_X, START_Z, "grass"), (END_X, END_Z, "emerald_block")]:
        # 1. Limpia el área alrededor del spawn/meta
        dibujo_xml += f'<DrawCuboid x1="{coord_x - 1}" y1="{Y_LEVEL}" z1="{coord_z - 1}" x2="{coord_x + 1}" y2="{WALL_HEIGHT}" z2="{coord_z + 1}" type="air"/>\n'

        # 2. Dibuja los PILARES (solo si quedan en la periferia del mapa)
        for y in [Y_LEVEL, Y_LEVEL + 1]:
            for dx, dz in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
                tx = coord_x + dx
                tz = coord_z + dz
                # Sólo colocar pilares si están en el borde exterior del mundo para no romper el laberinto interno
                if tx == 0 or tx == SIZE - 1 or tz == 0 or tz == SIZE - 1:
                    dibujo_xml += f'<DrawBlock x="{tx}" y="{y}" z="{tz}" type="stonebrick"/>\n'

        # 3. Suelo de meta/inicio (un bloque distintivo debajo del agente)
        dibujo_xml += f'<DrawBlock x="{coord_x}" y="{Y_LEVEL - 1}" z="{coord_z}" type="{block_type}"/>\n'

    wall_base_y = Y_LEVEL - 1
    wall_height = 3
    ext = 2

    def _add_l_wall(anchor_x, anchor_z):
        s = ""
        # decidir dirección fuera del laberinto: -1 = negativo, +1 = positivo, 0 = no esquina
        x_dir = -1 if anchor_x <= ext else (1 if anchor_x >= SIZE - 1 - ext else 0)
        z_dir = -1 if anchor_z <= ext else (1 if anchor_z >= SIZE - 1 - ext else 0)
        if x_dir == 0 and z_dir == 0:
            return s  # no estamos en una esquina/perímetro significativa

        # horizontal: a lo largo del eje X, colocado fuera en Z
        horizontal_z = anchor_z + z_dir * ext
        for x in range(anchor_x - ext, anchor_x + ext + 1):
            for y in range(wall_base_y, wall_base_y + wall_height):
                s += f'<DrawBlock x="{x}" y="{y}" z="{horizontal_z}" type="stonebrick"/>\n'

        # vertical: a lo largo del eje Z, colocado fuera en X
        vertical_x = anchor_x + x_dir * ext
        for z in range(anchor_z - ext, anchor_z + ext + 1):
            for y in range(wall_base_y, wall_base_y + wall_height):
                s += f'<DrawBlock x="{vertical_x}" y="{y}" z="{z}" type="stonebrick"/>\n'

        return s

    # Añadir muros adaptativos en START y END
    dibujo_xml += _add_l_wall(START_X, START_Z)
    dibujo_xml += _add_l_wall(END_X, END_Z)

    return dibujo_xml

def get_mission_xml(dibujo_xml):
    """
    Devuelve el XML completo de la misión.
    """
    
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<Mission xmlns="http://ProjectMalmo.microsoft.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" forceWorldReset="true">

  <About>
    <Summary>Multi-Agente en Laberinto Aleatorio (Modo Sandbox)</Summary>
  </About>

  <ServerSection>
    <ServerInitialConditions>
      <Time><StartTime>1</StartTime></Time>
    </ServerInitialConditions>
    <ServerHandlers>
      <FlatWorldGenerator generatorString="3;7,220*1,5*3,2;3;,biome_1" />

      <DrawingDecorator>
        <DrawCuboid x1="0" y1="{Y_LEVEL-1}" z1="0" x2="{SIZE - 1}" y2="{Y_LEVEL-1}" z2="{SIZE - 1}" type="sandstone"/>
        <DrawCuboid x1="0" y1="{Y_LEVEL}" z1="0" x2="{SIZE - 1}" y2="{WALL_HEIGHT}" z2="{SIZE - 1}" type="air"/>

        {dibujo_xml}

      </DrawingDecorator>

      </ServerHandlers>
  </ServerSection>

  <AgentSection mode="Survival">
    <Name>AgentA</Name>
    <AgentStart>
      <Placement x="{START_X}.5" y="{Y_LEVEL}.0" z="{START_Z}.5" yaw="0"/>
    </AgentStart>
    <AgentHandlers>
      <DiscreteMovementCommands/>
      <ObservationFromFullStats/>
      </AgentHandlers>
  </AgentSection>

  <AgentSection mode="Survival">
    <Name>AgentB</Name>
    <AgentStart>
      <Placement x="{END_X}.5" y="{Y_LEVEL}.0" z="{END_Z}.5" yaw="180"/>
    </AgentStart>
    <AgentHandlers>
      <DiscreteMovementCommands/>
      <ObservationFromFullStats/>
      </AgentHandlers>
  </AgentSection>

</Mission>'''

# Generación dinámica del XML de la misión
laberinto_matrix = generar_laberinto_dfs(SIZE)
xml_dibujo = generar_xml_laberinto(laberinto_matrix)
mission_xml = get_mission_xml(xml_dibujo)

try:
    mission_spec = MalmoPython.MissionSpec(mission_xml, True)
except RuntimeError as e:
    print("❌ Error al parsear XML generado:", e)
    sys.exit(1)

# ======================================================================
# CONTROLADOR MULTI-AGENTE
# ======================================================================

def tcp_open(host, port, timeout=0.5):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def run_agent_idle(role, agent_name, experiment_id, client_pool):
    print(f"[{agent_name}] hilo (role={role}) iniciado")
    agent_host = MalmoPython.AgentHost()
    
    mr = MalmoPython.MissionRecordSpec()

    # NO crear pool local aquí; usar el client_pool compartido pasado como argumento.
    pool = client_pool

    start_deadline = time.time() + START_RETRY_TIMEOUT
    while True:
        try:
            print(f"[{agent_name}] llamando startMission (role={role}, mission_id='{experiment_id}')...")
            
            agent_host.startMission(mission_spec, pool, mr, role, experiment_id)
            
            print(f"[{agent_name}] startMission retornó OK.")
            break
        except RuntimeError as e:
            print(f"[{agent_name}] startMission fallo: {e}")
            if time.time() > start_deadline:
                print(f"[{agent_name}] agotado tiempo de reintentos para startMission.")
                return
            time.sleep(START_RETRY_INTERVAL)

    # Esperar que la misión realmente comience y luego que termine.
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
            print(f"→ Asegurate de lanzar launchClient.bat -port {p} en ese puerto antes de ejecutar este script.")

    # Crear un ID de misión ÚNICO pero COMPARTIDO
    SHARED_MISSION_ID = f"mision_compartida_{int(time.time())}"

    # CREAR pool COMPARTIDO y añadir los ClientInfo
    shared_pool = MalmoPython.ClientPool()
    for p in CLIENT_PORTS:
        shared_pool.add(MalmoPython.ClientInfo("127.0.0.1", p))

    # Preparar ambos hilos (pasando shared_pool)
    tA = threading.Thread(target=run_agent_idle, args=(0, "AgentA", SHARED_MISSION_ID, shared_pool), daemon=True)
    tB = threading.Thread(target=run_agent_idle, args=(1, "AgentB", SHARED_MISSION_ID, shared_pool), daemon=True)

    print(f"Iniciando misión con ID: {SHARED_MISSION_ID}")
    
    print("Lanzando AgentA (role 0)...")
    tA.start()

    # Aumentamos la espera para dar tiempo a que el servidor de Minecraft se cree y reserve los recursos.
    print("Esperando 5 segundos para dar ventaja al servidor (A)...")
    time.sleep(5.0) 

    print("Lanzando AgentB (role 1)...")
    tB.start()
    
    # esperar ambos
    print("Ambos hilos lanzados. Esperando que terminen (join)...")
    tA.join()
    tB.join()
    print("Fin del script.")

if __name__ == "__main__":
    main()