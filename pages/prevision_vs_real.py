"""
Página de Previsión vs Consumo Real
Permite cargar un archivo de consumo real y comparar con la previsión
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import sys

sys.path.append('..')


def _money_column():
    return st.column_config.NumberColumn(format="S/ %.0f")


def _bar_text(values, tipo_comparacion):
    if tipo_comparacion == "Cantidad Física":
        return [f"{value:,.0f}" for value in values]
    return [f"S/ {value:,.0f}" for value in values]


@st.cache_data(ttl=3600)
def load_ejecutado():
    """Carga los datos de consumo real desde Google Sheets (EJECUTADO)"""
    import gspread
    from google.oauth2.service_account import Credentials
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open("EJECUTADO")
        # Usamos la primera hoja por defecto
        worksheet = sh.get_worksheet(0)
        data = worksheet.get(value_render_option='UNFORMATTED_VALUE')
        if not data:
            return pd.DataFrame()
            
        headers = [str(h) for h in data[0]]
        df = pd.DataFrame(data[1:], columns=headers)
        df.replace("", pd.NA, inplace=True)
        return df
    except Exception as e:
        st.error(f"Error conectando a Google Sheets (EJECUTADO): {e}")
        return None


def show(df, apply_filters):
    """Función principal de la página de Previsión vs Real"""

    st.title("📊 Previsión vs Consumo Real")
    st.markdown("---")

    df_filtered = apply_filters(df)
    if df_filtered.empty:
        st.warning("No hay datos con los filtros seleccionados")
        return

    top_left, top_right = st.columns([2, 3])
    with top_left:
        tipo_comparacion = st.radio("Métrica a comparar:", ["Valor Económico (S/.)", "Cantidad Física"], horizontal=True)

    df_real = load_ejecutado()
    use_demo = False

    with top_right:
        action_col1, action_col2, action_col3 = st.columns([2, 1.2, 1])
        with action_col1:
            st.caption("Fuente: EJECUTADO")
        with action_col2:
            if df_real is not None and not df_real.empty:
                if hasattr(st, "popover"):
                    with st.popover("Vista previa"):
                        st.dataframe(df_real.head(10), use_container_width=True, hide_index=True)
                else:
                    with st.expander("Vista previa"):
                        st.dataframe(df_real.head(10), use_container_width=True, hide_index=True)
        with action_col3:
            if st.button("🔄 Actualizar", use_container_width=True):
                load_ejecutado.clear()
                st.rerun()

    if df_real is None or df_real.empty:
        use_demo = st.checkbox("Activar simulación de demostración (por falta de datos)", value=False)

    df_comparison = df_filtered.copy()
    real_mode = None
    meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    meses_prev = [f'Valor_{m}' for m in meses]
    meses_real = [f'Real_{m}' for m in meses]
    df_real_material = pd.DataFrame(columns=['DESCRIPCION'] + meses_real)

    if tipo_comparacion == "Cantidad Física":
        meses_prev = [f'Cant_{m}' for m in meses]
    else:
        meses_prev = [f'Valor_{m}' for m in meses]

    if use_demo:
        st.caption("Modo demostración activo")
        np.random.seed(42)
        for mes, mes_prev in zip(meses, meses_prev):
            if mes_prev in df_filtered.columns:
                df_comparison[f'Real_{mes}'] = df_filtered[mes_prev] * np.random.uniform(0.7, 1.1, len(df_filtered))
            else:
                df_comparison[f'Real_{mes}'] = 0
        df_real_material = df_comparison.groupby('DESCRIPCION', dropna=False)[meses_real].sum().reset_index()
        real_mode = 'row'
        st.caption("Se generaron datos simulados para la comparación")

    st.markdown("---")
    if not (use_demo or df_real is not None):
        st.info("👉 Carga un archivo de consumo real o activa los datos de demostración para ver las comparaciones.")
        return

    if df_real is not None and not use_demo:
        # Detectar si es el formato transaccional (ej FINAL ENRIQUECIDO.xlsx)
        if 'Fecha de Asignacion' in df_real.columns and ('Mat./Prest.' in df_real.columns or 'Matricula' in df_real.columns):
            id_source_col = 'Mat./Prest.' if 'Mat./Prest.' in df_real.columns else 'Matricula'
            val_col = 'Precio total eD' if tipo_comparacion == "Valor Económico (S/.)" else 'Cantidad'
            
            if val_col not in df_real.columns:
                st.error(f"El archivo transaccional no contiene la columna '{val_col}' necesaria para esta métrica.")
                return
                
            trans_df = df_real.copy()
            # Dejamos la columna 'Fecha de Asignacion' intocable antes del if, y la parseamos mejor
            
            # --- Parseo de Fechas robusto ---
            # Las fechas en Google Sheets pueden venir como número serial (ej. 46024 para Feb 2026) o como texto
            fechas_numericas = pd.to_numeric(trans_df['Fecha de Asignacion'], errors='coerce')
            mask_seriales = fechas_numericas > 30000
            
            fechas_convertidas = pd.to_datetime(
                fechas_numericas[mask_seriales] - 2, # Ajuste para Google Sheets serial a datetime
                unit='D', 
                origin='1900-01-01'
            )
            
            text_fechas = pd.to_datetime(
                trans_df.loc[~mask_seriales, 'Fecha de Asignacion'].astype(str), 
                dayfirst=True, 
                errors='coerce'
            )
            
            trans_df['Fecha de Asignacion'] = pd.concat([fechas_convertidas, text_fechas]).sort_index()
            trans_df = trans_df.dropna(subset=['Fecha de Asignacion'])
            
            # Ajustar Diciembre 2025 a Enero 2026
            trans_df['Year'] = trans_df['Fecha de Asignacion'].dt.year
            trans_df['Month'] = trans_df['Fecha de Asignacion'].dt.month
            
            mask_dec_2025 = (trans_df['Year'] == 2025) & (trans_df['Month'] == 12)
            trans_df.loc[mask_dec_2025, 'Month'] = 1
            
            # Extraer mes 
            month_map = {1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'}
            trans_df['Mes_Abbr'] = trans_df['Month'].map(month_map)
            
            # Asegurar que la columna a sumar es numérica y limpiar formato
            cleaned_val = trans_df[val_col].astype(str).str.replace(r'^S/\s*', '', regex=True)
            # Como la coma representa decimales ahora, sustituimos comas por puntos para Python
            cleaned_val = cleaned_val.str.replace(',', '.', regex=False).str.strip()
            trans_df[val_col] = pd.to_numeric(cleaned_val, errors='coerce').fillna(0)

            # Detectar si hay columna de proyecto
            cols_proyecto_posibles = ['Codigo del Proyecto', 'Proyecto', 'Elemento PEP', 'Nombre del proyecto']
            proyecto_col_trans = next((col for col in cols_proyecto_posibles if col in trans_df.columns), None)
            
            index_cols = [id_source_col]
            if proyecto_col_trans:
                index_cols.append(proyecto_col_trans)

            # Pivotar usando suma
            df_real_pivot = trans_df.pivot_table(
                index=index_cols, 
                columns='Mes_Abbr', 
                values=val_col, 
                aggfunc='sum', 
                fill_value=0
            ).reset_index()
            
            # Renombrar para que encaje con el resto del script
            rename_dict = {id_source_col: 'Matricula'}
            if proyecto_col_trans and proyecto_col_trans != 'Codigo del Proyecto':
                rename_dict[proyecto_col_trans] = 'Codigo del Proyecto'
            df_real_pivot = df_real_pivot.rename(columns=rename_dict)
            df_real = df_real_pivot

        id_cols = ['Matricula', 'Matrícula', 'DESCRIPCION']
        real_id_col = next((col for col in id_cols if col in df_real.columns), None)
        if real_id_col is None:
            st.error("No se encontró una columna de identificación de material (Matricula, Matrícula o DESCRIPCION) en el archivo de consumo real.")
            return

        if 'Matricula_Clean' in df_comparison.columns and real_id_col in ['Matricula', 'Matrícula']:
            # Guardamos el ID original limpio para el merge por proyecto
            df_real['Matricula_Original'] = (
                df_real[real_id_col]
                .astype(str)
                .str.strip()
                .str.replace(r'\.0$', '', regex=True)
            )
            
            # El mapeo a descripción se mantiene para la vista agrupada por material
            mat_to_desc = dict(zip(df_comparison['Matricula_Clean'], df_comparison['DESCRIPCION']))
            df_real[real_id_col] = (
                df_real['Matricula_Original']
                .map(mat_to_desc)
                .fillna(df_real['Matricula_Original'])
            )

        real_month_cols = [col for col in meses if col in df_real.columns]
        if not real_month_cols:
            st.error("No se encontraron columnas mensuales (Ene, Feb, Mar, etc.) en el archivo de consumo real.")
            return

        # Columnas a conservar para el procesamiento
        keep_cols = [real_id_col] + real_month_cols
        if 'Matricula_Original' in df_real.columns:
            keep_cols.append('Matricula_Original')
            
        df_real_processed = df_real[keep_cols].copy()
        
        proyecto_col = 'Codigo del Proyecto' if 'Codigo del Proyecto' in df_real.columns else None
        id_vars = [real_id_col]
        if 'Matricula_Original' in df_real.columns:
            id_vars.append('Matricula_Original')
            
        if proyecto_col:
            id_vars.append(proyecto_col)
            # Asegurar que esté en el dataframe procesado
            df_real_processed[proyecto_col] = df_real[proyecto_col]
            
        df_real_processed = df_real_processed.melt(id_vars=id_vars, var_name='Mes_Abbr', value_name='Real_Value')
        df_real_processed['Real_Mes'] = 'Real_' + df_real_processed['Mes_Abbr']
        
        df_real_material = df_real_processed.pivot_table(
            index=real_id_col,
            columns='Real_Mes',
            values='Real_Value',
            aggfunc='sum',
            fill_value=0
        ).reset_index().rename(columns={real_id_col: 'DESCRIPCION'})

        if proyecto_col and 'Codigo del Proyecto' in df_comparison.columns:
            # Join row by row to df_comparison
            # Pivotar incluyendo Matricula_Original para el cruce si existe
            actual_pivot_index = [real_id_col, proyecto_col]
            if 'Matricula_Original' in df_real_processed.columns:
                actual_pivot_index.append('Matricula_Original')
                
            df_r = df_real_processed.pivot_table(
                index=actual_pivot_index,
                columns='Real_Mes',
                values='Real_Value',
                aggfunc='sum',
                fill_value=0
            ).reset_index()
            
            # Crear llaves de cruce robustas (Proyecto_Material)
            comp_mat_col = 'Matricula_Clean' if 'Matricula_Clean' in df_comparison.columns else 'Matricula'
            
            # Limpiamos posibles .0 en códigos de proyecto y material de la previsión
            df_comparison['temp_key'] = (
                df_comparison['Codigo del Proyecto'].astype(str).str.strip().str.upper().str.replace(r'\.0$', '', regex=True) + 
                "_" + 
                df_comparison[comp_mat_col].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            )
            
            # En los reales, usamos la columna 'Matricula_Original' que ya guardamos limpia
            # o el ID directo si no existe esa columna
            real_mat_id_col = 'Matricula_Original' if 'Matricula_Original' in df_r.columns else real_id_col
            df_r['temp_key'] = (
                df_r[proyecto_col].astype(str).str.strip().str.upper().str.replace(r'\.0$', '', regex=True) + 
                "_" + 
                df_r[real_mat_id_col].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            )
            
            # Use only one line per project-material to store actuals so we don't duplicate on pivot/sum
            first_idx = df_comparison.groupby('temp_key').head(1).index
            
            for m in meses_real:
                if m not in df_comparison.columns:
                    df_comparison[m] = 0.0
                if m in df_r.columns:
                    map_dict = dict(zip(df_r['temp_key'], df_r[m]))
                    df_comparison.loc[first_idx, m] = df_comparison.loc[first_idx, 'temp_key'].map(map_dict).fillna(0)
            
            df_comparison.drop(columns=['temp_key'], inplace=True)
            real_mode = 'row'
        else:
            real_mode = 'material'

    prevision_mensual = []
    real_mensual = []
    meses_con_datos = []   # solo meses que tienen datos reales

    for mes, mes_p, mes_r in zip(meses, meses_prev, meses_real):
        val_real = df_real_material[mes_r].sum() if mes_r in df_real_material.columns else 0
        val_prev = df_comparison[mes_p].sum() if mes_p in df_comparison.columns else 0
        # Solo incluir meses que aparezcan en el archivo real (col presente y con algún valor)
        if mes_r in df_real_material.columns and val_real >= 0:
            meses_con_datos.append(mes)
            prevision_mensual.append(val_prev)
            real_mensual.append(val_real)

    # Si no se detectaron meses (demo sin pivote), caer al modo original
    if not meses_con_datos:
        meses_con_datos = meses
        prevision_mensual = [df_comparison[mp].sum() if mp in df_comparison.columns else 0 for mp in meses_prev]
        real_mensual = [df_real_material[mr].sum() if mr in df_real_material.columns else 0 for mr in meses_real]

    # meses_prev y meses_real acotados a los meses con datos
    meses_prev_activos = [f'Valor_{m}' for m in meses_con_datos]
    meses_real_activos = [f'Real_{m}' for m in meses_con_datos]

    total_prev = sum(prevision_mensual)
    total_real = sum(real_mensual)
    
    # Calcular previsión de todo el año para la nueva métrica
    total_prev_anual = 0
    for m in meses_prev:
        if m in df_comparison.columns:
            total_prev_anual += df_comparison[m].sum()

    ejecucion = (total_real / total_prev * 100) if total_prev > 0 else 0
    ejecucion_anual = (total_real / total_prev_anual * 100) if total_prev_anual > 0 else 0
    
    desv_acumulada = []
    acum_prev = 0
    acum_real = 0
    for prev, real in zip(prevision_mensual, real_mensual):
        acum_prev += prev
        acum_real += real
        desv_acumulada.append(acum_real - acum_prev)


    tab_resumen, tab_detalle, tab_tabla = st.tabs(["Resumen Ejecutivo", "Análisis Detallado", "Tabla de Cumplimiento"])

    with tab_resumen:
        st.subheader("📊 Métricas de Ejecución")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Previsión (Activo)", f"S/ {total_prev:,.0f}", help="Suma de previsión solo de los meses que tienen consumo real")
        with col2:
            st.metric("Ejecución Real", f"S/ {total_real:,.0f}")
        with col3:
            st.metric("Diferencia", f"S/ {total_real - total_prev:,.0f}", delta=f"{total_real - total_prev:,.0f}")
        col4, col5 = st.columns(2)
        with col4:
            st.metric("% Ejec. (Mensual)", f"{ejecucion:.1f}%", help="Porcentaje de ejecución vs previsión de los meses activos")
        with col5:
            st.metric("% Ejec. (Anual)", f"{ejecucion_anual:.1f}%", help=f"Ejecución total vs Previsión de Todo el Año (S/ {total_prev_anual:,.0f})")

        col_chart, col_desv = st.columns([2, 1])
        with col_chart:
            st.subheader("📈 Comparativo Mensual")
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                name='Previsión',
                x=meses_con_datos,
                y=prevision_mensual,
                marker_color='#2C539E',
                text=_bar_text(prevision_mensual, tipo_comparacion),
                textposition='outside'
            ))
            fig_comp.add_trace(go.Bar(
                name='Real',
                x=meses_con_datos,
                y=real_mensual,
                marker_color='#FFBE00',
                text=_bar_text(real_mensual, tipo_comparacion),
                textposition='outside'
            ))
            fig_comp.update_layout(
                barmode='group',
                xaxis_title='Mes',
                yaxis_title='Valor (MS/.)',
                margin=dict(t=50, b=50, l=60, r=20),
                height=430,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                uniformtext_minsize=8,
                uniformtext_mode='hide'
            )
            st.plotly_chart(fig_comp, use_container_width=True)

        with col_desv:
            st.subheader("📉 Desviación")
            st.caption("Diferencia acumulada entre consumo real y previsión")
            fig_desv = go.Figure()
            fig_desv.add_trace(go.Scatter(
                x=meses_con_datos,
                y=desv_acumulada,
                mode='lines+markers',
                line=dict(color='#E94F37', width=3),
                marker=dict(size=8),
                fill='tozeroy',
                fillcolor='rgba(233, 79, 55, 0.15)'
            ))
            fig_desv.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_desv.update_layout(
                xaxis_title='Mes',
                yaxis_title='Desviación (MS/.)',
                margin=dict(t=30, b=30, l=60, r=20),
                height=330,
                showlegend=False
            )
            st.plotly_chart(fig_desv, use_container_width=True)

    with tab_detalle:
        st.subheader("🔍 Análisis Detallado")
        analysis_options = ["Material"] if real_mode == 'material' else ["Proyecto", "Material"]
        filter_col1, filter_col2 = st.columns([1, 2])
        with filter_col1:
            tipo_analisis = st.radio("Analizar por:", analysis_options, horizontal=True)

        if tipo_analisis == "Proyecto" and real_mode != 'material':
            with filter_col2:
                proyecto_select = st.selectbox("Seleccionar Proyecto:", df_comparison['Nombre del proyecto'].unique(), key="proyecto_vs_real")
            df_proy = df_comparison[df_comparison['Nombre del proyecto'] == proyecto_select]
            prev_proy = [df_proy[c].sum() if c in df_proy.columns else 0 for c in meses_prev_activos]
            real_proy = [df_proy[c].sum() if c in df_proy.columns else 0 for c in meses_real_activos]

            fig_proy = go.Figure()
            fig_proy.add_trace(go.Bar(
                name='Previsión',
                x=meses_con_datos,
                y=prev_proy,
                marker_color='#2C539E',
                text=_bar_text(prev_proy, tipo_comparacion),
                textposition='outside'
            ))
            fig_proy.add_trace(go.Bar(
                name='Real',
                x=meses_con_datos,
                y=real_proy,
                marker_color='#64AA5A',
                text=_bar_text(real_proy, tipo_comparacion),
                textposition='outside'
            ))
            fig_proy.update_layout(
                barmode='group',
                xaxis_title='Mes',
                yaxis_title='Valor (MS/.)',
                height=410,
                margin=dict(t=40, b=40, l=60, r=20),
                uniformtext_minsize=8,
                uniformtext_mode='hide'
            )
            st.plotly_chart(fig_proy, use_container_width=True)

            st.caption("Top materiales con mayor desviación dentro del proyecto seleccionado")
            mat_proy = df_proy.groupby('DESCRIPCION', dropna=False).agg({
                **{mes_p: 'sum' for mes_p in meses_prev_activos if mes_p in df_proy.columns},
                **{mes_r: 'sum' for mes_r in meses_real_activos if mes_r in df_proy.columns}
            }).reset_index()
            mat_proy['Previsión'] = mat_proy[[m for m in meses_prev_activos if m in mat_proy.columns]].sum(axis=1)
            mat_proy['Real'] = mat_proy[[m for m in meses_real_activos if m in mat_proy.columns]].sum(axis=1)
            mat_proy['Desviación'] = mat_proy['Real'] - mat_proy['Previsión']
            mat_proy['% Cumpl.'] = np.where(mat_proy['Previsión'] > 0, (mat_proy['Real'] / mat_proy['Previsión']) * 100, np.nan)
            tabla_mat = mat_proy[['DESCRIPCION', 'Previsión', 'Real', 'Desviación', '% Cumpl.']].sort_values('Desviación', key=np.abs, ascending=False).head(10).copy()
            tabla_mat.columns = ['Material', 'Previsión', 'Real', 'Desviación', '% Cumpl.']
            tabla_mat['Material'] = tabla_mat['Material'].str[:45]
            st.dataframe(
                tabla_mat,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Previsión': _money_column(),
                    'Real': _money_column(),
                    'Desviación': _money_column(),
                    '% Cumpl.': st.column_config.NumberColumn(format="%.1f%%")
                }
            )
        else:
            with filter_col2:
                material_select = st.selectbox("Seleccionar Material:", df_comparison['DESCRIPCION'].dropna().unique(), key="material_vs_real")
            df_mat = df_comparison[df_comparison['DESCRIPCION'] == material_select]
            df_mat_real = df_real_material[df_real_material['DESCRIPCION'] == material_select]

            prev_mat = [df_mat[c].sum() if c in df_mat.columns else 0 for c in meses_prev_activos]
            real_mat = [df_mat_real[c].sum() if c in df_mat_real.columns else 0 for c in meses_real_activos]
            fig_mat = go.Figure()
            fig_mat.add_trace(go.Bar(
                name='Previsión',
                x=meses_con_datos,
                y=prev_mat,
                marker_color='#2C539E',
                text=_bar_text(prev_mat, tipo_comparacion),
                textposition='outside'
            ))
            fig_mat.add_trace(go.Bar(
                name='Real',
                x=meses_con_datos,
                y=real_mat,
                marker_color='#64AA5A',
                text=_bar_text(real_mat, tipo_comparacion),
                textposition='outside'
            ))
            fig_mat.update_layout(
                barmode='group',
                xaxis_title='Mes',
                yaxis_title='Valor (MS/.)',
                height=390,
                margin=dict(t=40, b=40, l=60, r=20),
                uniformtext_minsize=8,
                uniformtext_mode='hide'
            )
            st.plotly_chart(fig_mat, use_container_width=True)

            st.caption("Distribución del material seleccionado por proyecto")
            uso_proy = df_mat.groupby('Nombre del proyecto').agg({
                'Total/Cantidad': 'sum',
                **{m: 'sum' for m in meses_prev_activos if m in df_mat.columns}
            }).reset_index()
            uso_proy['Previsión'] = uso_proy[[m for m in meses_prev_activos if m in uso_proy.columns]].sum(axis=1)
            uso_proy['Real'] = np.nan
            tabla_uso = uso_proy[['Nombre del proyecto', 'Total/Cantidad', 'Previsión', 'Real']].copy()
            tabla_uso.columns = ['Proyecto', 'Cantidad', 'Previsión', 'Real']
            tabla_uso['Proyecto'] = tabla_uso['Proyecto'].str[:50]
            st.dataframe(
                tabla_uso,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Cantidad': st.column_config.NumberColumn(format="%.0f"),
                    'Previsión': _money_column(),
                    'Real': _money_column()
                }
            )

    with tab_tabla:
        st.subheader("📋 Tabla de Cumplimiento")
        st.caption("Cumplimiento por proyecto, ordenado por previsión total")
        detalle_base = df_comparison.groupby('Nombre del proyecto', dropna=False).sum(numeric_only=True).reset_index()
        detalle_rows = []
        for _, row in detalle_base.iterrows():
            total_prev_proyecto = row[[m for m in meses_prev_activos if m in row]].sum()
            total_real_proyecto = row[[m for m in meses_real_activos if m in row]].sum() if real_mode == 'row' else np.nan
            detalle_rows.append({
                'Proyecto': row['Nombre del proyecto'],
                'Previsión Total': total_prev_proyecto,
                'Real Total': total_real_proyecto,
                'Diferencia': total_real_proyecto - total_prev_proyecto if pd.notna(total_real_proyecto) else np.nan,
                '% Cumplimiento': (total_real_proyecto / total_prev_proyecto * 100) if pd.notna(total_real_proyecto) and total_prev_proyecto > 0 else np.nan
            })
        df_detalle = pd.DataFrame(detalle_rows).sort_values('Previsión Total', ascending=False)
        st.dataframe(
            df_detalle,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Previsión Total': _money_column(),
                'Real Total': _money_column(),
                'Diferencia': _money_column(),
                '% Cumplimiento': st.column_config.NumberColumn(format="%.1f%%")
            }
        )
