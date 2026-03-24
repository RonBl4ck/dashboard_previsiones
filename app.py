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
    
    /* Reducir márgenes de la página */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
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
    """Carga los datos de prevision desde Google Sheets o un archivo Excel"""
    
    MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

    def _clean_numeric(series):
        """Limpia strings con formato monetario (ej: 'S/ 1,234') y convierte a numero."""
        try:
            cleaned = series.astype(str).str.replace(r'^S/\s*', '', regex=True)
            cleaned = cleaned.str.replace(',', '', regex=False).str.strip()
            return pd.to_numeric(cleaned, errors='coerce')
        except Exception:
            return pd.to_numeric(series, errors='coerce')

    if file_path is not None:
        df = pd.read_excel(file_path, sheet_name='PREVISION 01.26-(PI%)', header=1)
    else:
        import gspread
        from google.oauth2.service_account import Credentials
        try:
            # Leer credenciales desde st.secrets (funciona local y en Streamlit Cloud)
            creds_dict = dict(st.secrets["gcp_service_account"])
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            gc = gspread.authorize(credentials)
            sh = gc.open("PREVISIONES 2026")
            worksheet = sh.worksheet("Hoja 1")
            # UNFORMATTED_VALUE evaluates all formulas and returns raw numeric results
            data = worksheet.get(value_render_option='UNFORMATTED_VALUE')
            headers = [str(h) for h in data[1]]
            df = pd.DataFrame(data[2:], columns=headers)
            df.replace("", pd.NA, inplace=True)

            # Rename value-month columns: from the Sheet they come as 5-digit serials (Excel dates)
            # e.g. 46024 -> Valor_Ene. Sep is a special case named 'Sep30'.
            digit_5_cols = [c for c in headers if str(c).isdigit() and len(str(c)) == 5]
            col_list = list(headers)
            if 'Sep30' in col_list:
                sep30_pos = col_list.index('Sep30')
                before = [c for c in digit_5_cols if col_list.index(c) < sep30_pos]
                after  = [c for c in digit_5_cols if col_list.index(c) > sep30_pos]
                ordered = before[:8] + ['Sep30'] + after[:3]
            else:
                ordered = digit_5_cols[:12]
            rename_map = {col: f'Valor_{MESES[i]}' for i, col in enumerate(ordered) if i < 12}
            df = df.rename(columns=rename_map)

            # Clean all columns: UNFORMATTED_VALUE gives numbers directly.
            # For any cell that still comes as text (e.g. 'S/ 1,234' from conditional formatting)
            # apply the S/ stripping fallback.
            for col in df.columns:
                direct = pd.to_numeric(df[col], errors='coerce')
                if direct.notna().sum() > 0:
                    df[col] = direct
                else:
                    # Fallback: strip S/ prefix and commas
                    fallback = _clean_numeric(df[col])
                    if fallback.notna().sum() > 0:
                        df[col] = fallback
        except Exception as e:
            st.error(f"Error conectando a Google Sheets: {e}")
            return pd.DataFrame()

    # --- Limpieza comun (Excel y Sheets) ---
    df['Año'] = pd.to_numeric(df['Año'], errors='coerce')
    df = df[df['Año'] == 2026].copy()
    df = df.dropna(subset=['DESCRIPCION'])

    # Estandarizar Matricula y Descripcion
    s_mat = df['Matricula'].copy() if 'Matricula' in df.columns else pd.Series('S/M', index=df.index)
    if 'Matrícula' in df.columns:
        s_mat = s_mat.combine_first(df['Matrícula'])
    s_mat = s_mat.fillna('S/M').astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    desc_unificada = df.groupby(s_mat, dropna=False)['DESCRIPCION'].transform('first')
    df['DESCRIPCION'] = s_mat + ' - ' + desc_unificada.astype(str)
    df['Matricula_Clean'] = s_mat

    # Historicos
    meses_hist = {'Consumo 123': 'Hist_2023', 'Consumo 124': 'Hist_2024', 'Consumo 125': 'Hist_2025'}
    df = df.rename(columns=meses_hist)
    historicos = [c for c in ['Hist_2023', 'Hist_2024', 'Hist_2025'] if c in df.columns]
    if historicos:
        for c in historicos:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        df['Promedio_Historico'] = df[historicos].mean(axis=1).fillna(0)
    else:
        df['Promedio_Historico'] = 0

    # Renombrar columnas de CANTIDAD mensual (validas para ambos origenes)
    meses_cant = {m: f'Cant_{m}' for m in MESES}
    df = df.rename(columns=meses_cant)

    # Para uploads de Excel: renombrar columnas de VALOR con sufijos numericos
    excel_valor_map = {
        'Ene2': 'Valor_Ene', 'Feb3': 'Valor_Feb', 'Mar4': 'Valor_Mar',
        'Abr5': 'Valor_Abr', 'May6': 'Valor_May', 'Jun7': 'Valor_Jun',
        'Jul8': 'Valor_Jul', 'Ago9': 'Valor_Ago', 'Sep30': 'Valor_Sep',
        'Oct11': 'Valor_Oct', 'Nov12': 'Valor_Nov', 'Dic13': 'Valor_Dic'
    }
    df = df.rename(columns=excel_valor_map)

    # Calcular Valor_Anual
    valor_cols = [f'Valor_{m}' for m in MESES]
    existing_v = [c for c in valor_cols if c in df.columns]
    for c in existing_v:
        df[c] = _clean_numeric(df[c]).fillna(0)
    df['Valor_Anual'] = df[existing_v].sum(axis=1)

    # Limpiar otras columnas economicas
    for c in ['Valor materiales (MS/.)', 'P.U. s/.', 'Total/Cantidad']:
        if c in df.columns:
            df[c] = _clean_numeric(df[c]).fillna(0)

    # Limpiar columnas de cantidad mensual
    for c in [f'Cant_{m}' for m in MESES]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # Agregar codigo de proyecto al nombre
    if 'Codigo del Proyecto' in df.columns and 'Nombre del proyecto' in df.columns:
        df['Nombre del proyecto'] = df['Nombre del proyecto'].astype(str) + ' (' + df['Codigo del Proyecto'].astype(str) + ')'

    return df


# Sidebar con navegación
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 8px 0 12px 0;">
        <h2 style="color: white; margin: 0;">📊 Previsiones 2026</h2>
        <p style="color: #E9ECEF; font-size: 0.9rem;">Dashboard de Análisis</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Menú de navegación
    from streamlit_option_menu import option_menu
    
    selected = option_menu(
        menu_title=None,
        options=["Resumen", "Previsión vs Real", 
                 "Simulador", "Saldos y Ajustes"],
        icons=["house", "graph-up-arrow", "sliders", "box-seam"],
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
    
    df_principal = load_data()
    try:
        # Filtro de Sección
        secciones = ['Todas'] + list(df_principal['Seccion'].dropna().unique())
        seccion_filter = st.selectbox("Sección", secciones, key="filter_seccion")
        
        # Filtro de Área
        areas = ['Todas'] + list(df_principal['AREA'].dropna().unique())
        area_filter = st.selectbox("Área", areas, key="filter_area")

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        seccion_filter = 'Todas'
        area_filter = 'Todas'

    # ---
    # La carga de datos ahora es automática desde Google Sheets.
    # Se eliminó la opción de subir Excel manual para mayor consistencia.

# Función para aplicar filtros
def apply_filters(df):
    """Aplica los filtros globales al dataframe"""
    filtered_df = df.copy()
    
    if st.session_state.get("filter_seccion") and st.session_state["filter_seccion"] != 'Todas':
        filtered_df = filtered_df[filtered_df['Seccion'] == st.session_state["filter_seccion"]]
    
    if st.session_state.get("filter_area") and st.session_state["filter_area"] != 'Todas':
        filtered_df = filtered_df[filtered_df['AREA'] == st.session_state["filter_area"]]
    
    return filtered_df

# Contenido según selección
if not df_principal.empty:
    if selected == "Resumen":
        from pages import resumen_ejecutivo
        resumen_ejecutivo.show(df_principal, apply_filters)
        
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
