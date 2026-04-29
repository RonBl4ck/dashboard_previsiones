"""
Calculadora de Proporciones de Materiales
Permite estimar cantidades de materiales dependientes basándose en un material principal.
"""

import streamlit as st
import pandas as pd
import sys
from utils.google_sheets_helper import get_gspread_client, update_materials_prevision, get_engineering_kits, update_engineering_kits_batch

sys.path.append('..')


def normalize_column_name(name):
    """Limpia nombres de columnas eliminando saltos de línea y espacios extra."""
    return str(name).replace('\n', ' ').replace('  ', ' ').strip()


@st.cache_data(ttl=3600)
def load_2025_data():
    """Carga los datos desde la hoja de cálculo '2025' usando UNFORMATTED_VALUE."""
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame()

    try:
        sh = gc.open("2025")
        worksheet = sh.get_worksheet(0)
        data = worksheet.get(value_render_option='UNFORMATTED_VALUE')
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=[str(h) for h in data[0]])
        df.columns = [normalize_column_name(c) for c in df.columns]
        
        # Búsqueda priorizada de matrícula
        col_mat = None
        for k in ['MAT./PREST.', 'MATRICULA', 'CODIGO']:
            col_mat = next((c for c in df.columns if k in c.upper() and 'PROYECTO' not in c.upper()), None)
            if col_mat: break
            
        if col_mat:
            df['Matricula_Clean'] = df[col_mat].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        return df
    except Exception as e:
        st.error(f"No se pudo cargar '2025': {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_emitido_data():
    """Carga los datos desde la hoja de cálculo 'EMITIDO'."""
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame()

    try:
        sh = gc.open("EMITIDO")
        worksheet = sh.get_worksheet(0)
        data = worksheet.get(value_render_option='UNFORMATTED_VALUE')
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=[str(h) for h in data[0]])
        df.columns = [normalize_column_name(c) for c in df.columns]
        
        # Búsqueda priorizada de matrícula
        col_mat = None
        for k in ['MAT./PREST.', 'MATRICULA', 'CODIGO']:
            col_mat = next((c for c in df.columns if k in c.upper() and 'PROYECTO' not in c.upper()), None)
            if col_mat: break
            
        if col_mat:
            df['Matricula_Clean'] = df[col_mat].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        return df
    except Exception as e:
        st.error(f"No se pudo cargar 'EMITIDO': {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_consumo_data():
    """Carga los datos desde la hoja de cálculo 'CONSUMO'."""
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame()

    try:
        sh = gc.open("CONSUMO")
        worksheet = sh.get_worksheet(0)
        data = worksheet.get(value_render_option='UNFORMATTED_VALUE')
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=[str(h) for h in data[0]])
        df.columns = [normalize_column_name(c) for c in df.columns]
        
        # Búsqueda priorizada de matrícula
        col_mat = None
        for k in ['MAT./PREST.', 'MATRICULA', 'CODIGO']:
            col_mat = next((c for c in df.columns if k in c.upper() and 'PROYECTO' not in c.upper()), None)
            if col_mat: break

        if col_mat:
            df['Matricula_Clean'] = df[col_mat].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        return df
    except Exception as e:
        st.error(f"Error cargando 'CONSUMO': {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_material_catalog():
    """Consolida un catálogo de materiales desde todas las fuentes para búsquedas."""
    df_2025 = load_2025_data()
    df_emitido = load_emitido_data()
    df_consumo = load_consumo_data()
    
    catalog = {}
    
    for df in [df_emitido, df_2025, df_consumo]:
        if df.empty: continue
        
        # Identificar columnas
        col_mat = 'Matricula_Clean' if 'Matricula_Clean' in df.columns else None
        col_desc = next((c for c in df.columns if any(k in c.upper() for k in ['DESCRIPCION', 'TEXTO', 'DENOMINACION'])), None)
        col_price = next((c for c in df.columns if any(k in c.upper() for k in ['P.U.', 'PRECIO UNITARIO', 'COSTO UNITARIO'])), None)
        
        if col_mat and col_desc:
            for _, row in df.iterrows():
                mat = str(row[col_mat]).strip()
                if mat and mat != 'nan' and mat != 'None':
                    if mat not in catalog:
                        catalog[mat] = {
                            'descripcion': str(row[col_desc]).strip(),
                            'precio': float(row[col_price]) if col_price and pd.notna(row[col_price]) else 0.0
                        }
    return catalog

def show(df_prevision):
    """Función principal de la página Calculadora de Proporciones."""
    st.title("Calculadora de Materiales")
    st.markdown("""
    Herramienta dual para **estimar proporciones** basadas en ingeniería y **simular el impacto** de nuevos materiales en el presupuesto.
    """)
    
    tab_prop, tab_sim = st.tabs(["📊 Ratios de Proporción", "➕ Simulador de Adición/Reducción"])

    with tab_prop:
        show_proporciones(df_prevision)
        
    with tab_sim:
        show_simulador_adicion(df_prevision)


def show_proporciones(df_prevision):
    """Lógica unificada basada en Ingeniería (Modo Técnico)."""
    st.subheader("Validación Técnica de Materiales")

    # --- CARGA DE KITS ---
    if 'eng_kits' not in st.session_state:
        st.session_state['eng_kits'] = get_engineering_kits()

    with st.expander("💾 Gestión de Kits de Proporciones"):
        col_k1, col_k2 = st.columns(2)
        with col_k1:
            st.markdown("**Cargar Kit Guardado**")
            nombres_kits = st.session_state['eng_kits']['Nombre_Kit'].unique().tolist()
            if nombres_kits:
                kit_to_load = st.selectbox("Seleccionar Kit:", nombres_kits)
                if st.button("Cargar Selección", use_container_width=True):
                    df_kit = st.session_state['eng_kits'][st.session_state['eng_kits']['Nombre_Kit'] == kit_to_load]
                    mats_base = df_kit[df_kit['Tipo'] == 'BASE']['Display'].tolist()
                    mats_dep = df_kit[df_kit['Tipo'] == 'DEPENDIENTE']['Display'].tolist()
                    
                    st.session_state['calc_mat_p'] = mats_base
                    st.session_state['calc_mat_d'] = mats_dep
                    st.session_state['active_kit'] = df_kit
                    
                    # Cargar globales
                    if not df_kit.empty:
                        st.session_state['dist_interval'] = df_kit['Intervalo'].iloc[0]
                        tipo_f = df_kit['Factor'].iloc[0]
                        # Buscar indice en el selectbox
                        st.session_state['tipo_emp'] = "Kit Trifásico (3)" if tipo_f == 3.0 else "Individual (1)"
                        
                    st.rerun()
            else:
                st.info("No hay kits guardados aún.")
                
        with col_k2:
            st.markdown("**Guardar Configuración Actual**")
            new_kit_name = st.text_input("Nombre para el nuevo Kit:")
            if st.button("Guardar como Kit", use_container_width=True):
                if not new_kit_name:
                    st.error("Ingresa un nombre para el kit.")
                else:
                    st.session_state['save_kit_trigger'] = new_kit_name
                    st.rerun()

    st.markdown("---")

    # 1. Configuración de Fuente y Alcance
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fuente = st.selectbox(
            "1. Fuente de Datos para el Alcance:",
            ["Emitido", "2025", "Previsión", "Consumo"],
            help="Determina de dónde se sacarán las cantidades de los materiales base."
        )
    with col_f2:
        alcance = st.radio(
            "2. Alcance del cálculo:",
            ["General", "Por PI Específico"],
            horizontal=True
        )

    # 2. Preparar DataFrame según Fuente
    df_base = pd.DataFrame()
    col_cant = "Cant_Calculo"

    if fuente == "2025":
        with st.spinner("Cargando datos de 2025..."):
            df_base = load_2025_data()
    elif fuente == "Emitido":
        with st.spinner("Cargando datos de Emitido..."):
            df_base = load_emitido_data()
    elif fuente == "Consumo":
        with st.spinner("Cargando datos de Consumo..."):
            df_base = load_consumo_data()
    else:  # Previsión
        df_base = df_prevision.copy()

    if df_base.empty:
        st.error(f"No se pudo cargar la fuente '{fuente}'.")
        return

    # Detección dinámica de columna de cantidad según la fuente
    if fuente in ["2025", "Emitido"]:
        col_target = next((c for c in df_base.columns if 'PRECIO TOTAL' in c.upper() or 'CANT' in c.upper() or 'TOTAL' in c.upper()), None)
        df_base['Cant_Calculo'] = pd.to_numeric(df_base[col_target].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0) if col_target else 0
    elif fuente == "Consumo":
        cols_c = [c for c in df_base.columns if 'CONSUMO' in c.upper()]
        df_base['Cant_Calculo'] = df_base[cols_c].sum(axis=1) if cols_c else 0
    else:  # Previsión
        cols_cant_prev = [c for c in df_base.columns if 'Cant_' in c]
        df_base['Cant_Calculo'] = df_base[cols_cant_prev].sum(axis=1)

    # Identificar PI si aplica
    if alcance == "Por PI Específico":
        col_pi = next((c for c in df_base.columns if c.upper() == 'PI' or 'CODIGO' in c.upper() or 'PROYECTO' in c.upper() or 'ELEMENTO PEP' in c.upper()), None)
        if col_pi:
            lista_pis = sorted(df_base[col_pi].dropna().unique())
            pi_seleccionado = st.selectbox("Seleccionar PI:", lista_pis)
            df_base = df_base[df_base[col_pi] == pi_seleccionado]
        else:
            st.warning("No se encontró columna de identificador de proyecto (PI).")

    if df_base.empty:
        st.info("No hay datos disponibles.")
        return

    # 3. Agregación de Materiales
    col_desc = next((c for c in df_base.columns if any(k in c.upper() for k in ['DESCRIPCION', 'DESCRIPC', 'TEXTO', 'DENOMINACION'])), "Descripcion")
    col_mat_id = 'Matricula_Clean'
    if col_mat_id not in df_base.columns:
        for k in ['MAT./PREST.', 'MATRICULA', 'CODIGO']:
            col_mat_id = next((c for c in df_base.columns if k in c.upper() and 'PROYECTO' not in c.upper()), None)
            if col_mat_id: break
        if not col_mat_id: col_mat_id = "Matricula"
    col_um = next((c for c in df_base.columns if c.upper() in ['UM', 'U.M.', 'UNIDAD', 'UNIDAD DE MEDIDA']), "ud")

    # Asegurar columnas y agrupar
    for c in [col_mat_id, col_desc, col_um]:
        if c not in df_base.columns: df_base[c] = "N/A"

    df_grouped = df_base.groupby([col_mat_id, col_desc, col_um])[col_cant].sum().reset_index()
    df_grouped['Display'] = df_grouped[col_mat_id].astype(str) + " - " + df_grouped[col_desc].astype(str).str[:50]
    opciones_mat = df_grouped[df_grouped[col_cant] > 0].sort_values('Display')

    if opciones_mat.empty:
        st.warning("No hay materiales con cantidades registradas.")
        return

    # 4. Selección de Materiales
    mats_principales = st.multiselect(
        "3. Materiales Base (Principales):",
        options=opciones_mat['Display'].unique(),
        key="calc_mat_p"
    )

    mat_dependientes = st.multiselect(
        "4. Materiales Dependientes (A estimar):",
        options=opciones_mat['Display'].unique(),
        key="calc_mat_d"
    )

    if not mats_principales:
        st.info("Selecciona materiales base para comenzar.")
        return

    # 5. Configuración de Ingeniería
    st.markdown("#### ⚙️ Parámetros Globales")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        dist_interval = st.number_input("Intervalo Base (Cada cuánto aplica el cálculo):", min_value=1.0, value=100.0, step=1.0, key="dist_interval")
    with col_g2:
        tipo_emp = st.selectbox("Divisor por Fases:", ["Individual (1)", "Kit Trifásico (3)"], key="tipo_emp")
    
    factor_emp = 3.0 if "Trifásico" in tipo_emp or "3" in tipo_emp else 1.0

    st.markdown("#### 🔧 Multiplicadores")
    col_cfg1, col_cfg2 = st.columns(2)
    
    # Preparar df_base_config
    df_base_config = df_grouped[df_grouped['Display'].isin(mats_principales)].copy()
    df_base_config['Multiplicador'] = 1.0
    if 'active_kit' in st.session_state:
        # Pre-cargar multiplicadores
        kit_df = st.session_state['active_kit']
        kit_bases = kit_df[kit_df['Tipo'] == 'BASE']
        for _, row in kit_bases.iterrows():
            mask = df_base_config['Display'] == row['Display']
            if mask.any():
                df_base_config.loc[mask, 'Multiplicador'] = float(row['Multiplicador'])

    with col_cfg1:
        st.caption("Ajusta el multiplicador para cada **Material Base**:")
        edited_base = st.data_editor(
            df_base_config[['Display', 'Multiplicador']],
            column_config={
                "Display": st.column_config.TextColumn("Material Base", disabled=True),
                "Multiplicador": st.column_config.NumberColumn("Multi.", min_value=0.01, format="%.2f")
            },
            hide_index=True,
            use_container_width=True,
            key="eng_base_editor"
        )
        
    # Preparar df_dep_config
    df_dep_config = df_grouped[df_grouped['Display'].isin(mat_dependientes)].copy()
    df_dep_config['Multiplicador'] = 1.0
    if 'active_kit' in st.session_state:
        kit_df = st.session_state['active_kit']
        kit_deps = kit_df[kit_df['Tipo'] == 'DEPENDIENTE']
        for _, row in kit_deps.iterrows():
            mask = df_dep_config['Display'] == row['Display']
            if mask.any():
                df_dep_config.loc[mask, 'Multiplicador'] = float(row['Multiplicador'])

    with col_cfg2:
        if not mat_dependientes:
            st.info("Selecciona materiales dependientes.")
            edited_dep = pd.DataFrame()
        else:
            st.caption("Ajusta el multiplicador para cada **Material Dependiente**:")
            edited_dep = st.data_editor(
                df_dep_config[['Display', 'Multiplicador']],
                column_config={
                    "Display": st.column_config.TextColumn("Material Dependiente", disabled=True),
                    "Multiplicador": st.column_config.NumberColumn("Multi.", min_value=0.01, format="%.2f")
                },
                hide_index=True,
                use_container_width=True,
                key="eng_dep_editor"
            )

    # Lógica de Guardado (Se ejecuta aquí porque ya tenemos todos los datos de los editors)
    if 'save_kit_trigger' in st.session_state:
        kit_name = st.session_state.pop('save_kit_trigger')
        new_kit_rows = []
        
        # Añadir Bases
        for _, row in edited_base.iterrows():
            mat_raw = str(row['Display']).split(' - ', 1)
            mat_id = mat_raw[0]
            mat_desc = mat_raw[1] if len(mat_raw) > 1 else ""
            new_kit_rows.append({
                "Nombre_Kit": kit_name,
                "Matricula": mat_id,
                "Descripcion": mat_desc,
                "Tipo": "BASE",
                "Multiplicador": row['Multiplicador'],
                "Intervalo": dist_interval,
                "Factor": factor_emp,
                "Display": row['Display']
            })
            
        # Añadir Dependientes
        if not edited_dep.empty:
            for _, row in edited_dep.iterrows():
                mat_raw = str(row['Display']).split(' - ', 1)
                mat_id = mat_raw[0]
                mat_desc = mat_raw[1] if len(mat_raw) > 1 else ""
                new_kit_rows.append({
                    "Nombre_Kit": kit_name,
                    "Matricula": mat_id,
                    "Descripcion": mat_desc,
                    "Tipo": "DEPENDIENTE",
                    "Multiplicador": row['Multiplicador'],
                    "Intervalo": dist_interval,
                    "Factor": factor_emp,
                    "Display": row['Display']
                })
        
        if new_kit_rows:
            df_new_kit = pd.DataFrame(new_kit_rows)
            # Remove old kit with same name
            df_existing = st.session_state['eng_kits']
            if not df_existing.empty:
                df_existing = df_existing[df_existing['Nombre_Kit'] != kit_name]
                df_combined = pd.concat([df_existing, df_new_kit], ignore_index=True)
            else:
                df_combined = df_new_kit
            
            with st.spinner("Guardando Kit..."):
                update_engineering_kits_batch(df_combined)
                st.session_state['eng_kits'] = get_engineering_kits()
                st.success(f"Kit '{kit_name}' guardado correctamente.")
                st.rerun()

    # Cálculo de Demanda Técnica
    total_unidades_base = 0.0
    for _, row in edited_base.iterrows():
        cant_base = df_grouped[df_grouped['Display'] == row['Display']][col_cant].iloc[0]
        total_unidades_base += cant_base * row['Multiplicador']
    
    st.markdown("---")
    st.markdown("#### 📈 Resultado de Validación Técnica")
    st.caption(f"**Unidades Base Ajustadas:** {total_unidades_base:,.2f} | **Intervalo:** {dist_interval} | **Factor:** {factor_emp}")
    
    if mat_dependientes and not edited_dep.empty:
        resultados = []
        for _, row in edited_dep.iterrows():
            display_name = row['Display']
            multi_dep = row['Multiplicador']
            cant_actual = df_grouped[df_grouped['Display'] == display_name][col_cant].iloc[0]
            
            # Formula: Demanda es estática por el intervalo/factor, el multiplicador afecta lo que tenemos
            demanda_teorica = total_unidades_base / (dist_interval * factor_emp)
            presupuesto_ajustado = cant_actual * multi_dep
            diferencia = presupuesto_ajustado - demanda_teorica
            
            estado = "✅ Cumple"
            if abs(diferencia) > (demanda_teorica * 0.1):
                estado = "⚠️ Faltante" if diferencia < 0 else "⚠️ Excedente"
                
            resultados.append({
                "Material": display_name,
                "Multiplicador": f"x{multi_dep}",
                "Demanda Teórica": round(demanda_teorica, 2),
                "Presupuesto Ajustado": round(presupuesto_ajustado, 2),
                "Diferencia": round(diferencia, 2),
                "Estado": estado
            })
            
        df_resultados = pd.DataFrame(resultados)
        
        st.dataframe(
            df_resultados,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Demanda Teórica": st.column_config.NumberColumn(format="%,.2f"),
                "Presupuesto Ajustado": st.column_config.NumberColumn(format="%,.2f"),
                "Diferencia": st.column_config.NumberColumn(format="%+,.2f"),
            }
        )
    else:
        st.info("Selecciona materiales dependientes para ver la validación.")


def show_simulador_adicion(df_prevision):
    """Nueva funcionalidad para simular la adición de materiales y balanceo de presupuesto."""
    st.subheader("Simulador de Impacto Presupuestario")
    
    # 1. Selección de PI
    col_pi = next((c for c in df_prevision.columns if c.upper() == 'PI' or 'CODIGO' in c.upper() or 'PROYECTO' in c.upper() or 'ELEMENTO PEP' in c.upper()), None)
    
    if not col_pi:
        st.error("No se encontró columna de identificador de proyecto (PI) en los datos de previsión.")
        return

    # Usar 'Nombre del proyecto' si existe para el selectbox
    col_nombre = 'Nombre del proyecto' if 'Nombre del proyecto' in df_prevision.columns else col_pi
    lista_proyectos = sorted(df_prevision[col_nombre].dropna().unique())
    proyecto_sel = st.selectbox("1. Seleccionar Proyecto (PI):", lista_proyectos)
    
    df_pi = df_prevision[df_prevision[col_nombre] == proyecto_sel]
    pi_code = df_pi[col_pi].iloc[0] if not df_pi.empty else "N/A"
    
    # Presupuesto Actual del PI
    presupuesto_actual = df_pi['Valor_Anual'].sum()
    st.info(f"💰 **Presupuesto Actual del PI {pi_code}:** S/ {presupuesto_actual:,.2f}")

    st.markdown("---")
    
    # 2. Selección de Acción y Material
    col_acc, col_mat_sel = st.columns([1, 2])
    with col_acc:
        accion = st.radio("Acción:", ["Agregar Nuevo", "Modificar Existente"], horizontal=True)
    
    # Obtener materiales actuales del PI para búsqueda/modificación
    col_mat_id_pi = 'Matricula_Clean'
    col_desc_pi = next((c for c in df_pi.columns if any(k in c.upper() for k in ['DESCRIPCION', 'TEXTO'])), "DESCRIPCION")
    
    df_pi_mats_base = df_pi.groupby([col_mat_id_pi, col_desc_pi]).agg({
        'Valor_Anual': 'sum',
        'P.U. s/.': 'first'
    }).reset_index()
    # Calcular cantidad anual total
    df_pi_mats_base['Cant_Anual'] = df_pi_mats_base['Valor_Anual'] / df_pi_mats_base['P.U. s/.'].replace(0, 1)

    mat_seleccionado_obj = None
    if accion == "Modificar Existente":
        with col_mat_sel:
            df_pi_mats_base['Display'] = df_pi_mats_base[col_mat_id_pi].astype(str) + " - " + df_pi_mats_base[col_desc_pi].astype(str).str[:50]
            mat_sel_name = st.selectbox("Seleccionar material a modificar:", df_pi_mats_base['Display'].tolist())
            mat_seleccionado_obj = df_pi_mats_base[df_pi_mats_base['Display'] == mat_sel_name].iloc[0]

    st.markdown("#### 📦 Datos del Material")
    catalog = get_material_catalog()
    
    col1, col2 = st.columns([1, 2])
    
    if accion == "Agregar Nuevo":
        with col1:
            matricula_in = st.text_input("Matrícula (Opcional):", key="new_mat_id")
        
        sugerencia_desc = ""
        sugerencia_precio = 0.0
        if matricula_in in catalog:
            sugerencia_desc = catalog[matricula_in]['descripcion']
            sugerencia_precio = catalog[matricula_in]['precio']
            st.success(f"Encontrado en catálogo: {sugerencia_desc}")

        with col2:
            desc_in = st.text_input("Descripción del Material:", value=sugerencia_desc, key="new_mat_desc")
        
        col3, col4, col5 = st.columns(3)
        with col3:
            precio_in = st.number_input("Precio Unitario (S/):", min_value=0.0, value=float(sugerencia_precio), format="%.2f", key="new_mat_pu")
        with col4:
            cantidad_in = st.number_input("Cantidad Anual:", min_value=0.0, value=0.0, step=1.0, key="new_mat_qty")
    else:
        # Modificar Existente
        matricula_in = mat_seleccionado_obj[col_mat_id_pi]
        with col1:
            st.text_input("Matrícula:", value=matricula_in, disabled=True)
        with col2:
            desc_in = st.text_input("Descripción:", value=mat_seleccionado_obj[col_desc_pi], disabled=True)
        
        col3, col4, col5 = st.columns(3)
        with col3:
            precio_in = st.number_input("Precio Unitario (S/):", min_value=0.0, value=float(mat_seleccionado_obj['P.U. s/.']), format="%.2f")
        with col4:
            cantidad_actual = float(mat_seleccionado_obj['Cant_Anual'])
            cantidad_in = st.number_input("Nueva Cantidad Anual:", min_value=0.0, value=cantidad_actual, step=1.0)
            st.caption(f"Cantidad actual: {cantidad_actual:,.2f}")

    with col5:
        costo_nuevo_total = precio_in * cantidad_in
        # Si es modificación, el impacto es la diferencia
        costo_anterior = (mat_seleccionado_obj['Valor_Anual'] if mat_seleccionado_obj is not None else 0)
        impacto_soles = costo_nuevo_total - costo_anterior
        st.metric("Costo Final", f"S/ {costo_nuevo_total:,.2f}", delta=f"{impacto_soles:,.2f}" if accion == "Modificar Existente" else None)

    if (accion == "Agregar Nuevo" and costo_nuevo_total <= 0) or (accion == "Modificar Existente" and impacto_soles == 0):
        st.warning("Ajusta la cantidad o precio para ver el impacto.")
        return

    if impacto_soles <= 0:
        st.success(f"✨ Esta modificación genera un **ahorro de S/ {abs(impacto_soles):,.2f}**. No es necesario realizar reducciones en otros materiales.")
        monto_cubierto = 0.0
        updates_to_save = [] # Inicializar lista de actualizaciones
    else:
        st.markdown("---")
        # 3. Balanceo de Presupuesto
        st.markdown("#### ⚖️ Balanceo de Presupuesto (Reducciones)")
        st.markdown("Selecciona los materiales que deseas reducir para compensar el impacto de **S/ {:,.2f}**.".format(impacto_soles))
        
        # Filtrar materiales para reducir (no incluir el que se está modificando)
        df_pi_mats = df_pi_mats_base[df_pi_mats_base[col_mat_id_pi] != matricula_in].copy()
        df_pi_mats = df_pi_mats[df_pi_mats['Valor_Anual'] > 0]
        
        monto_a_compensar = impacto_soles
        monto_cubierto = 0.0
        updates_to_save = []

        if df_pi_mats.empty:
            st.warning("Este PI no tiene otros materiales con presupuesto asignado para reducir.")
        else:
            mats_a_reducir = st.multiselect(
                "Seleccionar materiales para reducir:",
                options=df_pi_mats[col_desc_pi].tolist(),
                help="Selecciona uno o varios materiales para bajar su cantidad y compensar el gasto."
            )
            
            if mats_a_reducir:
                modo_red = st.radio("Modo de Reducción:", ["Proporcional", "Manual (Tú eliges cuánto)"], horizontal=True)
                
                df_red = df_pi_mats[df_pi_mats[col_desc_pi].isin(mats_a_reducir)].copy()
                presupuesto_disponible = df_red['Valor_Anual'].sum()
                
                # Preparar DataFrame para el editor con cantidades
                df_red['Cant_Actual'] = df_red['Valor_Anual'] / df_red['P.U. s/.']
                df_red['Reducción (S/)'] = 0.0
                df_red['Reducción (Cant)'] = 0.0
                
                if modo_red == "Proporcional" and presupuesto_disponible > 0:
                    factor = min(1.0, monto_a_compensar / presupuesto_disponible)
                    df_red['Reducción (S/)'] = df_red['Valor_Anual'] * factor
                    df_red['Reducción (Cant)'] = df_red['Reducción (S/)'] / df_red['P.U. s/.'].replace(0, 1)
                
                st.write(f"**Presupuesto disponible en selección:** S/ {presupuesto_disponible:,.2f}")
                
                # Editor de reducciones con bi-direccionalidad (S/ <-> Cant)
                edited_red = st.data_editor(
                    df_red[[col_desc_pi, 'Cant_Actual', 'Valor_Anual', 'Reducción (S/)', 'Reducción (Cant)', 'P.U. s/.']],
                    column_config={
                        col_desc_pi: st.column_config.TextColumn("Material", disabled=True),
                        'Cant_Actual': st.column_config.NumberColumn("Cant. Actual", format="%,.2f", disabled=True),
                        'Valor_Anual': st.column_config.NumberColumn("Presup. Actual", format="S/ %,.2f", disabled=True),
                        'Reducción (S/)': st.column_config.NumberColumn("Reducción (S/)", format="S/ %,.2f", min_value=0.0, 
                                                                    disabled=(modo_red == "Proporcional")),
                        'Reducción (Cant)': st.column_config.NumberColumn("Reducción (Cant)", format="%,.2f", min_value=0.0,
                                                                       disabled=(modo_red == "Proporcional")),
                        'P.U. s/.': st.column_config.NumberColumn("P.U.", format="S/ %,.2f", disabled=True)
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="red_editor_v2"
                )
                
                for i, row_e in edited_red.iterrows():
                    m_desc = row_e[col_desc_pi]
                    m_pu = row_e['P.U. s/.']
                    m_val_orig = row_e['Valor_Anual']
                    m_red_s = row_e['Reducción (S/)']
                    
                    monto_cubierto += m_red_s
                    
                    if m_red_s > 0:
                        val_final = max(0.0, m_val_orig - m_red_s)
                        cant_final = val_final / m_pu if m_pu > 0 else 0
                        
                        updates_to_save.append({
                            'matricula': df_red[df_red[col_desc_pi] == m_desc][col_mat_id_pi].iloc[0],
                            'descripcion': m_desc, 'pu': m_pu, 
                            'total_qty': cant_final, 'total_valor': val_final, 'is_new': False
                        })

                monto_restante = max(0.0, monto_a_compensar - monto_cubierto)
                if monto_restante > 0.01:
                    st.error(f"⚠️ Faltan **S/ {monto_restante:,.2f}** para balancear el impacto total.")
                elif monto_cubierto > monto_a_compensar + 0.01:
                    st.warning(f"💡 Estás reduciendo **S/ {monto_cubierto - monto_a_compensar:,.2f}** más de lo necesario.")
                else:
                    st.success("✅ El impacto está cubierto.")
            else:
                if monto_a_compensar > 0.01:
                    st.error(f"⚠️ Faltan **S/ {monto_a_compensar:,.2f}** por balancear. Selecciona materiales para reducir.")

    # 4. Resumen Final y Botón de Guardado
    st.markdown("#### 📈 Resumen de Impacto Final")
    nuevo_total_pi = presupuesto_actual + impacto_soles - monto_cubierto
    
    col_res1, col_res2 = st.columns(2)
    with col_res1:
        st.metric("Nuevo Presupuesto Proyectado PI", f"S/ {nuevo_total_pi:,.2f}", delta=f"{nuevo_total_pi - presupuesto_actual:,.2f}")
    with col_res2:
        variacion = ((nuevo_total_pi / presupuesto_actual) - 1) * 100 if presupuesto_actual > 0 else 0
        st.metric("Variación % en PI", f"{variacion:.2f}%")

    st.markdown("---")
    
    if st.button("💾 CONFIRMAR Y GUARDAR CAMBIOS EN BASE DE DATOS", type="primary", use_container_width=True):
        # Preparar el update del material principal
        updates_to_save.append({
            'matricula': matricula_in,
            'descripcion': desc_in,
            'pu': precio_in,
            'total_qty': cantidad_in,
            'total_valor': costo_nuevo_total,
            'is_new': (accion == "Agregar Nuevo")
        })
        
        with st.spinner("Guardando cambios en Google Sheets..."):
            success, msg = update_materials_prevision(pi_code, updates_to_save)
            if success:
                st.success(msg)
                st.balloons()
                st.info("Los cambios se han aplicado. Los valores se distribuyeron equitativamente entre los 12 meses.")
                st.cache_data.clear()
            else:
                st.error(msg)
