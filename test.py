import requests
import time

print("1️⃣ [TESTE] Simulando a chegada de um Novo Lead...")
requests.post("http://localhost:5000/webhook/novo-lead", json={"nome": "João", "email": "joao@teste.com"})
time.sleep(2)

print("\n2️⃣ [TESTE] Simulando aviso do Stormy (Novo influenciador)...")
requests.post("http://localhost:5000/webhook/stormy", json={"influenciador": "Felipe Neto", "nicho": "Tecnologia"})
time.sleep(2)

print("\n3️⃣ [TESTE] Simulando CRON da Eva Brain (Otimização de Ads)...")
requests.get("http://localhost:5000/jobs/analisar-ads")
