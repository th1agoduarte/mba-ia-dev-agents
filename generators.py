async def process_algo():
    print("Iniciando o processo...")
    # processo algo
    yield 1
    print("Continuando o processo...")
    # processo algo
    yield 2
    print("Finalizando o processo...")


resultado = process_algo()

for valor in resultado:
    print(f"Valor gerado: {valor}")
    