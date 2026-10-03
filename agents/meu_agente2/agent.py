from google.adk import Agent
try:
    from agents.model_config import modelo
except ModuleNotFoundError:  # adk web: 'agents/' está no sys.path, não a raiz
    from model_config import modelo

root_agent = Agent(
    name="meu_agente2",
    instruction="""
        Escreva um código Python que imprima 'Olá, Mundo!' usando a função print().
        Certifique-se de que o código seja simples e fácil de entender.
    """,
    model=modelo(__file__),
)
