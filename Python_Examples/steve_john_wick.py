# Steve John Wick: Agente de Combate Autónomo con Q-Learning

from __future__ import print_function
from future import standard_library
import MalmoPython
import json
import logging
import os
import random
import sys
import time
import math

import tkinter as tk

standard_library.install_aliases()

# --- Misión XML ---
def get_mission_xml(agent_name):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<Mission xmlns="http://ProjectMalmo.microsoft.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <About>
        <Summary>Steve John Wick - Agente de Combate</Summary>
    </About>

    <ServerSection>
        <ServerInitialConditions>
            <Time>
                <StartTime>18000</StartTime>
                <AllowPassageOfTime>false</AllowPassageOfTime>
            </Time>
            <Weather>clear</Weather>
        </ServerInitialConditions>
        <ServerHandlers>
            <FlatWorldGenerator generatorString="3;7,226*minecraft:sandstone;1;"/>
            <DrawingDecorator>
                <DrawCuboid x1="-11" y1="227" z1="-11" x2="11" y2="230" z2="-11" type="bedrock" />
                <DrawCuboid x1="-11" y1="227" z1="11"  x2="11" y2="230" z2="11"  type="bedrock" />
                <DrawCuboid x1="-11" y1="227" z1="-10" x2="-11" y2="230" z2="10" type="bedrock" />
                <DrawCuboid x1="11"  y1="227" z1="-10" x2="11"  y2="230" z2="10" type="bedrock" />
                <DrawCuboid x1="-11" y1="231" z1="-11" x2="11" y2="231" z2="11" type="glowstone" />
                <DrawBlock x="0" y="230" z="0" type="redstone_block"/>
                <DrawBlock x="0" y="230" z="0" type="air"/>
                <DrawEntity x="0.5" y="227.0" z="5.5" type="Zombie" />
            </DrawingDecorator>
            <ServerQuitFromTimeUp timeLimitMs="30000"/>
            <ServerQuitWhenAnyAgentFinishes/>
        </ServerHandlers>
    </ServerSection>

    <AgentSection mode="Survival">
        <Name>{agent_name}</Name>
        <AgentStart>
            <Placement x="0.5" y="227.0" z="0.5" yaw="0"/>
            <Inventory>
                <InventoryItem slot="0" type="diamond_sword"/>
            </Inventory>
        </AgentStart>
        <AgentHandlers>
            <ObservationFromFullStats/>
            <ObservationFromNearbyEntities>
                <Range name="entities" xrange="40" yrange="2" zrange="40" />
            </ObservationFromNearbyEntities>
            <ContinuousMovementCommands turnSpeedDegs="180"/>
            <InventoryCommands/>
            <RewardForDamagingEntity>
                <Mob type="Zombie" reward="10"/>
            </RewardForDamagingEntity>
            <RewardForMissionEnd>
                <Reward description="victory" reward="100"/>
            </RewardForMissionEnd>

        </AgentHandlers>
    </AgentSection>
</Mission>'''


# CORRECCIÓN 2: Clase para manejar la ventana de visualización
class QVisualizer:
    def __init__(self, title="Q-Values"):
        self.root = None
        self.canvas = None
        self.title = title

    def setup(self, actions):
        self.root = tk.Tk()
        self.root.wm_title(self.title)
        self.actions = actions
        canvas_width = 400
        canvas_height = 50 + len(actions) * 40
        self.canvas = tk.Canvas(self.root, width=canvas_width, height=canvas_height, borderwidth=0, highlightthickness=0, bg="black")
        self.canvas.pack()
        self.root.update()

    def update(self, q_values, current_state, chosen_action_idx):
        if self.root is None:
            self.setup(self.actions)

        self.canvas.delete("all")
        
        # Dibuja el estado actual
        self.canvas.create_text(200, 20, text=f"State: {current_state}", fill="white", font=("Helvetica", 12))

        bar_width = 300
        max_q = max(q_values) if any(q != 0 for q in q_values) else 1.0
        min_q = min(q_values) if any(q != 0 for q in q_values) else -1.0

        for i, q in enumerate(q_values):
            y_pos = 50 + i * 40
            
            # Normalizar valor para el color y la longitud de la barra
            if q >= 0:
                color = '#%02x%02x%02x' % (0, int(255 * (q / max_q if max_q > 0 else 1)), 0) # Verde para positivo
                bar_len = q / max_q if max_q > 0 else 0
            else:
                color = '#%02x%02x%02x' % (int(255 * (q / min_q if min_q < 0 else 1)), 0, 0) # Rojo para negativo
                bar_len = -q / min_q if min_q < 0 else 0

            # Dibuja la barra
            self.canvas.create_rectangle(100, y_pos, 100 + bar_len * bar_width, y_pos + 20, fill=color)
            
            # Dibuja el texto
            action_text = self.actions[i]
            marker = "  <-- CHOSEN" if i == chosen_action_idx else ""
            self.canvas.create_text(10, y_pos + 10, text=f"{action_text}: {q:.2f}{marker}", anchor='w', fill="white")

        self.root.update()

class CombatAgent(object):
    def __init__(self, agent_host, actions, logger, visualizer):
        self.agent_host = agent_host
        self.actions = actions
        self.logger = logger
        self.visualizer = visualizer
        
        self.epsilon = 0.25
        self.alpha = 0.3
        self.gamma = 0.9

        self.prev_s = None
        self.prev_a = None
        self.was_facing_enemy = False
        
        self.angle_thresh = 15.0          # grados para considerar "mirando"
        self.facing_bonus = 0.2           # recompensa por tick mirando
        self.not_facing_penalty_max = 0.1 # penalización máxima por tick
        
    def get_state(self, world_state):
        if not world_state.observations: return None
        obs = json.loads(world_state.observations[-1].text)
        agent_health = obs.get('Life', 0)
        agent_yaw = obs.get('Yaw', 0)
        enemy_info = next((e for e in obs.get('entities', []) if e['name'] == 'Zombie'), None)
        if not enemy_info: return "enemy_dead"
        dx = enemy_info['x'] - obs['XPos']
        dz = enemy_info['z'] - obs['ZPos']
        enemy_yaw = -180 * math.atan2(dx, dz) / math.pi
        yaw_diff = enemy_yaw - agent_yaw
        while yaw_diff < -180: yaw_diff += 360
        while yaw_diff > 180: yaw_diff -= 360
        dist = enemy_info.get('distance', 100)
        health_bin = int(agent_health / 5)
        dist_bin = int(dist / 3)
        yaw_bin = int(yaw_diff / 45) 
        state_str = f"h:{health_bin}_d:{dist_bin}_y:{yaw_bin}"
        self.logger.debug(f"STATE: {state_str}")
        return state_str
    
    def _q_values_for_state(self, q_table, state):
        return [q_table.get((state, a_idx), 0.0) for a_idx in range(len(self.actions))]

    def update_q_table(self, q_table, reward, current_state):
        if self.prev_s is None or self.prev_a is None:
            return
        old_q = q_table.get((self.prev_s, self.prev_a), 0.0)
        next_max_q = 0.0
        if current_state != "terminal":
            q_next = self._q_values_for_state(q_table, current_state)
            next_max_q = max(q_next) if q_next else 0.0
        new_q = old_q + self.alpha * (reward + self.gamma * next_max_q - old_q)
        q_table[(self.prev_s, self.prev_a)] = new_q
        self.logger.debug(f"Q_UPDATE: s={self.prev_s}, a={self.actions[self.prev_a]}, r={reward:.2f}, old_q={old_q:.4f} -> new_q={new_q:.4f}")

    def choose_action(self, q_table, current_s):
        q_vals = self._q_values_for_state(q_table, current_s)

        is_random = random.random() < self.epsilon
        if is_random:
            action_idx = random.randint(0, len(self.actions) - 1)
        else:
            max_q = max(q_vals) if q_vals else 0.0
            action_idx = q_vals.index(max_q)

        self.visualizer.update(q_vals, current_s, action_idx)
        self.logger.info(f"Q-VALUES for state '{current_s}':")
        for i, val in enumerate(q_vals):
            marker = ""
            if i == action_idx:
                action_type = "(RANDOM)" if is_random else "(OPTIMAL)"
                marker = f"  <-- CHOSEN {action_type}"
            self.logger.info(f"  - {self.actions[i]:<10}: {val:>8.4f}{marker}")

        return action_idx

    def act(self, q_table, world_state, current_r):
        current_s = self.get_state(world_state)
        if current_s is None:
            return 0
        self.update_q_table(q_table, current_r, current_s)
        if current_s == "enemy_dead":
            self.logger.info("ENEMY DEAD. Ending mission.")
            self.agent_host.sendCommand("quit")
            return current_r

        action_idx = self.choose_action(q_table, current_s)
        action_cmd = self.actions[action_idx]

        if "turn" not in action_cmd:
            self.agent_host.sendCommand("turn 0")
        if "move" not in action_cmd:
            self.agent_host.sendCommand("move 0")
        if "attack" not in action_cmd:
            self.agent_host.sendCommand("attack 0")

        self.agent_host.sendCommand(action_cmd)
        if action_cmd == "attack 1":
            time.sleep(0.1)
            self.agent_host.sendCommand("attack 0")

        self.prev_s = current_s
        self.prev_a = action_idx
        return current_r

    def run_episode(self, q_table):
        total_reward = 0
        world_state = self.agent_host.getWorldState()
        while world_state.is_mission_running:
            current_r = 0
            world_state = self.agent_host.getWorldState()

            xml_rewards = sum(r.getValue() for r in world_state.rewards)
            if xml_rewards != 0:
                self.logger.info(f"REWARD: Received {xml_rewards} from XML.")
                current_r += xml_rewards

            # Penalización por ataque fallido
            if self.prev_a is not None and self.actions[self.prev_a] == "attack 1" and xml_rewards == 0:
                penalty = -1
                self.logger.info(f"PENALTY: {penalty} for missed attack.")
                current_r += penalty

            if world_state.number_of_observations_since_last_state > 0 and len(world_state.observations) > 0:
                obs = json.loads(world_state.observations[-1].text)

                enemy_info = next((e for e in obs.get('entities', []) if e['name'] == 'Zombie'), None)
                if enemy_info:
                    dx, dz = enemy_info['x'] - obs['XPos'], enemy_info['z'] - obs['ZPos']
                    enemy_yaw = -180 * math.atan2(dx, dz) / math.pi
                    agent_yaw = obs.get('Yaw', 0)
                    yaw_diff = enemy_yaw - agent_yaw
                    while yaw_diff < -180: yaw_diff += 360
                    while yaw_diff > 180: yaw_diff -= 360
                    abs_yaw = abs(yaw_diff)

                    is_facing_now = abs_yaw < self.angle_thresh
                    if is_facing_now:
                        current_r += self.facing_bonus
                        self.logger.info(f"SHAPING: +{self.facing_bonus:.2f} facing enemy (|yaw|={abs_yaw:.1f}°).")
                    else:
                        frac = min(abs_yaw / 180.0, 1.0)
                        penalty = - self.not_facing_penalty_max * frac
                        current_r += penalty
                        self.logger.info(f"SHAPING: {penalty:.2f} not facing (|yaw|={abs_yaw:.1f}°).")

                    self.was_facing_enemy = is_facing_now
                else:
                    self.was_facing_enemy = False

                total_reward += self.act(q_table, world_state, current_r)

            time.sleep(0.1)

        self.logger.info("MISSION ENDED. Final state processing.")
        final_reward = sum(r.getValue() for r in world_state.rewards)
        if final_reward != 0:
            self.logger.info(f"REWARD: Final mission reward: {final_reward}")
        self.update_q_table(q_table, final_reward, "terminal")
        return total_reward

def main():
    agent_host = MalmoPython.AgentHost()
    try:
        agent_host.parse(sys.argv)
    except RuntimeError as e:
        print('ERROR:', e); print(agent_host.getUsage()); exit(1)

    NUM_EPISODES = 10
    q_table = {}
    actions = ["attack 1", "move 1", "turn 1", "turn -1"]

    logger = logging.getLogger(__name__)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)

    visualizer = QVisualizer()
    visualizer.setup(actions)

    for i in range(NUM_EPISODES):
        print(f"\n--- EPISODIO {i+1}/{NUM_EPISODES} ---")
        mission_xml = get_mission_xml("SteveJohnWick")
        my_mission = MalmoPython.MissionSpec(mission_xml, True)
        
        max_retries = 3
        for retry in range(max_retries):
            try:
                agent_host.startMission(my_mission, MalmoPython.MissionRecordSpec())
                break
            except RuntimeError as e:
                if retry == max_retries - 1: print("Error starting mission:", e); exit(1)
                else: time.sleep(2.5)

        print("Waiting for the mission to start", end=' ')
        world_state = agent_host.getWorldState()
        while not world_state.has_mission_begun:
            print(".", end=""); time.sleep(0.1); world_state = agent_host.getWorldState()
            for error in world_state.errors: print("Error:", error.text)
        print("\nMission started!")

        combat_agent = CombatAgent(agent_host, actions, logger, visualizer)
        
        cumulative_reward = combat_agent.run_episode(q_table)
        print(f'Recompensa acumulada del episodio {i+1}: {cumulative_reward}')
        
        time.sleep(1)

    print("\n--- ENTRENAMIENTO FINALIZADO ---")

if __name__ == '__main__':
    main()