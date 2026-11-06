st.subheader("🤖 Pregúntale a tus datos")
pregunta = st.text_input("Escribe tu pregunta (ej. ¿cuál sucursal vendió más?)")
if st.button("Preguntar") and pregunta:
    with st.spinner("Pensando..."):
        r = requests.post(f"{API}/preguntar", json={"pregunta": pregunta}, timeout=60)
    if r.ok:
        st.success(r.json()["respuesta"])
    else:
        st.error(f"Error: {r.text}")