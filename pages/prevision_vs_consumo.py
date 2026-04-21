import streamlit as st
import pandas as pd
import numpy as np
import sys
import io
from utils.google_sheets_helper import get_gspread_client, get_consumo_notes, update_consumo_notes_batch

sys.path.append('..')

def normalize_column_name(name):
    """Limpia nombres de columnas eliminando saltos de línea y espacios extra."""
    return str(name).replace('\n', ' ').replace('  ', ' ').strip()

@st.cache_data(ttl=3600)
def load_consumo_data():
    """Carga los datos desde la hoja de cálculo 'CONSUMO'."""
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame()

    try:
        sh = gc.open("CONSUMO")
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        # Normalizar nombres de columnas para evitar problemas con saltos de línea
        df.columns = [normalize_column_name(c) for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error cargando el archivo 'CONSUMO' de Google Sheets: {e}")
        return pd.DataFrame()

def show(df_prevision):
    st.title("📊 Previsión vs Consumo Histórico")
    st.markdown("""
    Esta página identifica materiales que fueron consumidos en años anteriores (2023-2025) 
    pero que **no están incluidos** en la previsión actual de 2026.
    """)
    st.markdown("---")

    with st.spinner("Cargando datos de consumo y notas..."):
        df_consumo = load_consumo_data()
        dict_notas = get_consumo_notes()

    if df_consumo.empty:
        st.warning("No se encontraron datos en el archivo 'CONSUMO'.")
        return

    # 1. Preparar IDs de la previsión para el cruce
    ids_prevision = set(df_prevision['Matricula_Clean'].unique())

    # 2. Procesar datos de CONSUMO
    # Identificar columnas de consumo por año (manejo flexible de nombres)
    col_2023 = next((c for c in df_consumo.columns if 'Consumo' in c and '2023' in c), None)
    col_2024 = next((c for c in df_consumo.columns if 'Consumo' in c and '2024' in c), None)
    col_2025 = next((c for c in df_consumo.columns if 'Consumo' in c and '2025' in c), None)
    
    cols_historicas = [c for c in [col_2023, col_2024, col_2025] if c is not None]

    if not cols_historicas:
        st.error("No se detectaron las columnas de consumo (2023, 2024 o 2025) en el archivo.")
        return

    # Limpiar Matricula en el archivo de consumo
    df_consumo['Matricula_Clean'] = df_consumo['Matricula'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

    # 3. Filtrar: Materiales en Consumo que NO están en Previsión
    df_faltantes = df_consumo[~df_consumo['Matricula_Clean'].isin(ids_prevision)].copy()

    if df_faltantes.empty:
        st.success("✅ ¡Excelente! Todos los materiales con consumo histórico están incluidos en la previsión 2026.")
        return

    # 4. Cálculos Adicionales
    # Convertir a numérico para calcular el máximo
    for col in cols_historicas:
        df_faltantes[col] = pd.to_numeric(df_faltantes[col], errors='coerce').fillna(0)
    
    df_faltantes['Máximo Histórico'] = df_faltantes[cols_historicas].max(axis=1)

    # 5. Integrar Notas Persistentes
    df_faltantes['Anotación'] = df_faltantes['Matricula_Clean'].map(dict_notas).fillna('')

    # --- NUEVA SECCIÓN: BUSCADOR Y DETALLE ---
    st.subheader("🔍 Buscador de Materiales")
    
    # Crear lista de búsqueda: "Matrícula - Descripción"
    opciones_busqueda = df_faltantes['Matricula_Clean'] + " - " + df_faltantes['Descripcion'].astype(str).str[:60]
    map_busqueda = dict(zip(opciones_busqueda, df_faltantes['Matricula_Clean']))
    
    col_search, _ = st.columns([2, 1])
    with col_search:
        seleccion = st.selectbox(
            "Buscar por Matrícula o Nombre:",
            options=["-- Seleccionar para ver detalle --"] + list(opciones_busqueda),
            index=0,
            help="Escribe para buscar un material específico entre los materiales omitidos."
        )
    
    if seleccion != "-- Seleccionar para ver detalle --":
        mat_id = map_busqueda[seleccion]
        detalle = df_faltantes[df_faltantes['Matricula_Clean'] == mat_id].iloc[0]
        
        # Mostrar Ficha Técnica destacada
        with st.container():
            st.markdown(f"""
            <div style="background-color: white; padding: 20px; border-radius: 10px; border-left: 5px solid #1B3F66; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px;">
                <h3 style="margin-top:0; color:#1B3F66;">📄 Detalle del Material: {mat_id}</h3>
                <p><b>Descripción:</b> {detalle['Descripcion']}</p>
                <div style="display: flex; gap: 40px; margin-top: 15px;">
                    <div><small style="color:gray;">U.M.</small><br><b>{detalle.get('UM', '-')}</b></div>
                    <div><small style="color:gray;">P. Inventario</small><br><b>S/ {detalle.get('P. Inventario', 0):,.2f}</b></div>
                    <div><small style="color:gray;">Existe en Base</small><br><b>{detalle.get('EXISTE EN MATERIALES', '-')}</b></div>
                </div>
                <hr style="margin: 15px 0; border: 0; border-top: 1px solid #eee;">
                <div style="display: flex; gap: 40px;">
                    <div><small style="color:gray;">Consumo 2023</small><br><span style="font-size:1.1rem;">{detalle.get(col_2023, 0):,.0f}</span></div>
                    <div><small style="color:gray;">Consumo 2024</small><br><span style="font-size:1.1rem;">{detalle.get(col_2024, 0):,.0f}</span></div>
                    <div><small style="color:gray;">Consumo 2025</small><br><span style="font-size:1.1rem;">{detalle.get(col_2025, 0):,.0f}</span></div>
                    <div style="color: #E94F37;"><small style="color:#E94F37;">MÁX. HISTÓRICO</small><br><b style="font-size:1.2rem;">{detalle['Máximo Histórico']:,.0f}</b></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # 6. Interfaz de Tabla
    st.subheader(f"📋 Tabla Global de Materiales Omitidos ({len(df_faltantes)})")
    st.caption("Usa esta tabla para revisión masiva y para guardar tus anotaciones.")

    # Columnas a mostrar: Matricula, Descripcion, Máximo Histórico, EXISTE EN MATERIALES, Anotación
    col_display_map = {
        'Matricula': 'Matrícula',
        'Descripcion': 'Descripción',
        'Máximo Histórico': 'Máx. Histórico (23-25)',
        'EXISTE EN MATERIALES': 'Existe en Base',
        'Anotación': 'Anotación'
    }
    
    # Asegurar que existan las columnas solicitadas
    for col in col_display_map.keys():
        if col not in df_faltantes.columns:
            df_faltantes[col] = '-'

    df_to_edit = df_faltantes[list(col_display_map.keys())].copy()
    df_to_edit.columns = [col_display_map[c] for c in df_to_edit.columns]

    edited_df = st.data_editor(
        df_to_edit,
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            'Matrícula': st.column_config.TextColumn("Matrícula", disabled=True),
            'Descripción': st.column_config.TextColumn("Descripción", disabled=True),
            'Máx. Histórico (23-25)': st.column_config.NumberColumn("Máx. Histórico", format="%,.0f", disabled=True),
            'Existe en Base': st.column_config.TextColumn("Existe en Base", disabled=True),
            'Anotación': st.column_config.TextColumn("Anotación", help="Escribe tus observaciones aquí", max_chars=500)
        }
    )

    # 7. Botón de Guardado y Descarga
    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1.5, 3])
    
    with col_btn1:
        if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
            # Preparar dataframe para subir
            # Recuperar Matricula original para el cruce de guardado
            df_update = edited_df[['Matrícula', 'Anotación']].copy()
            df_update.columns = ['Matricula', 'Anotacion']
            
            # Combinar con las notas actuales para no borrar materiales que no aparecen en el filtro actual (si los hubiera)
            all_notes_df = pd.DataFrame(list(dict_notas.items()), columns=['Matricula', 'Anotacion'])
            
            if not all_notes_df.empty:
                # Upsert local
                idx_to_update = df_update['Matricula']
                all_notes_df = all_notes_df[~all_notes_df['Matricula'].isin(idx_to_update)]
                final_notes_df = pd.concat([all_notes_df, df_update], ignore_index=True)
            else:
                final_notes_df = df_update

            if update_consumo_notes_batch(final_notes_df):
                st.success("✅ Anotaciones guardadas correctamente en Google Sheets.")
                st.cache_data.clear()
                st.rerun()

    with col_btn2:
        # Preparación de datos para exportar a Excel
        buffer = io.BytesIO()
        
        # Sincronizar anotaciones del editor en el DataFrame de exportación
        df_export = df_faltantes.copy()
        # Mapear anotaciones desde edited_df (que el usuario pudo haber modificado)
        notas_actualizadas = dict(zip(edited_df['Matrícula'], edited_df['Anotación']))
        df_export['Anotación'] = df_export['Matricula_Clean'].map(notas_actualizadas).fillna('')
        
        # Seleccionar y renombrar columnas para el Excel
        export_cols = {
            'Matricula': 'Matrícula',
            'Descripcion': 'Descripción',
            col_2023: 'Consumo 2023',
            col_2024: 'Consumo 2024',
            col_2025: 'Consumo 2025',
            'Máximo Histórico': 'Máximo Histórico',
            'EXISTE EN MATERIALES': 'Existe en Base (Mase)',
            'Anotación': 'Anotación'
        }
        
        # Filtrar solo las que existen
        cols_finales = [c for c in export_cols.keys() if c in df_export.columns]
        df_to_excel = df_export[cols_finales].rename(columns=export_cols)
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_to_excel.to_excel(writer, index=False, sheet_name='Materiales Omitidos')
            
        st.download_button(
            label="📥 Descargar Excel",
            data=buffer.getvalue(),
            file_name="materiales_omitidos_consumo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Descarga la lista de materiales omitidos con su historial de consumo y anotaciones."
        )

    with col_btn3:
        st.info("💡 Consejo: Usa las anotaciones para documentar por qué un material histórico fue omitido.")
