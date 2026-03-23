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


def show(df, apply_filters):
    """Función principal de la página de Previsión vs Real"""

    st.title("📊 Previsión vs Consumo Real")
    st.markdown("---")

    df_filtered = apply_filters(df)
    if df_filtered.empty:
        st.warning("No hay datos con los filtros seleccionados")
        return

    st.subheader("📁 Cargar Archivo de Consumo Real")
    st.markdown("""
    <div style="background-color: #E9ECEF; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
        <p style="margin: 0;"><strong>Formato esperado del archivo:</strong></p>
        <ul style="margin: 5px 0;">
            <li>Columna de identificación: Matricula, Matrícula o DESCRIPCION</li>
            <li>Columnas mensuales: Ene, Feb, Mar, Abr, May, Jun, Jul, Ago, Sep, Oct, Nov, Dic</li>
            <li>Formato: Excel (.xlsx) o CSV</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Seleccionar archivo de consumo real:",
        type=['xlsx', 'csv'],
        help="Sube un archivo Excel o CSV con los datos de consumo real"
    )
    use_demo = st.checkbox("Usar datos de demostración (simular consumo)", value=False)

    df_real = None
    df_comparison = df_filtered.copy()
    real_mode = None
    meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    meses_prev = [f'Valor_{m}' for m in meses]
    meses_real = [f'Real_{m}' for m in meses]
    df_real_material = pd.DataFrame(columns=['DESCRIPCION'] + meses_real)

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_real = pd.read_csv(uploaded_file)
            else:
                df_real = pd.read_excel(uploaded_file)
            st.success(f"✅ Archivo cargado: {uploaded_file.name}")
            st.write(f"Filas: {len(df_real)}, Columnas: {len(df_real.columns)}")
            with st.expander("Vista previa del archivo cargado"):
                st.dataframe(df_real.head(10), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error al cargar el archivo: {e}")
            return
    elif use_demo:
        st.info("📊 Usando datos de demostración simulados")
        np.random.seed(42)
        for mes, mes_prev in zip(meses, meses_prev):
            if mes_prev in df_filtered.columns:
                df_comparison[f'Real_{mes}'] = df_filtered[mes_prev] * np.random.uniform(0.7, 1.1, len(df_filtered))
            else:
                df_comparison[f'Real_{mes}'] = 0
        df_real_material = df_comparison.groupby('DESCRIPCION', dropna=False)[meses_real].sum().reset_index()
        real_mode = 'row'
        st.success("✅ Datos de demostración generados correctamente")

    st.markdown("---")
    if not (use_demo or df_real is not None):
        st.info("👉 Carga un archivo de consumo real o activa los datos de demostración para ver las comparaciones.")
        return

    if df_real is not None and not use_demo:
        id_cols = ['Matricula', 'Matrícula', 'DESCRIPCION']
        real_id_col = next((col for col in id_cols if col in df_real.columns), None)
        if real_id_col is None:
            st.error("No se encontró una columna de identificación de material (Matricula, Matrícula o DESCRIPCION) en el archivo de consumo real.")
            return

        if 'Matricula_Clean' in df_comparison.columns and real_id_col in ['Matricula', 'Matrícula']:
            mat_to_desc = dict(zip(df_comparison['Matricula_Clean'], df_comparison['DESCRIPCION']))
            df_real[real_id_col] = (
                df_real[real_id_col]
                .astype(str)
                .str.strip()
                .replace(r'\.0$', '', regex=True)
                .map(mat_to_desc)
                .fillna(df_real[real_id_col].astype(str))
            )

        real_month_cols = [col for col in meses if col in df_real.columns]
        if not real_month_cols:
            st.error("No se encontraron columnas mensuales (Ene, Feb, Mar, etc.) en el archivo de consumo real.")
            return

        df_real_processed = df_real[[real_id_col] + real_month_cols].copy()
        df_real_processed = df_real_processed.melt(id_vars=[real_id_col], var_name='Mes_Abbr', value_name='Real_Value')
        df_real_processed['Real_Mes'] = 'Real_' + df_real_processed['Mes_Abbr']
        df_real_material = df_real_processed.pivot_table(
            index=real_id_col,
            columns='Real_Mes',
            values='Real_Value',
            aggfunc='sum',
            fill_value=0
        ).reset_index().rename(columns={real_id_col: 'DESCRIPCION'})

        for col in meses_real:
            if col not in df_real_material.columns:
                df_real_material[col] = 0
        real_mode = 'material'

    prevision_mensual = []
    real_mensual = []
    for mes_p, mes_r in zip(meses_prev, meses_real):
        prevision_mensual.append(df_comparison[mes_p].sum() if mes_p in df_comparison.columns else 0)
        real_mensual.append(df_real_material[mes_r].sum() if mes_r in df_real_material.columns else 0)

    total_prev = sum(prevision_mensual)
    total_real = sum(real_mensual)
    ejecucion = (total_real / total_prev * 100) if total_prev > 0 else 0
    desv_acumulada = []
    acum_prev = 0
    acum_real = 0
    for prev, real in zip(prevision_mensual, real_mensual):
        acum_prev += prev
        acum_real += real
        desv_acumulada.append(acum_real - acum_prev)

    tab_resumen, tab_detalle, tab_tabla = st.tabs(["Resumen Ejecutivo", "Análisis Detallado", "Tabla de Cumplimiento"])

    with tab_resumen:
        st.subheader("📈 Comparativo Mensual: Previsión vs Real")
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(name='Previsión', x=meses, y=prevision_mensual, marker_color='#2C539E'))
        fig_comp.add_trace(go.Bar(name='Real', x=meses, y=real_mensual, marker_color='#FFBE00'))
        fig_comp.update_layout(
            barmode='group',
            xaxis_title='Mes',
            yaxis_title='Valor (MS/.)',
            margin=dict(t=50, b=50, l=60, r=20),
            height=420,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        st.subheader("📊 Métricas de Ejecución")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Previsión Total", f"S/ {total_prev:,.0f}")
        with col2:
            st.metric("Ejecución Real", f"S/ {total_real:,.0f}")
        with col3:
            st.metric("Diferencia", f"S/ {total_real - total_prev:,.0f}", delta=f"{total_real - total_prev:,.0f}")
        with col4:
            st.metric("% Ejecución", f"{ejecucion:.1f}%")

        st.subheader("📉 Desviación Acumulada")
        fig_desv = go.Figure()
        fig_desv.add_trace(go.Scatter(
            x=meses,
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
            height=280,
            showlegend=False
        )
        st.plotly_chart(fig_desv, use_container_width=True)

    with tab_detalle:
        st.subheader("🔍 Análisis Detallado por Proyecto o Material")
        analysis_options = ["Material"] if real_mode == 'material' else ["Proyecto", "Material"]
        tipo_analisis = st.radio("Analizar por:", analysis_options, horizontal=True)

        if tipo_analisis == "Proyecto" and real_mode != 'material':
            proyecto_select = st.selectbox("Seleccionar Proyecto:", df_comparison['Nombre del proyecto'].unique(), key="proyecto_vs_real")
            df_proy = df_comparison[df_comparison['Nombre del proyecto'] == proyecto_select]
            prev_proy = [df_proy[c].sum() if c in df_proy.columns else 0 for c in meses_prev]
            real_proy = [df_proy[c].sum() if c in df_proy.columns else 0 for c in meses_real]

            fig_proy = go.Figure()
            fig_proy.add_trace(go.Bar(name='Previsión', x=meses, y=prev_proy, marker_color='#2C539E'))
            fig_proy.add_trace(go.Bar(name='Real', x=meses, y=real_proy, marker_color='#64AA5A'))
            fig_proy.update_layout(
                barmode='group',
                xaxis_title='Mes',
                yaxis_title='Valor (MS/.)',
                height=380,
                margin=dict(t=40, b=40, l=60, r=20)
            )
            st.plotly_chart(fig_proy, use_container_width=True)

            mat_proy = df_proy.groupby('DESCRIPCION', dropna=False).agg({
                **{mes_p: 'sum' for mes_p in meses_prev if mes_p in df_proy.columns},
                **{mes_r: 'sum' for mes_r in meses_real if mes_r in df_proy.columns}
            }).reset_index()
            mat_proy['Previsión'] = mat_proy[[m for m in meses_prev if m in mat_proy.columns]].sum(axis=1)
            mat_proy['Real'] = mat_proy[[m for m in meses_real if m in mat_proy.columns]].sum(axis=1)
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
            material_select = st.selectbox("Seleccionar Material:", df_comparison['DESCRIPCION'].dropna().unique(), key="material_vs_real")
            df_mat = df_comparison[df_comparison['DESCRIPCION'] == material_select]
            df_mat_real = df_real_material[df_real_material['DESCRIPCION'] == material_select]

            prev_mat = [df_mat[c].sum() if c in df_mat.columns else 0 for c in meses_prev]
            real_mat = [df_mat_real[c].sum() if c in df_mat_real.columns else 0 for c in meses_real]
            fig_mat = go.Figure()
            fig_mat.add_trace(go.Bar(name='Previsión', x=meses, y=prev_mat, marker_color='#2C539E'))
            fig_mat.add_trace(go.Bar(name='Real', x=meses, y=real_mat, marker_color='#64AA5A'))
            fig_mat.update_layout(
                barmode='group',
                xaxis_title='Mes',
                yaxis_title='Valor (MS/.)',
                height=350,
                margin=dict(t=40, b=40, l=60, r=20)
            )
            st.plotly_chart(fig_mat, use_container_width=True)

            uso_proy = df_mat.groupby('Nombre del proyecto').agg({
                'Total/Cantidad': 'sum',
                **{m: 'sum' for m in meses_prev if m in df_mat.columns}
            }).reset_index()
            uso_proy['Previsión'] = uso_proy[[m for m in meses_prev if m in uso_proy.columns]].sum(axis=1)
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
        st.subheader("📋 Detalle de Cumplimiento")
        detalle_base = df_comparison.groupby('Nombre del proyecto', dropna=False).sum(numeric_only=True).reset_index()
        detalle_rows = []
        for _, row in detalle_base.iterrows():
            total_prev_proyecto = row[[m for m in meses_prev if m in row]].sum()
            total_real_proyecto = row[[m for m in meses_real if m in row]].sum() if real_mode == 'row' else np.nan
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
