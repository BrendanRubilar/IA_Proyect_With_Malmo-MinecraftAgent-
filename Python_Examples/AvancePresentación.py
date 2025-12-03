import random
import sys
import time
import threading
import os
import MalmoPython
from collections import deque
import tkinter as tk 

print("Script de Agentes Multi-Laberinto con GUI 2D (PID=%d)" % os.getpid())

# ======================================================================
# CONFIGURACIÓN
# ======================================================================
SIZE = 21 
Y_LEVEL = 228
WALL_HEIGHT = Y_LEVEL + 1 
START_X, START_Z = 1, 1
END_X, END_Z = SIZE - 2, SIZE - 2

CLIENT_PORTS = [10000, 10001]
START_RETRY_TIMEOUT = 60.0 
START_RETRY_INTERVAL = 1.5

# Diccionario compartido para la posición actual de los agentes (Thread-safe logic)
CURRENT_POSITIONS = {
    "AgentA": (START_X, START_Z),
    "AgentB": (END_X, END_Z)
}

# ======================================================================
# CLASE PARA LA INTERFAZ GRÁFICA (VISUALIZADOR)
# ======================================================================
class MazeVisualizer:
    def __init__(self, root, matrix, cell_size=30):
        self.root = root
        self.matrix = matrix
        self.cell_size = cell_size
        self.rows = len(matrix)
        self.cols = len(matrix[0])
        
        # Configurar ventana
        self.root.title("Malmo Maze View")
        canvas_width = self.cols * cell_size
        canvas_height = self.rows * cell_size
        self.canvas = tk.Canvas(root, width=canvas_width, height=canvas_height, bg="black")
        self.canvas.pack()

        # Dibujar Laberinto Estático
        self.draw_maze()
        
        # Crear los iconos de los agentes
        # Agent A (Start) = Cyan
        self.agent_a_id = self.canvas.create_oval(0,0,0,0, fill="#00FFFF", outline="white", width=2)
        # Agent B (End) = Orange
        self.agent_b_id = self.canvas.create_oval(0,0,0,0, fill="#FFA500", outline="white", width=2)
        
        # Iniciar bucle de actualización
        self.update_positions()

    def draw_maze(self):
        s = self.cell_size
        for z in range(self.rows):
            for x in range(self.cols):
                # 0 es camino (blanco), 1 es pared (gris oscuro)
                color = "#FFFFFF" if self.matrix[z][x] == 0 else "#202020"
                
                # Resaltar inicio y fin
                if x == START_X and z == START_Z: color = "#00FF00" # Verde Inicio
                if x == END_X and z == END_Z: color = "#FF0000"     # Rojo Fin
                
                self.canvas.create_rectangle(x*s, z*s, (x+1)*s, (z+1)*s, fill=color, outline="")

    def update_positions(self):
        # Leer posiciones globales
        pos_a = CURRENT_POSITIONS.get("AgentA", (START_X, START_Z))
        pos_b = CURRENT_POSITIONS.get("AgentB", (END_X, END_Z))
        
        # Mover Agente A
        self.move_circle(self.agent_a_id, pos_a[0], pos_a[1])
        # Mover Agente B
        self.move_circle(self.agent_b_id, pos_b[0], pos_b[1])
        
        # Volver a llamar a esta función en 50ms (Polling)
        self.root.after(50, self.update_positions)

    def move_circle(self, item_id, grid_x, grid_z):
        s = self.cell_size
        padding = 4
        x1 = grid_x * s + padding
        y1 = grid_z * s + padding
        x2 = (grid_x + 1) * s - padding
        y2 = (grid_z + 1) * s - padding
        self.canvas.coords(item_id, x1, y1, x2, y2)

# ======================================================================
# 1. ALGORITMOS DE BÚSQUEDA
# ======================================================================

def generar_laberinto_dfs(size):
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

def busqueda_bidireccional(grid, start, end):
    if start == end: return [start]
    q_start = deque([start])
    q_end = deque([end])
    visitado_start = {start: None}
    visitado_end = {end: None}
    
    while q_start and q_end:
        # Expansión Start
        curr_s = q_start.popleft()
        if curr_s in visitado_end: return reconstruir_camino(visitado_start, visitado_end, curr_s)
        for v in obtener_vecinos(grid, curr_s):
            if v not in visitado_start:
                visitado_start[v] = curr_s
                q_start.append(v)
        # Expansión End
        curr_e = q_end.popleft()
        if curr_e in visitado_start: return reconstruir_camino(visitado_start, visitado_end, curr_e)
        for v in obtener_vecinos(grid, curr_e):
            if v not in visitado_end:
                visitado_end[v] = curr_e
                q_end.append(v)
    return [] 

def obtener_vecinos(grid, node):
    x, z = node
    vecinos = []
    moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    for dx, dz in moves:
        nx, nz = x + dx, z + dz
        if 0 <= nx < len(grid) and 0 <= nz < len(grid) and grid[nz][nx] == 0:
            vecinos.append((nx, nz))
    return vecinos

def reconstruir_camino(padres_s, padres_e, encuentro):
    camino_s = []
    curr = encuentro
    while curr is not None:
        camino_s.append(curr)
        curr = padres_s[curr]
    camino_s.reverse()
    camino_e = []
    curr = padres_e[encuentro]
    while curr is not None:
        camino_e.append(curr)
        curr = padres_e[curr]
    return camino_s + camino_e

def generar_acciones_con_coords(path, start_yaw):
    """
    Retorna una lista de tuplas: (comando_malmo, (x_objetivo, z_objetivo))
    Esto permite actualizar la GUI paso a paso.
    """
    if not path or len(path) < 2: return []

    acciones_y_coords = []
    current_yaw = start_yaw
    current_pos = path[0] # (x, z)
    
    for i in range(len(path) - 1):
        curr_x, curr_z = path[i]
        next_x, next_z = path[i+1]
        
        dx = next_x - curr_x
        dz = next_z - curr_z
        
        target_yaw = current_yaw
        if dz == 1:   target_yaw = 0   
        elif dz == -1: target_yaw = 180 
        elif dx == 1:  target_yaw = 270 
        elif dx == -1: target_yaw = 90  
        
        diff = (target_yaw - current_yaw) % 360
        
        # Giros (no cambian posición)
        if diff == 90:
            acciones_y_coords.append(("turn 1", current_pos)) 
        elif diff == 270:
            acciones_y_coords.append(("turn -1", current_pos)) 
        elif diff == 180:
            acciones_y_coords.append(("turn 1", current_pos))
            acciones_y_coords.append(("turn 1", current_pos))
            
        # Movimiento (cambia posición)
        acciones_y_coords.append(("move 1", (next_x, next_z)))
        current_pos = (next_x, next_z)
        current_yaw = target_yaw

    return acciones_y_coords

# ======================================================================
# 2. XML Y CONTROLADOR
# ======================================================================

def generar_xml_laberinto(laberinto):
    dibujo_xml = ""
    for z in range(SIZE):
        for x in range(SIZE):
            if laberinto[z][x] == 1:
                is_start = (START_X-1 <= x <= START_X+1 and START_Z-1 <= z <= START_Z+1)
                is_end = (END_X-1 <= x <= END_X+1 and END_Z-1 <= z <= END_Z+1)
                if not is_start and not is_end:
                    dibujo_xml += f'<DrawBlock x="{x}" y="{Y_LEVEL}" z="{z}" type="stonebrick"/>\n'
                    dibujo_xml += f'<DrawBlock x="{x}" y="{Y_LEVEL + 1}" z="{z}" type="stonebrick"/>\n'
    dibujo_xml += f'<DrawBlock x="{START_X}" y="{Y_LEVEL - 1}" z="{START_Z}" type="grass"/>\n'
    dibujo_xml += f'<DrawBlock x="{END_X}" y="{Y_LEVEL - 1}" z="{END_Z}" type="emerald_block"/>\n'
    return dibujo_xml

def get_mission_xml(dibujo_xml):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<Mission xmlns="http://ProjectMalmo.microsoft.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" forceWorldReset="true">
  <About><Summary>Bidireccional Maze</Summary></About>
  <ServerSection>
    <ServerInitialConditions><Time><StartTime>1</StartTime></Time></ServerInitialConditions>
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
    <AgentStart><Placement x="{START_X}.5" y="{Y_LEVEL}.0" z="{START_Z}.5" yaw="0"/></AgentStart>
    <AgentHandlers><DiscreteMovementCommands/></AgentHandlers>
  </AgentSection>
  <AgentSection mode="Survival">
    <Name>AgentB</Name>
    <AgentStart><Placement x="{END_X}.5" y="{Y_LEVEL}.0" z="{END_Z}.5" yaw="180"/></AgentStart>
    <AgentHandlers><DiscreteMovementCommands/></AgentHandlers>
  </AgentSection>
</Mission>'''

laberinto_matrix = generar_laberinto_dfs(SIZE)
xml_dibujo = generar_xml_laberinto(laberinto_matrix)
mission_spec = MalmoPython.MissionSpec(get_mission_xml(xml_dibujo), True)

def run_agent_moving(role, agent_name, experiment_id, client_pool, action_data):
    print(f"[{agent_name}] Iniciando...")
    agent_host = MalmoPython.AgentHost()
    mr = MalmoPython.MissionRecordSpec()

    try:
        start_deadline = time.time() + START_RETRY_TIMEOUT
        while True:
            try:
                agent_host.startMission(mission_spec, client_pool, mr, role, experiment_id)
                break
            except RuntimeError as e:
                if time.time() > start_deadline: raise e
                time.sleep(START_RETRY_INTERVAL)

        print(f"[{agent_name}] Esperando servidor...")
        world_state = agent_host.getWorldState()
        while not world_state.has_mission_begun:
            time.sleep(0.1)
            world_state = agent_host.getWorldState()

        print(f"[{agent_name}] GO! Ejecutando ruta...")
        time.sleep(1)

        # Iteramos sobre (comando, (x, z))
        for cmd, (nx, nz) in action_data:
            agent_host.sendCommand(cmd)
            
            # ACTUALIZAR GUI (Global Dictionary)
            CURRENT_POSITIONS[agent_name] = (nx, nz)
            
            if not agent_host.getWorldState().is_mission_running: break
            time.sleep(0.2) # Velocidad de movimiento

        print(f"[{agent_name}] Destino alcanzado. Terminando misión...")
        
        # --- CORRECCIÓN AQUÍ ---
        time.sleep(0.5) # Pequeña pausa para ver la posición final
        agent_host.sendCommand("quit") # Enviamos QUIT explícitamente al terminar la ruta
        # -----------------------

        # Ahora sí podemos esperar a que el servidor cierre la sesión
        while world_state.is_mission_running:
            time.sleep(0.5)
            world_state = agent_host.getWorldState()

    except Exception as e:
        print(f"[{agent_name}] Error: {e}")
    
    # El finally queda solo como seguridad por si el programa crashea antes
    finally:
        pass

def main():
    print("--- Calculando ruta bidireccional ---")
    ruta_completa = busqueda_bidireccional(laberinto_matrix, (START_X, START_Z), (END_X, END_Z))
    
    if not ruta_completa:
        print("No hay camino.")
        return

    mid_index = len(ruta_completa) // 2
    path_a = ruta_completa[:mid_index + 1]
    path_b = ruta_completa[mid_index:][::-1] 

    # Generamos acciones Y coordenadas esperadas
    cmds_a = generar_acciones_con_coords(path_a, start_yaw=0)
    cmds_b = generar_acciones_con_coords(path_b, start_yaw=180)

    shared_mission_id = f"mision_vis_{int(time.time())}"
    client_pool = MalmoPython.ClientPool()
    for p in CLIENT_PORTS:
        client_pool.add(MalmoPython.ClientInfo("127.0.0.1", p))

    # Lanzar hilos de Malmo
    tA = threading.Thread(target=run_agent_moving, args=(0, "AgentA", shared_mission_id, client_pool, cmds_a))
    tB = threading.Thread(target=run_agent_moving, args=(1, "AgentB", shared_mission_id, client_pool, cmds_b))
    
    tA.start()
    time.sleep(1)
    tB.start()

    # --- INICIAR GUI EN EL HILO PRINCIPAL ---
    # Esto bloqueará 'main' hasta que cierres la ventana, pero los hilos seguirán corriendo
    print("Iniciando Ventana Gráfica (Cierra la ventana para terminar el script)...")
    root = tk.Tk()
    app = MazeVisualizer(root, laberinto_matrix, cell_size=25)
    root.mainloop()
    
    # Al cerrar ventana:
    print("Cerrando...")
    tA.join()
    tB.join()
    print("Fin.")

if __name__ == "__main__":
    main()