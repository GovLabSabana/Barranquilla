# Versión actualizada de streamlit_app.py con semaforización
from prophet import Prophet
import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, to_hex
from datetime import datetime
import plotly.graph_objects as go

# --- CONFIGURACIÓN GLOBAL ---
custom_palette = ["#98cfe0", "#2ca6c5", "#032f45", "#f8b909", "#f38e1a"]
custom_font = "'Segoe UI', sans-serif"

st.set_page_config(layout="wide", page_title="Crímenes en Barranquilla")
st.markdown(f"""
    <style>
        html, body, [class*="css"]  {{
            background-color: #032f45;
            color: white;
            font-family: {custom_font};
        }}
        .stSelectbox label, .stMultiSelect label, .stDateInput label, .stSlider label, .stCheckbox label {{
            color: white;
        }}
        .stSelectbox div[data-baseweb], .stMultiSelect div[data-baseweb], .stDateInput div[data-baseweb], .stSlider div[data-baseweb], .stCheckbox div[data-baseweb] {{
            background-color: #032f45;
            color: white;
        }}
        .stButton>button {{
            background-color: #2ca6c5;
            color: white;
        }}
        .st-bb {{
            background-color: #2ca6c5;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 24px;
        }}
        .stTabs [data-baseweb="tab"] {{
            background-color: transparent;
            color: white;
            border-radius: 4px 4px 0px 0px;
        }}
        .stTabs [aria-selected="true"] {{
            background-color: #2ca6c5;
            color: white;
        }}
    </style>
""", unsafe_allow_html=True)

st.title(" Mapa Interactivo de Crímenes en Barranquilla")

#   Esto es para mostrar en otra tab la semaforización 
tab1, tab2, tab3 = st.tabs(["Mapa de Puntos", "Semaforización de Barrios", "Predicción de Crímenes"])

# --- SUBIR ARCHIVO PERSONALIZADO ---
archivo = st.sidebar.file_uploader(
    "Sube tu archivo de crímenes (.geojson o .csv)", type=["geojson", "csv"])


@st.cache_data
def cargar_datos():
    gdf_barrios = gpd.read_file("barrios.geojson")
    return gdf_barrios


gdf_barrios = cargar_datos()

if archivo is not None:
    if archivo.name.endswith(".geojson"):
        gdf_crimenes = gpd.read_file(archivo)
        print(gdf_crimenes.columns)
        st.sidebar.write("🧾 Columnas cargadas:", gdf_crimenes.columns.tolist())
    elif archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)
        geometry = gpd.points_from_xy(df.longitud, df.latitud)
        gdf_crimenes = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    st.sidebar.success("Archivo cargado correctamente")
else:
    gdf_crimenes = gpd.read_file("crimenes.geojson")

# --- SIDEBAR DE FILTROS ---
st.sidebar.header("Filtros")
barrios_opciones = sorted(gdf_barrios.NOMBRE.dropna().unique())
barrios = st.sidebar.selectbox("Selecciona un barrio:", options=[
                               "Todos"] + barrios_opciones)

tipos_opciones = sorted(gdf_crimenes.tipo_crimen.dropna().unique())
tipo_crimen = st.sidebar.selectbox("Tipo de Crimen", options=[
                                   "Todos"] + list(tipos_opciones))

sexo = st.sidebar.selectbox("Sexo de la víctima", options=["Todos", "M", "F"])

rango_fecha = st.sidebar.date_input("Rango de fechas", value=(
    pd.to_datetime(gdf_crimenes['fecha'].min()).date(), 
    pd.to_datetime(gdf_crimenes['fecha'].max()).date()))
min_hora, max_hora = st.sidebar.slider(
    "Rango horario (hora del día)", 0, 23, (0, 23))

grupos = ["habitante_calle", "prostitucion", "lgtbi", "grupo_etnico"]
filtros_sociales = {g: st.sidebar.checkbox(
    f"{g.replace('_', ' ').title()}", value=False) for g in grupos}

#aca comienza la semaforizacion
def agregar_semaforizacion(gdf_crimenes, gdf_barrios, filtrado=True):
    # Si estamos usando datos filtrados, aplicamos el filtrado
    if filtrado:
        gdf = filtrar_datos(gdf_crimenes)
    else:
        gdf = gdf_crimenes
        
    # Contar crímenes por barrio
    crimen_por_barrio = gdf['barrio'].value_counts().reset_index()
    crimen_por_barrio.columns = ['barrio', 'cantidad_crimenes']
    
    # Merge con el GeoDataFrame de barrios
    gdf_barrios_semaforo = gdf_barrios.merge(
        crimen_por_barrio, how='left', 
        left_on='NOMBRE', right_on='barrio'
    )
    
    # Rellenar NaN con 0 para barrios sin crímenes
    gdf_barrios_semaforo['cantidad_crimenes'] = gdf_barrios_semaforo['cantidad_crimenes'].fillna(0)
    
    # Colores para semaforización
    def asignar_color(cantidad):
        if cantidad == 0:
            return '#5cba47'  # Verde para barrios sin crímenes
        elif cantidad <= 5:
            return '#ffda33'  # Amarillo para barrios con pocos crímenes
        elif cantidad <= 15:
            return '#ff9c33'  # Naranja para barrios con crímenes moderados
        else:
            return '#ff3333'  # Rojo para barrios con muchos crímenes
    
    # Aplicar función para asignar colores
    gdf_barrios_semaforo['color_semaforo'] = gdf_barrios_semaforo['cantidad_crimenes'].apply(asignar_color)
    
    return gdf_barrios_semaforo

# --- FILTRADO DE DATOS ---
def filtrar_datos(gdf_crimenes):
    gdf = gdf_crimenes.copy()
    
    # Filtros de barrio, tipo de crimen y sexo
    if barrios != "Todos":
        gdf = gdf[gdf['barrio'] == barrios]
    if tipo_crimen != "Todos":
        gdf = gdf[gdf['tipo_crimen'] == tipo_crimen]
    if sexo != "Todos":
        gdf = gdf[gdf['sexo'] == sexo]

    # Validar columnas de fecha y hora
    gdf['fecha_dt'] = pd.to_datetime(gdf['fecha'], errors='coerce')
    gdf = gdf[(gdf['fecha_dt'].dt.date >= rango_fecha[0]) &
            (gdf['fecha_dt'].dt.date <= rango_fecha[1])]

    # Validar y filtrar por hora
    if 'hora' in gdf.columns:
        try:
            gdf['hora_h'] = pd.to_datetime(
                gdf['hora'], format='%H:%M', errors='coerce').dt.hour
            gdf = gdf[gdf['hora_h'].notna()]
            gdf = gdf[gdf['hora_h'].between(min_hora, max_hora)]
        except Exception as e:
            st.warning(f"⚠️ Error al procesar la columna 'hora': {e}")

    # Filtrar por grupos sociales
    for grupo, filtro_activo in filtros_sociales.items():
        if filtro_activo and grupo in gdf.columns:
            gdf = gdf[gdf[grupo] == True]
            
    return gdf

# Aplicar filtros a los datos
gdf = filtrar_datos(gdf_crimenes)

# --- PESTAÑA 1: MAPA DE PUNTOS ---
with tab1:
    # --- PALETA DE COLORES ---
    categorias = sorted(gdf['tipo_crimen'].dropna().unique())
    cmap = ListedColormap(custom_palette)
    color_dict = {cat: to_hex(cmap(i / max(1, len(categorias)-1)))
                for i, cat in enumerate(categorias)}

    # --- MAPA DE PUNTOS ---
    if not gdf.empty:
        centro = [gdf.geometry.y.mean(), gdf.geometry.x.mean()]
        m = folium.Map(location=centro, zoom_start=13, tiles="CartoDB dark_matter")

        folium.GeoJson(gdf_barrios, name="Barrios",
                    style_function=lambda x: {"fillOpacity": 0, "color": "white", "weight": 1}).add_to(m)

        for _, row in gdf.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=4,
                color=color_dict.get(row['tipo_crimen'], "#ffffff"),
                fill=True,
                fill_color=color_dict.get(row['tipo_crimen'], "#ffffff"),
                fill_opacity=0.85,
                popup=folium.Popup(f"""
                    <b>ID:</b> {row['id']}<br>
                    <b>Tipo:</b> {row['tipo_crimen']}<br>
                    <b>Fecha:</b> {row['fecha']}<br>
                    <b>Hora:</b> {row.get('hora', 'N/A')}<br>
                    <b>Barrio:</b> {row['barrio']}<br>
                    <b>Edad:</b> {row['edad']}<br>
                    <b>Sexo:</b> {row['sexo']}<br>
                    <b>Sociales:</b><br>
                    {'✔️' if row.get('habitante_calle', False) else '❌'} Habitante calle<br>
                    {'✔️' if row.get('prostitucion', False) else '❌'} Prostitución<br>
                    {'✔️' if row.get('lgtbi', False) else '❌'} LGTBI<br>
                    {'✔️' if row.get('grupo_etnico', False) else '❌'} Grupo étnico
                """, max_width=300)
            ).add_to(m)

        st_data = st_folium(m, width=1200, height=600)
    else:
        st.warning("⚠️ No hay datos disponibles con los filtros seleccionados.")

# --- PESTAÑA 2: SEMAFORIZACIÓN DE BARRIOS ---
with tab2:
    # Crear gdf_barrios_semaforo
    gdf_barrios_semaforo = agregar_semaforizacion(gdf_crimenes, gdf_barrios)
    
    # Crear mapa para semaforización
    centro = [gdf_barrios.geometry.centroid.y.mean(), gdf_barrios.geometry.centroid.x.mean()]
    m_semaforo = folium.Map(location=centro, zoom_start=13, tiles="CartoDB dark_matter")
    
    # Añadir leyenda
    leyenda_html = """
    <div style="position: fixed; bottom: 50px; right: 50px; background-color: rgba(0, 0, 0, 0.7); 
                padding: 10px; border-radius: 5px; z-index: 900; color: white;">
      <h4>Semaforización de Crímenes</h4>
      <p><i class="fa fa-square" style="color:#5cba47;"></i> Sin crímenes</p>
      <p><i class="fa fa-square" style="color:#ffda33;"></i> 1-5 crímenes</p>
      <p><i class="fa fa-square" style="color:#ff9c33;"></i> 6-15 crímenes</p>
      <p><i class="fa fa-square" style="color:#ff3333;"></i> >15 crímenes</p>
    </div>
    """
    m_semaforo.get_root().html.add_child(folium.Element(leyenda_html))
    
    # Añadir capa de barrios semaforizados
    folium.GeoJson(
        gdf_barrios_semaforo,
        name="Semaforización",
        style_function=lambda x: {
            'fillColor': x['properties'].get('color_semaforo', '#5cba47'),
            'color': 'white',
            'weight': 1,
            'fillOpacity': 0.6
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['NOMBRE', 'cantidad_crimenes'],
            aliases=['Barrio:', 'Total crímenes:'],
            style="background-color: white; color: #333333;"
        )
    ).add_to(m_semaforo)
    
    # Mostrar el mapa de semaforización
    st_semaforo = st_folium(m_semaforo, width=1200, height=600)
    
    # Mostrar estadísticas de crímenes por barrio
    st.subheader("Estadísticas de Crímenes por Barrio")
    
    # Crear un DataFrame ordenado para mostrar los barrios con más crímenes
    stats_df = gdf_barrios_semaforo[['NOMBRE', 'cantidad_crimenes']].copy()
    stats_df = stats_df.sort_values('cantidad_crimenes', ascending=False)
    stats_df.columns = ['Barrio', 'Cantidad de Crímenes']
    
    # Mostrar tabla de estadísticas
    st.dataframe(stats_df, use_container_width=True)
    
    # Visualización adicional  para ver 10 barrios con más crímenes :D
    st.subheader("Top 10 Barrios con más Crímenes")
    top_10 = stats_df.head(10)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(top_10['Barrio'], top_10['Cantidad de Crímenes'], color='#2ca6c5')
    ax.set_xlabel('Barrio', fontsize=12)
    ax.set_ylabel('Cantidad de Crímenes', fontsize=12)
    ax.set_xticklabels(top_10['Barrio'], rotation=45, ha='right')
    ax.set_facecolor('#032f45')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    for spine in ax.spines.values():
        spine.set_color('white')
    
    # Añadir valores en las barras
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{int(height)}', ha='center', va='bottom', color='white')
    
    plt.tight_layout()
    st.pyplot(fig)

# --- TABLA DE DATOS ---
if st.checkbox("Mostrar tabla de crímenes filtrados"):
    cols_to_drop = ['geometry']
    if 'fecha_dt' in gdf.columns:
        cols_to_drop.append('fecha_dt')
    if 'hora_h' in gdf.columns:
        cols_to_drop.append('hora_h')
    st.dataframe(gdf.drop(columns=cols_to_drop, errors='ignore'))


    # --- PREDICCIÓN DE CRÍMENES ---
with tab3:
    st.subheader("📈 Predicción de casos de criminalidad por semana")

 
    crimenes = gpd.read_file("crimenes.geojson")
    crimenes["fecha"] = pd.to_datetime(crimenes["fecha"])


    df_semanal = crimenes.groupby(pd.Grouper(key="fecha", freq="W")).size().reset_index(name="casos")
    df_prophet = df_semanal.rename(columns={"fecha": "ds", "casos": "y"})


    semanas_entrenamiento = st.slider("Semanas para entrenar el modelo", 4, len(df_prophet)-1, 12)
    semanas_prediccion = st.slider("Semanas a predecir", 1, 12, 4)

 
    modelo_seleccionado = st.selectbox("Selecciona el modelo de predicción", 
                                       ["Prophet", "Regresión lineal", "Árbol de decisión"])

    # Datos de entrenamiento
    train = df_prophet.tail(semanas_entrenamiento)

    
    if modelo_seleccionado == "Prophet":
        try:
            from prophet import Prophet
        except ImportError:
            from fbprophet import Prophet

        model = Prophet()
        model.fit(train)
        future = model.make_future_dataframe(periods=semanas_prediccion, freq="W")
        forecast = model.predict(future)
        pred_dates = forecast["ds"]
        pred_values = forecast["yhat"]

    elif modelo_seleccionado == "Regresión lineal":
        from sklearn.linear_model import LinearRegression
        import numpy as np

        train["semana"] = np.arange(len(train))
        X_train = train[["semana"]]
        y_train = train["y"]

        model = LinearRegression()
        model.fit(X_train, y_train)

        X_future = np.arange(len(train), len(train) + semanas_prediccion).reshape(-1, 1)
        pred_values = model.predict(X_future)
        pred_dates = pd.date_range(start=train["ds"].iloc[-1] + pd.Timedelta(weeks=1), periods=semanas_prediccion, freq="W")

    elif modelo_seleccionado == "Árbol de decisión":
        from sklearn.tree import DecisionTreeRegressor
        import numpy as np

        train["semana"] = np.arange(len(train))
        X_train = train[["semana"]]
        y_train = train["y"]

        model = DecisionTreeRegressor()
        model.fit(X_train, y_train)

        X_future = np.arange(len(train), len(train) + semanas_prediccion).reshape(-1, 1)
        pred_values = model.predict(X_future)
        pred_dates = pd.date_range(start=train["ds"].iloc[-1] + pd.Timedelta(weeks=1), periods=semanas_prediccion, freq="W")

  
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_prophet["ds"], y=df_prophet["y"],
                             mode="lines+markers", name="Casos reales", line=dict(color="red")))
    fig.add_trace(go.Scatter(x=pred_dates, y=pred_values,
                             mode="lines+markers", name=f"Predicción ({modelo_seleccionado})", 
                             line=dict(color="pink", dash="dot")))
    fig.update_layout(title="Predicción semanal de casos",
                      xaxis_title="Fecha", yaxis_title="Número de casos",
                      legend=dict(x=0, y=1.1, orientation="h"))

    st.plotly_chart(fig, use_container_width=True)
