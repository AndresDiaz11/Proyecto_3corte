import os
from typing import Optional
import requests

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

NOMBRE_BD = "Futbol"

GEMINI_API_KEY = os.env.get("GEMINI_API_KEY")
MODELO_IA = "gemini-3.1-pro"   

#CONEXION CON MONGO

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError(
        "Falta la variable de entorno MONGO_URI. "
        "Crea un archivo .env con tu cadena de conexion de Atlas (mira el README)."
    )

cliente = MongoClient(MONGO_URI)
bd = cliente[NOMBRE_BD]

# clave = nombre que usa la API / valor = nombre real en Atlas
COLECCIONES = {
    "goleadores": bd["goleadores"],
    "partidos": bd["Partidos"],
    "standings": bd["standings"],
}

#LA APLICACION

app = FastAPI(
    title="API Proyecto Final",
    description="Consulta y administra los datos del proyecto.",
)
def _a_json(doc):
    """El _id de Mongo es un objeto especial; lo pasamos a texto para el JSON."""
    doc["_id"] = str(doc["_id"])
    return doc

def obtener_coleccion(nombre: str):
    if nombre not in COLECCIONES:
        raise HTTPException(
            status_code=404,
            detail=f"Coleccion '{nombre}' no existe. Opciones: {list(COLECCIONES)}",
        )
    return COLECCIONES[nombre]


def construir_filtro(campo, valor):
    """Si el valor parece numero, busca tanto texto como numero."""
    if not (campo and valor):
        return {}
    opciones = [valor]
    try:
        opciones.append(int(valor))
    except ValueError:
        pass
    return {campo: {"$in": opciones}}


@app.get("/datos")
def listar(coleccion: str = "goleadores", campo: Optional[str] = None,
           valor: Optional[str] = None, limite: int = 20):
    col = obtener_coleccion(coleccion)
    filtro = construir_filtro(campo, valor)
    documentos = [_a_json(d) for d in col.find(filtro).limit(limite)]
    return {"cantidad": len(documentos), "datos": documentos}


@app.get("/estadisticas")
def estadisticas(agrupar_por: str, sumar: str, coleccion: str = "goleadores"):
    col = obtener_coleccion(coleccion)
    pipeline = [
        {"$group": {"_id": f"${agrupar_por}",
                    "suma": {"$sum": f"${sumar}"},
                    "conteo": {"$sum": 1}}},
        {"$sort": {"suma": -1}},
    ]
    grupos = [{agrupar_por: r["_id"], "suma": r["suma"], "conteo": r["conteo"]}
              for r in col.aggregate(pipeline)]
    return {"grupos": grupos}

#IA GEMINI

class Pregunta(BaseModel):
    pregunta: str
 
    model_config = {
        "json_schema_extra": {
            "example": {"pregunta": "¿Cuál sucursal vendió más?"}
        }
    }
 
 
@app.post("/preguntar")
def preguntar(p: Pregunta):
    """Responde una pregunta en lenguaje natural usando los datos de la coleccion."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Falta la GEMINI_API_KEY.")
 
    # 1. Una muestra de los datos como contexto para la IA
    muestra = [_a_json(d) for d in coleccion.find().limit(30)]
 
    # 2. El prompt: instrucciones + datos + pregunta
    prompt = (
        "Eres un asistente que responde preguntas sobre estos datos. "
        "Responde en español, breve y claro. Si la respuesta no está en los datos, dilo.\n\n"
        f"DATOS (muestra):\n{muestra}\n\nPREGUNTA: {p.pregunta}"
    )
 
    # 3. Llamamos a la API del modelo (¡es otra API REST!)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODELO_IA}:generateContent?key={GEMINI_API_KEY}"
    )
    try:
        r = requests.post(
            url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        respuesta = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al llamar al modelo: {e}")
 
    return {"respuesta": respuesta}