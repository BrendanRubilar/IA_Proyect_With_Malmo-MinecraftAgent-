import random

import sys

import time

from malmo import MalmoPython


# Configuración del laberinto (DEBE ser impar para el DFS)

SIZE = 21

Y_LEVEL = 228 # Nivel Y donde se construyen los bloques base (suelo del laberinto)


# Las paredes tendrán 2 bloques de alto (Y=228 y Y=229)

WALL_HEIGHT = Y_LEVEL + 1


# Posiciones de inicio y fin (en coordenadas de celda, DEBEN ser impares)

START_X, START_Z = 1, 1

END_X, END_Z = SIZE - 2, SIZE - 2


# ----------------------------------------------------------------------

# 1. ALGORITMO DE GENERACIÓN DE LABERINTOS CON DFS

# ----------------------------------------------------------------------


def generar_laberinto_dfs(size):

    """Crea un laberinto usando el algoritmo de Búsqueda en Profundidad (DFS)."""

   

    # Inicializa la cuadrícula: 1 = Pared, 0 = Pasillo

    laberinto = [[1] * size for _ in range(size)]

   

    # Pila para el DFS

    pila = [(START_X, START_Z)]

    laberinto[START_Z][START_X] = 0  # Marca la celda de inicio como pasillo

   

    # Vecinos (direcciones: (dx, dz))

    direcciones = [(0, 2), (0, -2), (2, 0), (-2, 0)]


    while pila:

        cx, cz = pila[-1] # Celda actual

       

        vecinos_no_visitados = []

        for dx, dz in direcciones:

            nx, nz = cx + dx, cz + dz # Vecino (a dos pasos)

           

            # Comprueba límites y si la celda vecina es una pared (no visitada)

            if 1 <= nx < size - 1 and 1 <= nz < size - 1 and laberinto[nz][nx] == 1:

                vecinos_no_visitados.append((nx, nz, dx, dz))

       

        if vecinos_no_visitados:

            # Elije un vecino al azar

            nx, nz, dx, dz = random.choice(vecinos_no_visitados)

           

            # Cava el pasaje (rompe la pared a medio camino)

            laberinto[nz][nx] = 0

            laberinto[cz + dz // 2][cx + dx // 2] = 0

           

            # Avanza: empuja la nueva celda a la pila

            pila.append((nx, nz))

        else:

            # Backtrack: es un callejón sin salida

            pila.pop()

           

    return laberinto


# ----------------------------------------------------------------------

# 2. CONSTRUCCIÓN DEL XML

# ----------------------------------------------------------------------


def generar_xml_laberinto(laberinto):

    """Convierte la matriz del laberinto en comandos DrawBlock XML y garantiza espacio de movimiento."""

   

    dibujo_xml = ""

   

    # 1. Dibuja las paredes (2 bloques de alto: Y_LEVEL y Y_LEVEL + 1)

    for z in range(SIZE):

        for x in range(SIZE):

            if laberinto[z][x] == 1:  # 1 es pared

                # Dibuja la pared de 2 bloques de alto

                dibujo_xml += f'<DrawBlock x="{x}" y="{Y_LEVEL}" z="{z}" type="stonebrick"/>\n'

                dibujo_xml += f'<DrawBlock x="{x}" y="{Y_LEVEL + 1}" z="{z}" type="stonebrick"/>\n'

   

    # 2. GARANTIZAR ESPACIO LIBRE EN SPAWN Y META

    # Limpia un cubo de 3x3 (X-1 a X+1, Z-1 a Z+1) en el área de movimiento (Y=228 a Y=229)

   

    # Limpieza de SPAWN

    dibujo_xml += f'<DrawCuboid x1="{START_X - 1}" y1="{Y_LEVEL}" z1="{START_Z - 1}" x2="{START_X + 1}" y2="{WALL_HEIGHT}" z2="{START_Z + 1}" type="air"/>\n'

    # Limpieza de META

    dibujo_xml += f'<DrawCuboid x1="{END_X - 1}" y1="{Y_LEVEL}" z1="{END_Z - 1}" x2="{END_X + 1}" y2="{WALL_HEIGHT}" z2="{END_Z + 1}" type="air"/>\n'

    
    # 3. Dibuja los bloques de INICIO y FIN (se dibujan en el suelo, Y=228, sobreescribiendo el aire)

    # Bloque de INICIO (suelo)

    dibujo_xml += f'<DrawBlock x="{START_X}" y="{Y_LEVEL-1}" z="{START_Z}" type="grass"/>\n'

    # Bloque de FIN (suelo)

    dibujo_xml += f'<DrawBlock x="{END_X}" y="{Y_LEVEL-1}" z="{END_Z}" type="emerald_block"/>\n'

   

    return dibujo_xml


# ----------------------------------------------------------------------

# 3. FUNCIÓN DE LA MISIÓN

# ----------------------------------------------------------------------


def get_mission_xml(dibujo_xml):

    """Devuelve el XML completo de la misión, inyectando los comandos de dibujo."""

   

    # CORRECCIÓN FINAL DE COMPATIBILIDAD: forceWorldReset debe estar en el tag <Mission>

    xml_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>

<Mission xmlns="http://ProjectMalmo.microsoft.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" forceWorldReset="true">


  <About>

    <Summary>Laberinto aleatorio con DFS.</Summary>

  </About>


  <ServerSection>

    <ServerInitialConditions>

      <Time><StartTime>1</StartTime></Time>

    </ServerInitialConditions>


    <ServerHandlers>

      <FlatWorldGenerator

        generatorString="3;7,220*1,5*3,2;3;,biome_1"

        />


      <DrawingDecorator>

        <DrawCuboid x1="0" y1="227" z1="0" x2="{SIZE - 1}" y2="227" z2="{SIZE - 1}" type="sandstone"/>

        <DrawCuboid x1="0" y1="228" z1="0" x2="{SIZE - 1}" y2="{WALL_HEIGHT}" z2="{SIZE - 1}" type="air"/>


        {dibujo_xml}


      </DrawingDecorator>


      <ServerQuitWhenAnyAgentFinishes/>

    </ServerHandlers>

  </ServerSection>


  <AgentSection mode="Survival">

    <Name>Agente_Explorador</Name>

    <AgentStart>

      <Placement x="{START_X}.5" y="{Y_LEVEL}.0" z="{START_Z}.5" yaw="0"/>

    </AgentStart>


    <AgentHandlers>

      <DiscreteMovementCommands/>

      <ObservationFromFullStats/>

      <RewardForTouchingBlockType>

        <Block reward="100.0" type="emerald_block" behaviour="onceOnly"/>

      </RewardForTouchingBlockType>

      <AgentQuitFromTouchingBlockType>

        <Block type="emerald_block"/>

      </AgentQuitFromTouchingBlockType>

    </AgentHandlers>

  </AgentSection>


</Mission>'''

    return xml_content


# ----------------------------------------------------------------------

# 4. BUCLE PRINCIPAL DE MALMO

# ----------------------------------------------------------------------


if __name__ == '__main__':

    # 1. Genera el laberinto con DFS

    laberinto_matrix = generar_laberinto_dfs(SIZE)

   

    # 2. Convierte la matriz a XML de dibujo

    xml_dibujo = generar_xml_laberinto(laberinto_matrix)

   

    # 3. Obtiene el XML completo de la misión

    mission_xml = get_mission_xml(xml_dibujo)

   

    # 4. Inicializa Malmo

    agent_host = MalmoPython.AgentHost()

    try:

        agent_host.parse(sys.argv)

    except RuntimeError as e:

        print('ERROR:', e)

        print(agent_host.getUsage())

        exit(1)

    if agent_host.receivedArgument("help"):

        print(agent_host.getUsage())

        exit(0)


    # 5. Envía la misión

    my_mission = MalmoPython.MissionSpec(mission_xml, True)

    my_mission_record = MalmoPython.MissionRecordSpec()


    try:

        # Usamos la firma simple de startMission, ya que el reinicio se maneja en el XML.

        agent_host.startMission(my_mission, my_mission_record)

    except RuntimeError as e:

        print("Error starting mission:", e)

        exit(1)


    # 6. Espera que la misión comience

    world_state = agent_host.getWorldState()

    sys.stdout.write("Esperando a que la misión comience.")

   

    # Espera hasta que la misión empiece

    while not world_state.is_mission_running:

        sys.stdout.write(".")

        time.sleep(0.1)

        world_state = agent_host.getWorldState()

       

    print("\nMisión en ejecución...")

   

    # 7. Bucle principal del agente (puedes añadir aquí tu lógica RL/IA)

    # Por ahora, solo esperamos que termine.

    while world_state.is_mission_running:

        time.sleep(0.1)

        world_state = agent_host.getWorldState()


    print("Misión terminada.") 