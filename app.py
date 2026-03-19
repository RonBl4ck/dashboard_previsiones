"""
Dashboard de Previsiones 2026
Aplicación principal con navegación multi-página
"""

import streamlit as st
import pandas as pd
from pathlib import Path

# Configuración de página
st.set_page_config(
    page_title="Dashboard Previsiones 2026",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado para estilo corporativo
st.markdown("""
<style>
    /* Colores corporativos */
    :root {
        --primary-color: #1B3F66;
        --secondary-color: #2E86AB;
        --accent-color: #E94F37;
        --success-color: #2ECC71;
        --warning-color: #F39C12;
        --background-color: #F8F9FA;
    }
    
    /* Títulos */
    h1, h2, h3 {
        color: var(--primary-color) !important;
        margin-top: 0rem !important; /* Elimina el espacio superior */
        margin-bottom: 0.5rem !important; /* Reduce el espacio inferior */
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--primary-color) !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: white !important;
    }
    
    /* Títulos en la barra lateral */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: white !important;
    }
    
    /* Etiquetas de los filtros en la barra lateral */
    [data-testid="stSidebar"] label {
        color: white !important;
    }
    
    /* Ocultar la navegación multipágina nativa de Streamlit */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
    
    /* KPIs Cards */
    .kpi-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        margin: 10px 0;
    }
    
    .kpi-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    /* Métricas nativas */
    [data-testid="stMetric"] {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        color: var(--primary-color) !important;
    }
    
    /* Botones */
    .stButton button {
        background-color: var(--primary-color) !important;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        font-weight: 500;
    }
    
    .stButton button:hover {
        background-color: var(--secondary-color) !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #E9ECEF;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: var(--primary-color) !important;
        color: white !important;
    }
    
    /* Dataframes */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #E9ECEF;
        border-radius: 8px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Cargar datos con cache
@st.cache_data(ttl=3600)
def load_data(file_path=None):
    """Carga los datos de previsión desde un archivo Excel"""
    if file_path is None:
        file_path = Path(__file__).parent / "data" / "prevision_2026.xlsx"
    
    df = pd.read_excel(file_path, sheet_name='PREVISION 01.26-(PI%)', header=1)
    
    # Limpieza básica
    df = df[df['Año'] == 2026]  # Solo datos de 2026
    df = df.dropna(subset=['DESCRIPCION'])  # Solo filas con descripción
    
    # Renombrar columnas de valores mensuales para facilitar uso
    meses_valor = {
        'Ene2': 'Valor_Ene', 'Feb3': 'Valor_Feb', 'Mar4': 'Valor_Mar',
        'Abr5': 'Valor_Abr', 'May6': 'Valor_May', 'Jun7': 'Valor_Jun',
        'Jul8': 'Valor_Jul', 'Ago9': 'Valor_Ago', 'Sep30': 'Valor_Sep',
        'Oct11': 'Valor_Oct', 'Nov12': 'Valor_Nov', 'Dic13': 'Valor_Dic'
    }
    df = df.rename(columns=meses_valor)
    
    # Renombrar columnas de cantidades mensuales
    meses_cant = {
        'Ene': 'Cant_Ene', 'Feb': 'Cant_Feb', 'Mar': 'Cant_Mar',
        'Abr': 'Cant_Abr', 'May': 'Cant_May', 'Jun': 'Cant_Jun',
        'Jul': 'Cant_Jul', 'Ago': 'Cant_Ago', 'Sep': 'Cant_Sep',
        'Oct': 'Cant_Oct', 'Nov': 'Cant_Nov', 'Dic': 'Cant_Dic'
    }
    df = df.rename(columns=meses_cant)
    
    # Crear una columna de valor anual total para consistencia
    valor_cols = [f'Valor_{m}' for m in ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']]
    existing_valor_cols = [col for col in valor_cols if col in df.columns]
    df['Valor_Anual'] = df[existing_valor_cols].sum(axis=1)
    
    return df

# Sidebar con navegación
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h2 style="color: white; margin: 0;">📊 Previsiones 2026</h2>
        <p style="color: #E9ECEF; font-size: 0.9rem;">Dashboard de Análisis</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")

    # Carga de datos
    st.markdown("### 📥 Cargar Datos")
    uploaded_file = st.file_uploader(
        "Sube tu archivo Excel de previsiones", 
        type=['xlsx'],
        help="El archivo debe tener la misma estructura que el de la plantilla."
    )

    if uploaded_file is not None:
        # Si se sube un archivo, se usa ese.
        # Se resetea el cache para asegurar que los datos se recarguen.
        st.cache_data.clear()
        df_principal = load_data(uploaded_file)
        st.success("¡Archivo cargado con éxito!")
    else:
        # Si no, se usan los datos por defecto.
        df_principal = load_data()

    st.markdown("---")
    
    # Menú de navegación
    from streamlit_option_menu import option_menu
    
    selected = option_menu(
        menu_title=None,
        options=["Resumen Ejecutivo", "Previsión Mensual", "Previsión vs Real", 
                 "Simulador", "Saldos y Ajustes"],
        icons=["house", "calendar", "graph-up-arrow", "sliders", "box-seam"],
        menu_icon="cast",
        default_index=0,
        orientation="vertical",
        styles={
            "container": {"padding": "10px!important", "background-color": "#1B3F66"},
            "icon": {"color": "#E9ECEF", "font-size": "18px"},
            "nav-link": {
                "font-size": "14px",
                "text-align": "left",
                "margin": "5px 10px",
                "color": "#E9ECEF",
                "--hover-color": "#2E86AB"
            },
            "nav-link-selected": {"background-color": "#2E86AB", "color": "white"},
        }
    )
    
    st.markdown("---")
    
    # Filtros globales en sidebar
    st.markdown("### 🎛️ Filtros Globales")
    
    # df_principal = pd.DataFrame() # DataFrame por defecto vacío
    try:
        # df_principal = load_data()
        
        # Filtro de Sección
        secciones = ['Todas'] + list(df_principal['Seccion'].dropna().unique())
        seccion_filter = st.selectbox("Sección", secciones, key="filter_seccion")
        
        # Filtro de Área
        areas = ['Todas'] + list(df_principal['AREA'].dropna().unique())
        area_filter = st.selectbox("Área", areas, key="filter_area")
        
        # Filtro de Gestor
        gestores = ['Todos'] + list(df_principal['Gestor Previsión'].dropna().unique())
        gestor_filter = st.selectbox("Gestor", gestores, key="filter_gestor")
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        seccion_filter = 'Todas'
        area_filter = 'Todas'
        gestor_filter = 'Todos'

# Función para aplicar filtros
def apply_filters(df):
    """Aplica los filtros globales al dataframe"""
    filtered_df = df.copy()
    
    if st.session_state.get("filter_seccion") and st.session_state["filter_seccion"] != 'Todas':
        filtered_df = filtered_df[filtered_df['Seccion'] == st.session_state["filter_seccion"]]
    
    if st.session_state.get("filter_area") and st.session_state["filter_area"] != 'Todas':
        filtered_df = filtered_df[filtered_df['AREA'] == st.session_state["filter_area"]]
    
    if st.session_state.get("filter_gestor") and st.session_state["filter_gestor"] != 'Todos':
        filtered_df = filtered_df[filtered_df['Gestor Previsión'] == st.session_state["filter_gestor"]]
    
    return filtered_df

# Contenido según selección
if not df_principal.empty:
    if selected == "Resumen Ejecutivo":
        from pages import resumen_ejecutivo
        resumen_ejecutivo.show(df_principal, apply_filters)
        
    elif selected == "Previsión Mensual":
        from pages import prevision_mensual
        prevision_mensual.show(df_principal, apply_filters)
        
    elif selected == "Previsión vs Real":
        from pages import prevision_vs_real
        prevision_vs_real.show(df_principal, apply_filters)
        
    elif selected == "Simulador":
        from pages import simulador
        simulador.show(df_principal, apply_filters)
        
    elif selected == "Saldos y Ajustes":
        from pages import saldos
        saldos.show(df_principal, apply_filters)
else:
    st.warning("No se pudieron cargar los datos principales. Verifica el archivo de origen.")
