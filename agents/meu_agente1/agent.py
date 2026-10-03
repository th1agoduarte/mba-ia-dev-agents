from google.adk import Agent
try:
    from agents.model_config import modelo
except ModuleNotFoundError:  # adk web: 'agents/' está no sys.path, não a raiz
    from model_config import modelo

root_agent = Agent(name="meu_agente1", model=modelo(__file__))
