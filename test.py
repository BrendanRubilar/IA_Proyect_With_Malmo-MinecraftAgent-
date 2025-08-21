import malmoenv
import gym

# Crear entorno estilo OpenAI Gym
env = malmoenv.make()

print("Intentando conectarse al cliente Malmo...")

obs = env.reset()  # aquí intenta conectarse al cliente Malmo
print("Conexión establecida, agente listo.")
print("Observación inicial:", obs)

# Solo hacemos un paso de prueba
action = env.action_space.sample()
obs, reward, done, info = env.step(action)
print("Acción aleatoria ejecutada:", action)
print("Nueva observación:", obs)
print("Recompensa:", reward)
