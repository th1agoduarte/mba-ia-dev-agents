"""2. Instrução e escolha de modelo — equivale a `agents/meu_agente2`.

Dois mapeamentos do ADK para cá:

- `instruction=` vira `system_prompt=`.
- `model=LiteLlm(model="anthropic/claude-sonnet-4-6")` não tem equivalente: o
  LangChain não precisa de uma ponte tipo LiteLLM porque cada provedor já tem seu
  pacote de integração. Trocar de provedor é trocar a string `"provider:modelo"`
  (e instalar o pacote correspondente).

Duas formas de declarar o modelo:

1. String `"provider:modelo"` — resolvida por `init_chat_model`. Simples.
2. Objeto de chat model — quando você precisa de parâmetros (temperature etc.).
"""

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from exemplos_langchain.acme.config import MODELO_RAPIDO

INSTRUCAO = """
    Escreva um código Python que imprima 'Olá, Mundo!' usando a função print().
    Certifique-se de que o código seja simples e fácil de entender.
"""

# Forma 1: string. Equivale ao `model="gemini-3.1-flash-lite"` do ADK.
agente = create_agent(model=MODELO_RAPIDO, system_prompt=INSTRUCAO)

# Forma 2: objeto, quando há parâmetros a ajustar. `temperature=0` é o que você
# quer em agente que decide chamada de ferramenta — reduz a "conversa" do modelo.
modelo = init_chat_model(MODELO_RAPIDO, temperature=0)
agente_deterministico = create_agent(model=modelo, system_prompt=INSTRUCAO)

# Para trocar de provedor, instale o pacote e troque só a string:
#   uv add langchain-anthropic  ->  "anthropic:claude-sonnet-4-6"
#   uv add langchain-openai     ->  "openai:gpt-5.5"
