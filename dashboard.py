"""
Dashboard del Proyecto Final - Futbol
=====================================
Frontend (Streamlit) que consume la API (api.py):
lista, filtra, grafica y crea registros en las 3 colecciones.

Como ejecutar (en OTRA terminal, con la API ya corriendo):
    python -m streamlit run dashboard.py
"""

import pandas as pd
import requests
import streamlit as st

API = "http://localhost:8000"  # luego cambia por la URL de Render

st.set_page_config(page_title="Proyecto Final", page_icon="⚽", layout="wide")
st.title("⚽ Dashboard de Fútbol")


# --- Funciones que hablan con la API ---------------------------------------
@st.cache_data(ttl=30)
def listar(coleccion, campo=None, valor=None, limite=200):
    params = {"coleccion": coleccion, "limite": limite}
    if campo and valor:
        params.update({"campo": campo, "valor": valor})
    r = requests.get(f"{API}/datos", params=params, timeout=60)
    r.raise_for_status()
    datos = r.json()["datos"]
    # json_normalize aplana los objetos: team -> team.name, homeTeam -> homeTeam.name
    df = pd.json_normalize(datos) if datos else pd.DataFrame()
    # las listas (ej. referees) se pasan a texto para poder mostrarlas
    for c in df.columns:
        if df[c].apply(lambda x: isinstance(x, list)).any():
            df[c] = df[c].astype(str)
    return df


@st.cache_data(ttl=30)
def estadisticas(coleccion, agrupar_por, sumar):
    r = requests.get(
        f"{API}/estadisticas",
        params={"coleccion": coleccion, "agrupar_por": agrupar_por, "sumar": sumar},
        timeout=60,
    )
    r.raise_for_status()
    return pd.DataFrame(r.json()["grupos"])


def enviar(endpoint, payload):
    """Hace el POST a la API y muestra el resultado segun el codigo de estado."""
    try:
        r = requests.post(f"{API}/{endpoint}", json=payload, timeout=60)
    except Exception as e:
        st.error(f"No pude conectarme a la API: {e}")
        return
    if r.status_code == 201:
        st.success(f"Guardado con id {r.json()['id']}")
        st.cache_data.clear()
    elif r.status_code == 409:
        st.warning("Ese registro ya existe (duplicado).")
    elif r.status_code == 422:
        st.error("Datos inválidos. Revisa los campos.")
        st.code(r.text)
    else:
        st.error(f"Error de la API ({r.status_code}): {r.text}")


# --- Barra lateral: colección ----------------------------------------------
st.sidebar.header("Filtros")
coleccion = st.sidebar.selectbox("Colección", ["goleadores", "partidos", "standings"])

# --- Verifica que la API este arriba ---------------------------------------
try:
    df = listar(coleccion)
except Exception:
    st.error(
        f"No pude conectarme a la API en {API}. "
        f"Revisa que esté corriendo:  python -m uvicorn api:app --reload"
    )
    st.stop()

if df.empty:
    st.warning("La colección está vacía.")
    st.stop()

columnas = [c for c in df.columns if c != "_id"]
numericas = df.select_dtypes("number").columns.tolist()

# --- Filtro -----------------------------------------------------------------
campo = st.sidebar.selectbox("Filtrar por campo", ["(todos)"] + columnas)
if campo != "(todos)":
    opciones = sorted(df[campo].dropna().astype(str).unique())
    valor = st.sidebar.selectbox("Valor", opciones)
    df = listar(coleccion, campo=campo, valor=valor)

# --- Métricas ---------------------------------------------------------------
c1, c2 = st.columns(2)
c1.metric("Registros", len(df))
if numericas:
    col_metrica = st.sidebar.selectbox("Métrica a sumar", numericas)
    if col_metrica in df.columns:
        c2.metric(f"Suma de {col_metrica}", int(df[col_metrica].fillna(0).sum()))

# --- Estadísticas (agregación de la API) -----------------------------------
st.subheader("Estadísticas")
categoricas = [c for c in columnas if c not in numericas]
if categoricas and numericas:
    a1, a2 = st.columns(2)
    agrupar = a1.selectbox("Agrupar por", categoricas)
    sumar = a2.selectbox("Sumar", numericas)
    if st.button("Calcular"):
        g = estadisticas(coleccion, agrupar, sumar)
        if g.empty:
            st.info("Sin resultados.")
        else:
            g[agrupar] = g[agrupar].astype(str)
            st.bar_chart(g.set_index(agrupar)["suma"])
            st.dataframe(g, use_container_width=True)

# --- Tabla de datos ---------------------------------------------------------
st.subheader("Datos")
st.dataframe(df, use_container_width=True)

# --- Formularios para crear (uno por colección) ----------------------------
st.subheader("➕ Agregar registro")

if coleccion == "goleadores":
    with st.form("nuevo_goleador"):
        f1, f2 = st.columns(2)
        competition_code = f1.text_input("competition_code", "PD")
        competition_name = f2.text_input("competition_name", "LaLiga")
        season = f1.number_input("season", min_value=1900, value=2023, step=1)
        player_id = f2.number_input("player_id", min_value=0, step=1)
        player_name = f1.text_input("player_name")
        player_nationality = f2.text_input("player_nationality")
        player_section = f1.text_input("player_section", "Offence")
        team_id = f2.number_input("team_id", min_value=0, step=1)
        team_name = f1.text_input("team_name")
        goals = f2.number_input("goals", min_value=0, step=1)
        assists = f1.number_input("assists", min_value=0, step=1)
        penalties = f2.number_input("penalties", min_value=0, step=1)
        guardar = st.form_submit_button("Guardar")
    if guardar:
        enviar("goleadores", {
            "competition_code": competition_code,
            "competition_name": competition_name,
            "season": int(season),
            "player_id": int(player_id),
            "player_name": player_name,
            "player_nationality": player_nationality,
            "player_section": player_section,
            "team_id": int(team_id),
            "team_name": team_name,
            "goals": int(goals),
            "assists": int(assists),
            "penalties": int(penalties),
        })

elif coleccion == "standings":
    with st.form("nuevo_standing"):
        f1, f2 = st.columns(2)
        position = f1.number_input("position", min_value=1, step=1)
        temporada = f2.number_input("temporada", min_value=1900, value=2023, step=1)
        team_id = f1.number_input("team_id", min_value=0, step=1)
        team_name = f2.text_input("team_name")
        team_short_name = f1.text_input("team_short_name (opcional)")
        team_tla = f2.text_input("team_tla (opcional)")
        form_txt = f1.text_input("form (ej. W,W,D,L,W)")
        tipo_tabla = f2.selectbox("tipo_tabla", ["TOTAL", "HOME", "AWAY"])
        competition_name = f1.text_input("competition_name", "LaLiga")
        competition_code = f2.text_input("competition_code", "PD")
        playedGames = f1.number_input("playedGames", min_value=0, step=1)
        won = f2.number_input("won", min_value=0, step=1)
        draw = f1.number_input("draw", min_value=0, step=1)
        lost = f2.number_input("lost", min_value=0, step=1)
        points = f1.number_input("points", min_value=0, step=1)
        goalsFor = f2.number_input("goalsFor", min_value=0, step=1)
        goalsAgainst = f1.number_input("goalsAgainst", min_value=0, step=1)
        guardar = st.form_submit_button("Guardar")
    if guardar:
        enviar("standings", {
            "position": int(position),
            "team_id": int(team_id),
            "team_name": team_name,
            "team_short_name": team_short_name,
            "team_tla": team_tla,
            "form": form_txt,
            "playedGames": int(playedGames),
            "won": int(won),
            "draw": int(draw),
            "lost": int(lost),
            "points": int(points),
            "goalsFor": int(goalsFor),
            "goalsAgainst": int(goalsAgainst),
            "competition_name": competition_name,
            "competition_code": competition_code,
            "tipo_tabla": tipo_tabla,
            "temporada": int(temporada),
        })

else:  # partidos
    with st.form("nuevo_partido"):
        f1, f2 = st.columns(2)
        id_partido = f1.number_input("id (único)", min_value=1, step=1)
        utcDate = f2.text_input("utcDate", "2023-08-11T17:30:00Z")
        matchday = f1.number_input("matchday", min_value=1, step=1)
        status = f2.text_input("status", "FINISHED")
        stage = f1.text_input("stage", "REGULAR_SEASON")
        competition_name = f2.text_input("competition_name", "LaLiga")
        competition_code = f1.text_input("competition_code", "PD")
        home_team_id = f2.number_input("home_team_id", min_value=0, step=1)
        home_team_name = f1.text_input("home_team_name")
        away_team_id = f2.number_input("away_team_id", min_value=0, step=1)
        away_team_name = f1.text_input("away_team_name")
        home_goals = f2.number_input("home_goals", min_value=0, step=1)
        away_goals = f1.number_input("away_goals", min_value=0, step=1)
        guardar = st.form_submit_button("Guardar")
    if guardar:
        enviar("partidos", {
            "id": int(id_partido),
            "utcDate": utcDate,
            "status": status,
            "matchday": int(matchday),
            "stage": stage,
            "competition_name": competition_name,
            "competition_code": competition_code,
            "home_team_id": int(home_team_id),
            "home_team_name": home_team_name,
            "away_team_id": int(away_team_id),
            "away_team_name": away_team_name,
            "home_goals": int(home_goals),
            "away_goals": int(away_goals),
        })


# Gemini asistente para preguntas en lenguaje natural        
st.subheader("🤖 Pregúntale a tus datos")
pregunta = st.text_input("Escribe tu pregunta (ej. ¿Cual es el jugador con más goles?)")
if st.button("Preguntar") and pregunta:
    with st.spinner("Pensando..."):
        r = requests.post(f"{API}/preguntar", json={"pregunta": pregunta}, timeout=60)
    if r.ok:
        st.success(r.json()["respuesta"])
    else:
        st.error(f"Error: {r.text}")