import os
from typing import Optional
import requests

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import PyMongoError
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

NOMBRE_BD = "Futbol"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODELO_IA = "gemma-4-26b-a4b-it"   

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
# Posts 
# ==== CREAR ================================================================
def insertar(nombre_coleccion: str, doc: dict, filtro_duplicado: dict):
    """Inserta el documento; 409 si ya existe, 503 si falla Mongo."""
    col = COLECCIONES[nombre_coleccion]
    try:
        if col.find_one(filtro_duplicado):
            raise HTTPException(status_code=409, detail="Ese registro ya existe.")
        resultado = col.insert_one(doc)
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Error al conectar con la base de datos.")
    return {"mensaje": "Registro creado", "id": str(resultado.inserted_id)}


# ---- 1. GOLEADORES ----
class NuevoGoleador(BaseModel):
    competition_code: str = Field(min_length=1)
    competition_name: str = Field(min_length=1)
    season: str = Field(min_length=4)
    player_id: str = Field(min_length=1)
    player_name: str = Field(min_length=1)
    player_nationality: str
    player_section: str
    team_id: str = Field(min_length=1)
    team_name: str = Field(min_length=1)
    goals: int = Field(ge=0)
    assists: int = Field(ge=0)
    penalties: int = Field(ge=0)


@app.post("/goleadores", status_code=201)
def crear_goleador(r: NuevoGoleador):
    doc = r.model_dump()
    return insertar("goleadores", doc, {
        "player_id": doc["player_id"],
        "season": doc["season"],
        "competition_code": doc["competition_code"],
    })


# ---- 2. STANDINGS ----
class NuevoStanding(BaseModel):
    position: int = Field(ge=1)
    team_id: int
    team_name: str = Field(min_length=1)
    team_short_name: str = ""
    team_tla: str = ""
    form: str = ""
    playedGames: int = Field(ge=0)
    won: int = Field(ge=0)
    draw: int = Field(ge=0)
    lost: int = Field(ge=0)
    points: int = Field(ge=0)
    goalsFor: int = Field(ge=0)
    goalsAgainst: int = Field(ge=0)
    competition_name: str = Field(min_length=1)
    competition_code: str = Field(min_length=1)
    tipo_tabla: str = Field(description="TOTAL, HOME o AWAY")
    temporada: int = Field(ge=1900)


@app.post("/standings", status_code=201)
def crear_standing(r: NuevoStanding):
    d = r.model_dump()
    doc = {
        "position": d["position"],
        "team": {
            "id": d["team_id"],
            "name": d["team_name"],
            "shortName": d["team_short_name"] or d["team_name"],
            "tla": d["team_tla"],
            "crest": f"https://crests.football-data.org/{d['team_id']}.png",
        },
        "playedGames": d["playedGames"],
        "form": d["form"],
        "won": d["won"],
        "draw": d["draw"],
        "lost": d["lost"],
        "points": d["points"],
        "goalsFor": d["goalsFor"],
        "goalsAgainst": d["goalsAgainst"],
        "goalDifference": d["goalsFor"] - d["goalsAgainst"],
        "competition_name": d["competition_name"],
        "competition_code": d["competition_code"],
        "tipo_tabla": d["tipo_tabla"],
        "temporada": d["temporada"],
    }
    return insertar("standings", doc, {
        "team.id": d["team_id"],
        "temporada": d["temporada"],
        "competition_code": d["competition_code"],
        "tipo_tabla": d["tipo_tabla"],
    })


# ---- 3. PARTIDOS (version simplificada) ----
class NuevoPartido(BaseModel):
    id: int
    utcDate: str = Field(min_length=10, description="Ej: 2023-08-11T17:30:00Z")
    status: str = "FINISHED"
    matchday: int = Field(ge=1)
    stage: str = "REGULAR_SEASON"
    competition_name: str = Field(min_length=1)
    competition_code: str = Field(min_length=1)
    home_team_id: int
    home_team_name: str = Field(min_length=1)
    away_team_id: int
    away_team_name: str = Field(min_length=1)
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)


@app.post("/partidos", status_code=201)
def crear_partido(r: NuevoPartido):
    d = r.model_dump()
    if d["home_goals"] > d["away_goals"]:
        ganador = "HOME_TEAM"
    elif d["home_goals"] < d["away_goals"]:
        ganador = "AWAY_TEAM"
    else:
        ganador = "DRAW"

    doc = {
        "id": d["id"],
        "utcDate": d["utcDate"],
        "status": d["status"],
        "matchday": d["matchday"],
        "stage": d["stage"],
        "homeTeam": {
            "id": d["home_team_id"],
            "name": d["home_team_name"],
            "shortName": d["home_team_name"],
            "tla": "",
            "crest": f"https://crests.football-data.org/{d['home_team_id']}.png",
        },
        "awayTeam": {
            "id": d["away_team_id"],
            "name": d["away_team_name"],
            "shortName": d["away_team_name"],
            "tla": "",
            "crest": f"https://crests.football-data.org/{d['away_team_id']}.png",
        },
        "score": {
            "winner": ganador,
            "duration": "REGULAR",
            "fullTime": {"home": d["home_goals"], "away": d["away_goals"]},
            "halfTime": {"home": 0, "away": 0},
        },
        "competition_name": d["competition_name"],
        "competition_code": d["competition_code"],
    }
    return insertar("partidos", doc, {"id": d["id"]})
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