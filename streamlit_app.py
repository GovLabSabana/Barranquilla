# -*- coding: utf-8 -*-
# Modificado desde Colab e integrado con Railway con mejoras visuales

import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, to_hex
from datetime import datetime

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
    </style>
""", unsafe_allow_html=True)

st.title("📍 Mapa Interactivo de Crímenes en Barranquilla")

# --- SUBIR ARCHIVO PERSONALIZADO ---
archivo = st.sidebar.file_uploader("Sube tu archivo de crímenes (.geojson o .csv)", type=["geojson", "csv"])

@st.cache_data
def cargar_datos():
    gdf_barrios = gpd.read_file("barrios.geojson")
    return gdf_barrios

gdf_barrios = cargar_datos()

if archivo is not None:
    if archivo.name.endswith(".geojson"):
        gdf_crimenes = gpd.read_file(archivo)
    elif archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)
        geometry = gpd.points_from_xy(df.longitud, df.latitud)
        gdf_crimenes = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    st.success("Archivo cargado correctamente")
else:
    gdf_crimenes = gpd.read_file("crimenes.geojson")

# --- SIDEBAR DE FILTROS ---
st.sidebar.header("Filtros")
barrios_opciones = sorted(gdf_barrios.NOMBRE.dropna().unique())
barrios = st.sidebar.selectbox("Selecciona un barrio:", options=["Todos"] + barrios_opciones)

tipos_opciones = sorted(gdf_crimenes.tipo_crimen.dropna().unique())
tipo_crimen = st.sidebar.selectbox("Tipo de Crimen", options=["Todos"] + list(tipos_opciones))

sexo = st.sidebar.selectbox("Sexo de la víctima", options=["Todos", "M", "F"])

rango_fecha = st.sidebar.date_input("Rango de fechas", value=(gdf_crimenes['fecha'].min(), gdf_crimenes['fecha'].max()))
min_hora, max_hora = st.sidebar.slider("Rango horario (hora del día)", 0, 23, (0, 23))

grupos = ["habitante_calle", "prostitucion", "lgtbi", "grupo_etnico"]
filtros_sociales = {g: st.sidebar.checkbox(f"{g.replace('_', ' ').title()}", value=False) for g in grupos}

# --- FILTRADO DE DATOS ---
gdf = gdf_crimenes.copy()
if barrios != "Todos":
    gdf = gdf[gdf['barrio'] == barrios]
if tipo_crimen != "Todos":
    gdf = gdf[gdf['tipo_crimen'] == tipo_crimen]
if sexo != "Todos":
    gdf = gdf[gdf['sexo'] == sexo]

# Validar columnas de fecha y hora
gdf['fecha_dt'] = pd.to_datetime(gdf['fecha'], errors='coerce')
gdf = gdf[(gdf['fecha_dt'].dt.date >= rango_fecha[0]) & (gdf['fecha_dt'].dt.date <= rango_fecha[1])]

if 'hora' in gdf.columns:
    gdf['hora'] = gdf['hora'].astype(str).str[:5]
    gdf['hora_h'] = pd.to_datetime(gdf['hora'], format='%H:%M', errors='coerce').dt.hour
    gdf = gdf[gdf['hora_h'].between(min_hora, max_hora, inclusive='both')]
else:
    #st.warning("No se encontró la columna 'hora'. Se omite el filtro horario.")

for g, activo in filtros_sociales.items():
    if activo:
        gdf = gdf[gdf[g] == 1]

# --- PALETA DE COLORES ---
categorias = sorted(gdf['tipo_crimen'].dropna().unique())
cmap = ListedColormap(custom_palette)
color_dict = {cat: to_hex(cmap(i / max(1, len(categorias)-1))) for i, cat in enumerate(categorias)}

# --- MAPA ---
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
                {'✔️' if row['habitante_calle'] else '❌'} Habitante calle<br>
                {'✔️' if row['prostitucion'] else '❌'} Prostitución<br>
                {'✔️' if row['lgtbi'] else '❌'} LGTBI<br>
                {'✔️' if row['grupo_etnico'] else '❌'} Grupo étnico
            """, max_width=300)
        ).add_to(m)

    st_data = st_folium(m, width=1200, height=600)
else:
    st.warning("⚠️ No hay datos disponibles con los filtros seleccionados.")

# --- TABLA ---
cols_to_drop = ['geometry', 'fecha_dt', 'hora_h'] if 'hora_h' in gdf.columns else ['geometry', 'fecha_dt']
if st.checkbox("Mostrar tabla de crímenes filtrados"):
    st.dataframe(gdf.drop(columns=cols_to_drop, errors='ignore'))
