"""
Encuentra el modelo de IA que SÍ funciona con tu clave.
Ponlo junto a tu .env y ejecútalo:
    python prueba_ia.py
"""
import os
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

key = os.environ.get("GEMINI_API_KEY")
print("¿Hay clave?:", bool(key), "| empieza con:", (key[:4] + "...") if key else "NADA")

base = "https://generativelanguage.googleapis.com/v1beta"

# 1. Lista los modelos que soportan generateContent
r = requests.get(f"{base}/models?key={key}")
data = r.json()
modelos = [
    m["name"].split("/")[-1]
    for m in data.get("models", [])
    if "generateContent" in m.get("supportedGenerationMethods", [])
]
print("\nModelos con generateContent:")
print(modelos)

# 2. Prueba cada uno hasta que uno responda 200
print("\nProbando cada modelo:")
ganador = None
for m in modelos:
    url = f"{base}/models/{m}:generateContent?key={key}"
    rr = requests.post(url, json={"contents": [{"parts": [{"text": "di: ok"}]}]})
    print(f"  {m}  ->  {rr.status_code}")
    if rr.status_code == 200 and ganador is None:
        ganador = m

print("\n==============================")
if ganador:
    print("USA ESTE MODELO:", ganador)
    print(f'En api.py:   MODELO_IA = "{ganador}"')
else:
    print("Ninguno respondió 200. Pega esta salida completa para revisarlo.")
