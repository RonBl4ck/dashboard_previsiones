"""
Página de Saldos y Ajustes
Permite gestionar stock, compararlo con previsiones y ejecución real.
"""

import streamlit as st
import pandas as pd
import sys
import numpy as np
from utils.google_sheets_helper import get_saldos_data, update_saldos_batch
# Reutilizamos load_ejecutado para no duplicar código
from pages.prevision_vs_real import load_ejecutado

sys.path.append('..')


def _format_value(value, decimals=0, use_k=False, suffix=''):
    """Formatea un valor numérico según las preferencias del usuario.
    
    Args:
        value: Valor numérico a formatear.
        decimals: Cantidad de decimales (0-4).
        use_k: Si True, divide entre 1000 y añade 'k'.
        suffix: Sufijo de unidad (ej: 'm', 'kg', 'und'). Se pega al número sin espacio.
    
    Returns:
        Cadena formateada (ej: '10k', '1,500m', '10km').
    """
    if pd.isna(value) or value == 0:
        return "0" + (suffix if suffix else "")
    
    if use_k and abs(value) >= 1000:
        formatted = f"{value / 1000:,.{decimals}f}k"
    else:
        formatted = f"{value:,.{decimals}f}"
    
    if suffix:
        formatted += suffix
    
    return formatted


def _build_auto_annotation(prev_orig, stockq, result, decimals, use_k, suffix):
    """Construye la anotación automática del cálculo StockQ.
    
    Formato literal:
      Se considera la diferencia de la prevision (1,500m) - StockQ (500m) = (1,000m)
    """
    fmt = lambda v: _format_value(v, decimals, use_k, suffix)
    return f"Se considera la diferencia de la prevision ({fmt(prev_orig)}) - StockQ ({fmt(stockq)}) = ({fmt(result)})"


def show(df_previsiones, apply_filters):
    """Función principal de la página de Saldos y Ajustes"""

    st.title("📦 Control de Saldos e Inventario")
    st.markdown("---")

    df_filtered = apply_filters(df_previsiones)
    if df_filtered.empty:
        st.warning("No hay datos de previsión con los filtros seleccionados")
        return

    # --- 1. CARGA DE DATOS (PREVISIÓN, EJECUTADO, SALDOS) ---
    with st.spinner("Cargando datos del inventario y ejecución..."):
        # Obtener Saldos de Sheets
        df_saldos_sheets = get_saldos_data()
        
        # Obtener Ejecutado 
        df_ejecutado_raw = load_ejecutado()
        df_ejec_material = pd.DataFrame(columns=['Matricula_Original', 'Real_Total', 'Precio_Total'])

        if df_ejecutado_raw is not None and not df_ejecutado_raw.empty:
            # Procesar ejecutado (similar pero simplificado de prevision_vs_real)
            if 'Fecha de Asignacion' in df_ejecutado_raw.columns:
                id_col = 'Mat./Prest.' if 'Mat./Prest.' in df_ejecutado_raw.columns else 'Matricula'
                val_col = 'Cantidad'
                price_col = 'Precio total eD'
                
                if val_col in df_ejecutado_raw.columns and price_col in df_ejecutado_raw.columns:
                    t_df = df_ejecutado_raw.copy()
                    
                    # Limpiar columnas
                    t_df[id_col] = t_df[id_col].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                    
                    cant_clean = t_df[val_col].astype(str).str.replace(',', '.', regex=False)
                    t_df['Cant_Num'] = pd.to_numeric(cant_clean, errors='coerce').fillna(0)
                    
                    price_clean = t_df[price_col].astype(str).str.replace(r'^S/\s*', '', regex=True).str.replace(',', '.', regex=False)
                    t_df['Price_Num'] = pd.to_numeric(price_clean, errors='coerce').fillna(0)
                    
                    # Agrupar por material total del año
                    df_ejec_material = t_df.groupby(id_col).agg({
                        'Cant_Num': 'sum',
                        'Price_Num': 'sum'
                    }).reset_index()
                    df_ejec_material.columns = ['Matricula_Original', 'Real_Total', 'Precio_Total']

    # --- 2. PREPARACIÓN Y MERGE DE DATOS ---
    
    # Previsiones (Agrupar por material único)
    mat_col = 'Matricula_Clean' if 'Matricula_Clean' in df_filtered.columns else 'Matricula'
    
    meses_cant = [f'Cant_{m}' for m in ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']]
    meses_val = [f'Valor_{m}' for m in ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']]
    
    agg_dict = {
        'DESCRIPCION': 'first',
        'UNIDAD': 'first',
        'P.U. s/.': 'first',
        'Hist_2025': 'sum' if 'Hist_2025' in df_filtered.columns else 'first'
    }
    
    for m in meses_cant:
        if m in df_filtered.columns: agg_dict[m] = 'sum'
    for m in meses_val:
        if m in df_filtered.columns: agg_dict[m] = 'sum'
        
    df_prev_grouped = df_filtered.groupby(mat_col).agg(agg_dict).reset_index()
    
    # Calcular totales previstos
    df_prev_grouped['Total_Prev_Cant'] = df_prev_grouped[[m for m in meses_cant if m in df_prev_grouped.columns]].sum(axis=1)
    df_prev_grouped['Total_Prev_Val'] = df_prev_grouped[[m for m in meses_val if m in df_prev_grouped.columns]].sum(axis=1)
    
    if 'Hist_2025' not in df_prev_grouped.columns:
        df_prev_grouped['Hist_2025'] = 0
        
    df_prev_grouped.rename(columns={mat_col: 'Matricula'}, inplace=True)
    
    # Cruce Principal (Previsión + Ejecutado + Saldos)
    df_master = df_prev_grouped.copy()
    
    # Unir Ejecutado
    if not df_ejec_material.empty:
        df_master = pd.merge(df_master, df_ejec_material, left_on='Matricula', right_on='Matricula_Original', how='left')
        df_master['Real_Total'] = df_master['Real_Total'].fillna(0)
        df_master['Precio_Total'] = df_master['Precio_Total'].fillna(0)
    else:
        df_master['Real_Total'] = 0
        df_master['Precio_Total'] = 0
        
    # Unir Saldos
    if not df_saldos_sheets.empty:
        df_master = pd.merge(df_master, df_saldos_sheets, on='Matricula', how='left')
        df_master['Stock'] = df_master['Stock'].fillna(0)
        df_master['Visible'] = df_master['Visible'].fillna(False)
        df_master['Anotacion'] = df_master['Anotacion'].fillna('')
        df_master['Valor_Manual'] = pd.to_numeric(df_master['Valor_Manual'], errors='coerce')
        df_master['StockQ'] = pd.to_numeric(df_master['StockQ'], errors='coerce').fillna(0)
        df_master['Decimals'] = pd.to_numeric(df_master['Decimals'], errors='coerce').fillna(0).astype(int)
        df_master['UseK'] = df_master['UseK'].fillna(False).astype(bool)
        df_master['UnitSuffix'] = df_master['UnitSuffix'].fillna('').astype(str)
    else:
        df_master['Stock'] = 0
        df_master['Visible'] = False
        df_master['Anotacion'] = ''
        df_master['Valor_Manual'] = np.nan
        df_master['StockQ'] = 0
        df_master['Decimals'] = 0
        df_master['UseK'] = False
        df_master['UnitSuffix'] = ''
        
    # Variables de UI en State
    if 'saldos_df' not in st.session_state:
        st.session_state['saldos_df'] = df_saldos_sheets

    # --- 3. PANEL DE GESTIÓN (POPOVER) ---
    col_pop, col_space = st.columns([1, 4])
    with col_pop:
        with st.popover("⚙️ Gestionar Materiales", use_container_width=True):
            st.markdown("### Buscar y Editar Stock")
            
            opciones_mat = df_master['Matricula'] + " - " + df_master['DESCRIPCION'].str[:40]
            mat_dict = dict(zip(opciones_mat, df_master['Matricula']))
            
            selected_op = st.selectbox("Buscar material:", [""] + list(opciones_mat), index=0)
            
            if selected_op and selected_op != "":
                sel_mat_id = mat_dict[selected_op]
                row_data = df_master[df_master['Matricula'] == sel_mat_id].iloc[0]
                
                unidad_txt = row_data.get('UNIDAD', 'Unid')
                pu_txt = row_data.get('P.U. s/.', 0)
                
                st.info(f"**{row_data['DESCRIPCION']}**\n\nUnidad: {unidad_txt} | P.U.: S/ {pu_txt:,.2f}")
                
                with st.form(key=f"form_stock_{sel_mat_id}"):
                    curr_stock = float(row_data['Stock'])
                    curr_visible = bool(row_data['Visible'])
                    curr_val_man = row_data['Valor_Manual'] if pd.notna(row_data['Valor_Manual']) else 0.0
                    curr_anot = str(row_data['Anotacion'])
                    curr_stockq = float(row_data['StockQ'])
                    curr_decimals = int(row_data['Decimals'])
                    curr_usek = bool(row_data['UseK'])
                    curr_suffix = str(row_data['UnitSuffix']) if str(row_data['UnitSuffix']) != 'nan' else ''
                    
                    # --- Sección: Stock Físico ---
                    st.markdown("#### 📦 Stock Físico")
                    new_stock = st.number_input(f"Stock Disponible ({unidad_txt})", value=curr_stock, min_value=0.0, step=1.0)
                    
                    is_manual = st.checkbox("Usar Valor Manual (S/.) en lugar de calcularlo del P.U.", value=pd.notna(row_data['Valor_Manual']))
                    new_val_man = st.number_input("Valor Manual (S/.)", value=float(curr_val_man) if pd.notna(row_data['Valor_Manual']) else 0.0, disabled=not is_manual)
                    
                    st.markdown("---")
                    
                    # --- Sección: StockQ y Formato ---
                    st.markdown("#### 📐 Stock Q (Descuento de Previsión)")
                    st.caption("Cantidad a descontar de la previsión 2026. La columna '2026 Prev.' mostrará Previsión - StockQ.")
                    new_stockq = st.number_input(
                        f"StockQ ({unidad_txt})", 
                        value=curr_stockq, 
                        min_value=0.0, 
                        step=1.0,
                        help="Ingresa la cantidad que deseas descontar de la previsión total de 2026."
                    )
                    
                    st.markdown("**Opciones de Formato:**")
                    col_fmt1, col_fmt2 = st.columns(2)
                    with col_fmt1:
                        new_decimals = st.slider("Decimales", min_value=0, max_value=4, value=curr_decimals, help="Cantidad de decimales a mostrar")
                    with col_fmt2:
                        new_usek = st.checkbox("Reducir a K (ej: 10,000 → 10k)", value=curr_usek)
                    
                    new_suffix = st.text_input(
                        "Sufijo de Unidad (ej: m, kg, und)", 
                        value=curr_suffix,
                        max_chars=10,
                        help="Se mostrará al final del número, ej: 1,500 m"
                    )
                    
                    st.markdown("---")
                    
                    # --- Sección: Notas ---
                    st.markdown("#### 📝 Notas")
                    # La anotación manual es independiente del cálculo automático
                    manual_note = curr_anot
                    # Si la anotación guardada empieza con el prefijo automático, separar
                    if curr_anot.startswith('Se considera'):
                        manual_note = ''
                    
                    new_anot = st.text_input("Anotación Manual (se mostrará en la columna Anotaciones)", value=manual_note)
                    new_visible = st.checkbox("Mostrar en la tabla principal", value=curr_visible)
                    
                    if st.form_submit_button("Guardar en Sheets", type="primary"):
                        # Construir anotación: nota manual se guarda en Anotacion
                        # La nota automática del cálculo se genera al vuelo en la visualización
                        final_anot = new_anot.strip()
                        
                        final_val_man = new_val_man if is_manual else ""
                        
                        # Actualizar estado local
                        s_df = st.session_state['saldos_df']
                        idx = s_df[s_df['Matricula'] == sel_mat_id].index
                        
                        new_row_data = {
                            'Matricula': sel_mat_id,
                            'Stock': new_stock,
                            'Valor_Manual': final_val_man,
                            'Visible': new_visible,
                            'Anotacion': final_anot,
                            'StockQ': new_stockq,
                            'Decimals': new_decimals,
                            'UseK': new_usek,
                            'UnitSuffix': new_suffix
                        }
                        
                        if len(idx) > 0:
                            for key, val in new_row_data.items():
                                s_df.loc[idx, key] = val
                        else:
                            new_row = pd.DataFrame([new_row_data])
                            s_df = pd.concat([s_df, new_row], ignore_index=True)
                        
                        st.session_state['saldos_df'] = s_df
                        
                        # Subir a Google Sheets en batch
                        if update_saldos_batch(s_df):
                            st.success("✅ ¡Guardado!")
                            st.rerun()

    # --- 4. PREPARAR TABLA PRINCIPAL ---
    
    # Filtrar solo visibles
    df_tabla = df_master[df_master['Visible'] == True].copy()
    
    if df_tabla.empty:
        st.info("No hay materiales marcados para mostrarse en el cuadro principal. Usa el botón 'Gestionar Materiales' para agregar algunos.")
        return
    
    # Helper para obtener sufijo limpio de cada fila
    def _clean_suffix(val):
        s = str(val) if pd.notna(val) else ''
        return '' if s == 'nan' else s
        
    # Calcular Valor S/. Stock
    df_tabla['Stock_Valor'] = df_tabla.apply(
        lambda r: r['Valor_Manual'] if pd.notna(r['Valor_Manual']) and str(r['Valor_Manual']) != '' 
                  else r['Stock'] * r['P.U. s/.'], 
        axis=1
    )
    
    # Calcular Previsión Neta (Previsión - StockQ)
    df_tabla['Prev_Neta_Cant'] = df_tabla.apply(
        lambda r: max(r['Total_Prev_Cant'] - r['StockQ'], 0) if r['StockQ'] > 0 else r['Total_Prev_Cant'],
        axis=1
    )
    df_tabla['Prev_Neta_Val'] = df_tabla.apply(
        lambda r: r['Prev_Neta_Cant'] * r['P.U. s/.'],
        axis=1
    )
    
    # Formatear TODAS las columnas de cantidad con las preferencias de cada fila
    df_tabla['Stock_Display'] = df_tabla.apply(
        lambda r: _format_value(r['Stock'], int(r['Decimals']), bool(r['UseK']), _clean_suffix(r['UnitSuffix'])),
        axis=1
    )
    df_tabla['Hist2025_Display'] = df_tabla.apply(
        lambda r: _format_value(r['Hist_2025'], int(r['Decimals']), bool(r['UseK']), _clean_suffix(r['UnitSuffix'])),
        axis=1
    )
    df_tabla['Prev_Display'] = df_tabla.apply(
        lambda r: _format_value(r['Prev_Neta_Cant'], int(r['Decimals']), bool(r['UseK']), _clean_suffix(r['UnitSuffix'])),
        axis=1
    )
    df_tabla['Emit_Display'] = df_tabla.apply(
        lambda r: _format_value(r['Real_Total'], int(r['Decimals']), bool(r['UseK']), _clean_suffix(r['UnitSuffix'])),
        axis=1
    )
    
    # Generar nota automática al vuelo para cada fila (solo si tiene StockQ)
    df_tabla['Nota_Auto'] = df_tabla.apply(
        lambda r: _build_auto_annotation(
            r['Total_Prev_Cant'], r['StockQ'], r['Prev_Neta_Cant'],
            int(r['Decimals']), bool(r['UseK']), _clean_suffix(r['UnitSuffix'])
        ) if r['StockQ'] > 0 else '',
        axis=1
    )
    
    # Columna Anotaciones: solo la nota manual del usuario
    df_tabla['Anot_Manual'] = df_tabla['Anotacion'].astype(str).apply(
        lambda x: '' if x == 'nan' or x.strip() == '' else x.strip()
    )
    
    # Armar Dataframe Final
    df_display = pd.DataFrame({
        'Material': df_tabla['Matricula'],
        'Descripción': df_tabla['DESCRIPCION'],
        'Stock': df_tabla['Stock_Display'],
        'S/.': df_tabla['Stock_Valor'],
        '2025': df_tabla['Hist2025_Display'],
        '2026 Prev.': df_tabla['Prev_Display'],
        'S/. ': df_tabla['Prev_Neta_Val'],  # Espacio para no duplicar key dict
        '2026 Emit.': df_tabla['Emit_Display'],
        'S/.  ': df_tabla['Precio_Total'],  # Dos espacios
        'Anotaciones': df_tabla['Anot_Manual']
    })
    
    # Mostrar tabla principal
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            'Stock': st.column_config.TextColumn("Stock"),
            'S/.': st.column_config.NumberColumn("S/.", format="%,.2f"),
            '2025': st.column_config.TextColumn("2025"),
            '2026 Prev.': st.column_config.TextColumn("2026 Prev.", help="Previsión neta (Previsión - StockQ)"),
            'S/. ': st.column_config.NumberColumn("S/.", format="%,.2f"),
            '2026 Emit.': st.column_config.TextColumn("2026 Emit."),
            'S/.  ': st.column_config.NumberColumn("S/.", format="%,.2f"),
            'Anotaciones': st.column_config.TextColumn("Anotaciones"),
        }
    )
    
    # --- 5. NOTAS AL PIE (cálculos automáticos + manuales) ---
    tiene_nota_auto = df_tabla[df_tabla['Nota_Auto'].str.strip() != '']
    tiene_nota_manual = df_tabla[df_tabla['Anot_Manual'].str.strip() != '']
    
    if not tiene_nota_auto.empty or not tiene_nota_manual.empty:
        st.markdown("---")
        st.markdown("### 📋 Notas")
        
        for _, row in df_tabla.iterrows():
            partes = []
            if str(row['Nota_Auto']).strip():
                partes.append(row['Nota_Auto'])
            if str(row['Anot_Manual']).strip():
                partes.append(row['Anot_Manual'])
            if partes:
                st.markdown(f"- **{row['Matricula']}**: {' | '.join(partes)}")
