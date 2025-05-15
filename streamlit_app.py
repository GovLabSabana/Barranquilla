# Versión corregida de streamlit_app.py con colormap unificado verde → rojo

import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from matplotlib.colors import to_hex
from matplotlib import cm
from datetime import datetime

# --- CONFIGURACIÓN GLOBAL ---
custom_font = "'Segoe UI', sans-serif"
colormap = cm.get_cmap("RdYlGn_r")

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

# Tabs
tab1, tab2 = st.tabs(["Mapa de Puntos", "Semaforización de Barrios"])

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
        st.sidebar.write("🗞 Columnas cargadas:", gdf_crimenes.columns.tolist())
    elif archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)
        geometry = gpd.points_from_xy(df.longitud, df.latitud)
        gdf_crimenes = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    st.sidebar.success("Archivo cargado correctamente")
else:
    gdf_crimenes = gpd.read_file("crimenes.geojson")

# Sidebar
st.sidebar.header("Filtros")
barrios_opciones = sorted(gdf_barrios.NOMBRE.dropna().unique())
barrios = st.sidebar.selectbox("Selecciona un barrio:", options=["Todos"] + barrios_opciones)

tipos_opciones = sorted(gdf_crimenes.tipo_crimen.dropna().unique())
tipo_crimen = st.sidebar.selectbox("Tipo de Crimen", options=["Todos"] + list(tipos_opciones))

sexo = st.sidebar.selectbox("Sexo de la víctima", options=["Todos", "M", "F"])

rango_fecha = st.sidebar.date_input("Rango de fechas", value=(
    pd.to_datetime(gdf_crimenes['fecha'].min()).date(), 
    pd.to_datetime(gdf_crimenes['fecha'].max()).date()))
min_hora, max_hora = st.sidebar.slider("Rango horario (hora del día)", 0, 23, (0, 23))

grupos = ["habitante_calle", "prostitucion", "lgtbi", "grupo_etnico"]
filtros_sociales = {g: st.sidebar.checkbox(f"{g.replace('_', ' ').title()}", value=False) for g in grupos}

# Funciones auxiliares
def obtener_color(valor, vmin, vmax):
    norm = (valor - vmin) / (vmax - vmin) if vmax != vmin else 0
    rgba = colormap(norm)
    return to_hex(rgba)

def filtrar_datos(gdf_crimenes):
    gdf = gdf_crimenes.copy()
    if barrios != "Todos":
        gdf = gdf[gdf['barrio'] == barrios]
    if tipo_crimen != "Todos":
        gdf = gdf[gdf['tipo_crimen'] == tipo_crimen]
    if sexo != "Todos":
        gdf = gdf[gdf['sexo'] == sexo]

    gdf['fecha_dt'] = pd.to_datetime(gdf['fecha'], errors='coerce')
    gdf = gdf[(gdf['fecha_dt'].dt.date >= rango_fecha[0]) &
              (gdf['fecha_dt'].dt.date <= rango_fecha[1])]

    if 'hora' in gdf.columns:
        gdf['hora_h'] = pd.to_datetime(
            gdf['hora'], format='%H:%M', errors='coerce').dt.hour
        gdf = gdf[gdf['hora_h'].notna()]
        gdf = gdf[gdf['hora_h'].between(min_hora, max_hora)]

    for grupo, activo in filtros_sociales.items():
        if activo and grupo in gdf.columns:
            gdf = gdf[gdf[grupo] == True]
    return gdf

def agregar_semaforizacion(gdf_crimenes, gdf_barrios):
    gdf = filtrar_datos(gdf_crimenes)
    crimenes_por_barrio = gdf['barrio'].value_counts().reset_index()
    crimenes_por_barrio.columns = ['barrio', 'cantidad_crimenes']

    gdf_barrios_semaforo = gdf_barrios.merge(
        crimenes_por_barrio, how='left', left_on='NOMBRE', right_on='barrio')
    gdf_barrios_semaforo['cantidad_crimenes'] = gdf_barrios_semaforo['cantidad_crimenes'].fillna(0)

    vmin = gdf_barrios_semaforo['cantidad_crimenes'].min()
    vmax = gdf_barrios_semaforo['cantidad_crimenes'].max()

    gdf_barrios_semaforo['color_semaforo'] = gdf_barrios_semaforo['cantidad_crimenes'].apply(lambda x: obtener_color(x, vmin, vmax))
    return gdf_barrios_semaforo, vmin, vmax

# Aplicar filtros
gdf = filtrar_datos(gdf_crimenes)

# --- TAB 1 ---
with tab1:
    centro = [gdf.geometry.y.mean(), gdf.geometry.x.mean()]
    m = folium.Map(location=centro, zoom_start=13, tiles="CartoDB dark_matter")

    folium.GeoJson(gdf_barrios, style_function=lambda x: {"fillOpacity": 0, "color": "white", "weight": 1}).add_to(m)

    gdf_barrios_semaforo, vmin, vmax = agregar_semaforizacion(gdf_crimenes, gdf_barrios)
    gdf = gdf.merge(gdf_barrios_semaforo[['NOMBRE', 'color_semaforo']], how='left', left_on='barrio', right_on='NOMBRE')

    for _, row in gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=4,
            color=row.get('color_semaforo', '#ffffff'),
            fill=True,
            fill_color=row.get('color_semaforo', '#ffffff'),
            fill_opacity=0.85,
            popup=folium.Popup(f"""
                <b>ID:</b> {row['id']}<br>
                <b>Tipo:</b> {row['tipo_crimen']}<br>
                <b>Fecha:</b> {row['fecha']}<br>
                <b>Hora:</b> {row.get('hora', 'N/A')}<br>
                <b>Barrio:</b> {row['barrio']}<br>
                <b>Edad:</b> {row['edad']}<br>
                <b>Sexo:</b> {row['sexo']}<br>
            """, max_width=300)
        ).add_to(m)

    st_folium(m, width=1200, height=600)

# --- TAB 2 ---
with tab2:
    gdf_barrios_semaforo, vmin, vmax = agregar_semaforizacion(gdf_crimenes, gdf_barrios)
    centro = [gdf_barrios.geometry.centroid.y.mean(), gdf_barrios.geometry.centroid.x.mean()]
    m_semaforo = folium.Map(location=centro, zoom_start=13, tiles="CartoDB dark_matter")

    folium.GeoJson(
        gdf_barrios_semaforo,
        style_function=lambda x: {
            'fillColor': x['properties'].get('color_semaforo', '#5cba47'),
            'color': 'white',
            'weight': 1,
            'fillOpacity': 0.6
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['NOMBRE', 'cantidad_crimenes'],
            aliases=['Barrio:', 'Total crímenes:']
        )
    ).add_to(m_semaforo)

    st_folium(m_semaforo, width=1200, height=600)

    st.subheader("Estadísticas de Crímenes por Barrio")
    stats_df = gdf_barrios_semaforo[['NOMBRE', 'cantidad_crimenes']].copy()
    stats_df.columns = ['Barrio', 'Cantidad de Crímenes']
    stats_df = stats_df.sort_values('Cantidad de Crímenes', ascending=False)
    st.dataframe(stats_df, use_container_width=True)

    st.subheader("Top 10 Barrios con más Crímenes")
    top_10 = stats_df.head(10)
    colores_barras = top_10['Cantidad de Crímenes'].apply(lambda x: obtener_color(x, vmin, vmax))

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(top_10['Barrio'], top_10['Cantidad de Crímenes'], color=colores_barras)
    ax.set_xlabel('Barrio')
    ax.set_ylabel('Cantidad de Crímenes')
    ax.set_xticklabels(top_10['Barrio'], rotation=45, ha='right')
    ax.set_facecolor('#032f45')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    for spine in ax.spines.values():
        spine.set_color('white')
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{int(height)}', ha='center', va='bottom', color='white')
    plt.tight_layout()
    st.pyplot(fig)

if st.checkbox("Mostrar tabla de crímenes filtrados"):
    cols_to_drop = ['geometry']
    if 'fecha_dt' in gdf.columns:
        cols_to_drop.append('fecha_dt')
    if 'hora_h' in gdf.columns:
        cols_to_drop.append('hora_h')
    st.dataframe(gdf.drop(columns=cols_to_drop, errors='ignore'))
