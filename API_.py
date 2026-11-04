import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

NOMBRE_BD = "Futbol"

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