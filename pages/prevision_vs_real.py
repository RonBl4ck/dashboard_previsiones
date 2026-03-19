"""
Página de Previsión vs Consumo Real
Permite cargar un archivo de consumo real y comparar con la previsión
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys
sys.path.append('..')
from components.charts import (
    create_comparison_bar, create_gauge_chart, create_area_diff_chart
)


def show(df, apply_filters):
    """Función principal de la página de Previsión vs Real"""
    
    st.title("📊 Previsión vs Consumo Real")
    st.markdown("---")
    
    # Aplicar filtros
    df_filtered = apply_filters(df)
    
    if df_filtered.empty:
        st.warning("No hay datos con los filtros seleccionados")
        return
    
    # Sección de carga de archivo de consumo real
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
    
    # Datos de ejemplo para demostración
    use_demo = st.checkbox("Usar datos de demostración (simular consumo)", value=False)
    
    df_real = None
    
    # Initialize df_comparison with df_filtered. This DataFrame will hold both prevision and real data.
    df_comparison = df_filtered.copy()
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_real = pd.read_csv(uploaded_file)
            else:
                df_real = pd.read_excel(uploaded_file)
            st.success(f"✅ Archivo cargado: {uploaded_file.name}")
            st.write(f"Filas: {len(df_real)}, Columnas: {len(df_real.columns)}")
            
            with st.expander("Vista previa del archivo cargado"):
                st.dataframe(df_real.head(10), use_container_width=True)
        except Exception as e:
            st.error(f"Error al cargar el archivo: {e}")
    
    elif use_demo:
        # Generate demo data and merge it into df_comparison
        st.info("📊 Usando datos de demostración simulados")
        
        # Simular consumo real como un porcentaje de la previsión
        import numpy as np
        np.random.seed(42)
        
        meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        meses_prev = ['Valor_Ene', 'Valor_Feb', 'Valor_Mar', 'Valor_Abr', 'Valor_May', 'Valor_Jun',
                      'Valor_Jul', 'Valor_Ago', 'Valor_Sep', 'Valor_Oct', 'Valor_Nov', 'Valor_Dic']
        
        # Create a temporary DataFrame for simulated real data, using DESCRIPCION as the key
        df_simulated_real = df_filtered[['DESCRIPCION']].copy() 
        
        # Crear datos simulados (entre 70% y 110% de la previsión)
        for mes, mes_prev in zip(meses, meses_prev):
            if mes_prev in df_filtered.columns:
                factor = np.random.uniform(0.7, 1.1, len(df_filtered)) # Factor per row
                df_simulated_real[f'Real_{mes}'] = df_filtered[mes_prev] * factor
            else:
                df_simulated_real[f'Real_{mes}'] = 0 # If no prevision data, no real data
        
        # Merge simulated real data into df_comparison
        df_comparison = pd.merge(df_comparison, df_simulated_real, on='DESCRIPCION', how='left')
        st.success("✅ Datos de demostración generados correctamente")
    
    st.markdown("---")
    
    # If there are real data (loaded or simulated), show comparisons
    if use_demo or df_real is not None:
        # Process uploaded df_real if it exists and demo data is not used
        if df_real is not None and not use_demo:
        # Generar datos de demostración
            # Identify material ID column in df_real
            id_cols = ['Matricula', 'Matrícula', 'DESCRIPCION']
            real_id_col = next((col for col in id_cols if col in df_real.columns), None)

            if real_id_col is None:
                st.error("No se encontró una columna de identificación de material (Matricula, Matrícula o DESCRIPCION) en el archivo de consumo real.")
                return

            # Identify monthly columns in df_real
            meses_upload = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            real_month_cols = [col for col in meses_upload if col in df_real.columns]

            if not real_month_cols:
                st.error("No se encontraron columnas mensuales (Ene, Feb, Mar, etc.) en el archivo de consumo real.")
                return

            # Prepare df_real for merging: melt and pivot to create 'Real_Mes' columns
            df_real_processed = df_real[[real_id_col] + real_month_cols].copy()
            df_real_processed = df_real_processed.melt(id_vars=[real_id_col], var_name='Mes_Abbr', value_name='Real_Value')
            df_real_processed['Real_Mes'] = 'Real_' + df_real_processed['Mes_Abbr']
            
            # Pivot to get Real_Ene, Real_Feb, etc. columns
            df_real_pivot = df_real_processed.pivot_table(index=real_id_col, columns='Real_Mes', values='Real_Value', fill_value=0).reset_index()
            
            # Rename the ID column to 'DESCRIPCION' for merging with df_comparison
            df_real_pivot = df_real_pivot.rename(columns={real_id_col: 'DESCRIPCION'})
            
            # Merge with df_comparison. Use a left merge to keep all prevision data and add real data.
            df_comparison = pd.merge(df_comparison, df_real_pivot, on='DESCRIPCION', how='left')
            
            # Fill NaN values for newly merged 'Real_Mes' columns with 0
            for col in [f'Real_{m}' for m in meses_upload]:
                if col in df_comparison.columns:
                    df_comparison[col] = df_comparison[col].fillna(0)

        # Now, df_comparison contains 'Real_Mes' columns either from demo or uploaded data
        meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        meses_prev = ['Valor_Ene', 'Valor_Feb', 'Valor_Mar', 'Valor_Abr', 'Valor_May', 'Valor_Jun',
                      'Valor_Jul', 'Valor_Ago', 'Valor_Sep', 'Valor_Oct', 'Valor_Nov', 'Valor_Dic']
        meses_real = [f'Real_{m}' for m in meses]
        
        # Calcular totales mensuales
        prevision_mensual = []
        real_mensual = []
        
        for mes, mes_p, mes_r in zip(meses, meses_prev, meses_real):
            prev_val = df_comparison[mes_p].sum() if mes_p in df_comparison.columns else 0
            real_val = df_comparison[mes_r].sum() if mes_r in df_comparison.columns else 0
            prevision_mensual.append(prev_val)
            real_mensual.append(real_val)
        
        # Gráfico comparativo mensual
        st.subheader("📈 Comparativo Mensual: Previsión vs Real")
        
        fig_comp = go.Figure()
        
        fig_comp.add_trace(go.Bar(
            name='Previsión',
            x=meses,
            y=prevision_mensual,
            marker_color='#2C539E',
            text=[f'{v:,.0f}' for v in prevision_mensual],
            textposition='outside',
            textfont=dict(size=9)
        ))
        
        fig_comp.add_trace(go.Bar(
            name='Real',
            x=meses,
            y=real_mensual,
            marker_color='#FFBE00',
            text=[f'{v:,.0f}' for v in real_mensual],
            textposition='outside',
            textfont=dict(size=9)
        ))
        
        fig_comp.update_layout(
            barmode='group',
            xaxis_title='Mes',
            yaxis_title='Valor (MS/.)',
            margin=dict(t=50, b=50, l=60, r=20),
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        
        st.plotly_chart(fig_comp, use_container_width=True)
        
        # Métricas de ejecución
        st.subheader("📊 Métricas de Ejecución")
        
        total_prev = sum(prevision_mensual)
        total_real = sum(real_mensual)
        ejecucion = (total_real / total_prev * 100) if total_prev > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Previsión Total", f"S/ {total_prev:,.0f}")
        with col2:
            st.metric("Ejecución Real", f"S/ {total_real:,.0f}")
        with col3:
            delta = total_real - total_prev
            st.metric("Diferencia", f"S/ {delta:,.0f}", delta=f"{delta:,.0f}")
        with col4:
            st.metric("% Ejecución", f"{ejecucion:.1f}%")
        
        st.markdown("---")
        
        # Gauge de ejecución
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("🎯 Nivel de Ejecución")
            
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=ejecucion,
                title={'text': "% de Ejecución", 'font': {'size': 16, 'color': '#2C539E'}},
                gauge={
                    'axis': {'range': [None, 120], 'ticksuffix': '%'},
                    'bar': {'color': '#2C539E'},
                    'steps': [
                        {'range': [0, 50], 'color': '#A4B6D4'},
                        {'range': [50, 80], 'color': '#FFBE00'},
                        {'range': [80, 100], 'color': '#64AA5A'}
                    ],
                    'threshold': {
                        'line': {'color': '#FFBE00', 'width': 4},
                        'thickness': 0.75,
                        'value': 100
                    }
                }
            ))
            
            fig_gauge.update_layout(height=300, margin=dict(t=30, b=20, l=20, r=20))
            st.plotly_chart(fig_gauge, use_container_width=True)
        
        with col2:
            st.subheader("📉 Desviación Acumulada")
            
            # Calcular desviación acumulada
            desv_acumulada = []
            acum_prev = 0
            acum_real = 0
            
            for p, r in zip(prevision_mensual, real_mensual):
                acum_prev += p
                acum_real += r
                desv_acumulada.append(acum_real - acum_prev)
            
            fig_desv = go.Figure()
            
            fig_desv.add_trace(go.Scatter(
                x=meses,
                y=desv_acumulada,
                mode='lines+markers',
                name='Desviación Acumulada',
                line=dict(color='#FFBE00', width=3),
                marker=dict(size=10),
                fill='tozeroy',
                fillcolor='rgba(255, 190, 0, 0.2)'
            ))
            
            fig_desv.add_hline(y=0, line_dash="dash", line_color="gray")
            
            fig_desv.update_layout(
                xaxis_title='Mes',
                yaxis_title='Desviación (MS/.)',
                margin=dict(t=30, b=30, l=60, r=20),
                height=300,
                showlegend=False
            )
            
            st.plotly_chart(fig_desv, use_container_width=True)
        
        st.markdown("---")

        # ============================================
        # NUEVA SECCIÓN: ANÁLISIS POR PROYECTO O MATERIAL
        # ============================================
        st.subheader("🔍 Análisis Detallado por Proyecto o Material")
        
        # Selector de tipo de análisis
        tipo_analisis = st.radio(
            "Analizar por:",
            ["Proyecto", "Material"],
            horizontal=True
        )
        
        # Colores corporativos
        COLOR_VERDE = "#64AA5A"
        COLOR_AMARILLO = "#FFBE00"
        COLOR_AZUL_OSCURO = "#2C539E"
        COLOR_AZUL_CLARO = "#A4B6D4"
        COLOR_BLANCO = "#FBFBFB"
        
        if tipo_analisis == "Proyecto":
            # Análisis por proyecto
            proyectos_unicos = df_comparison['Nombre del proyecto'].unique()
            proyecto_select = st.selectbox(
                "Seleccionar Proyecto:",
                proyectos_unicos,
                key="proyecto_vs_real"
            )
            
            # Filtrar datos del proyecto from df_comparison
            df_proy = df_comparison[df_comparison['Nombre del proyecto'] == proyecto_select]
            
            # Calcular totales mensuales del proyecto
            prev_proy = []
            real_proy = []
            
            for mes_p, mes_r in zip(meses_prev, meses_real):
                prev_proy.append(df_proy[mes_p].sum() if mes_p in df_proy.columns else 0)
                real_proy.append(df_proy[mes_r].sum() if mes_r in df_proy.columns else 0)
            
            # KPIs del proyecto
            total_prev_proy = sum(prev_proy)
            total_real_proy = sum(real_proy)
            ejec_proy = (total_real_proy / total_prev_proy * 100) if total_prev_proy > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(f"""
                <div style="background-color: {COLOR_AZUL_OSCURO}; border-radius: 10px; padding: 15px; text-align: center;">
                    <div style="color: {COLOR_BLANCO}; font-size: 0.85rem; opacity: 0.9;">Previsión Proyecto</div>
                    <div style="color: {COLOR_BLANCO}; font-size: 1.2rem; font-weight: bold; margin-top: 5px;">S/ {total_prev_proy:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div style="background-color: {COLOR_VERDE}; border-radius: 10px; padding: 15px; text-align: center;">
                    <div style="color: {COLOR_BLANCO}; font-size: 0.85rem; opacity: 0.9;">Real Proyecto</div>
                    <div style="color: {COLOR_BLANCO}; font-size: 1.2rem; font-weight: bold; margin-top: 5px;">S/ {total_real_proy:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                # Color según ejecución
                color_ejec = COLOR_VERDE if ejec_proy >= 90 else COLOR_AMARILLO
                st.markdown(f"""
                <div style="background-color: {color_ejec}; border-radius: 10px; padding: 15px; text-align: center;">
                    <div style="color: {COLOR_AZUL_OSCURO}; font-size: 0.85rem; opacity: 0.9;">% Ejecución</div>
                    <div style="color: {COLOR_AZUL_OSCURO}; font-size: 1.2rem; font-weight: bold; margin-top: 5px;">{ejec_proy:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                n_materiales = df_proy['DESCRIPCION'].nunique()
                st.markdown(f"""
                <div style="background-color: {COLOR_AZUL_CLARO}; border-radius: 10px; padding: 15px; text-align: center;">
                    <div style="color: {COLOR_AZUL_OSCURO}; font-size: 0.85rem; opacity: 0.9;">Materiales</div>
                    <div style="color: {COLOR_AZUL_OSCURO}; font-size: 1.2rem; font-weight: bold; margin-top: 5px;">{n_materiales}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Gráfico comparativo del proyecto
            fig_proy = go.Figure()
            
            fig_proy.add_trace(go.Bar(
                name='Previsión',
                x=meses,
                y=prev_proy,
                marker_color=COLOR_AZUL_OSCURO,
                text=[f'{v:,.0f}' if v > 0 else '' for v in prev_proy],
                textposition='outside',
                textfont=dict(size=9, color=COLOR_AZUL_OSCURO)
            ))
            
            fig_proy.add_trace(go.Bar(
                name='Real',
                x=meses,
                y=real_proy,
                marker_color=COLOR_VERDE,
                text=[f'{v:,.0f}' if v > 0 else '' for v in real_proy],
                textposition='outside',
                textfont=dict(size=9, color=COLOR_VERDE)
            ))
            
            fig_proy.update_layout(
                title=dict(text=f'Previsión vs Real - {proyecto_select[:50]}', 
                          x=0.5, font=dict(size=12, color=COLOR_AZUL_OSCURO)),
                barmode='group',
                xaxis_title='Mes',
                yaxis_title='Valor (MS/.)',
                height=400,
                margin=dict(t=60, b=50, l=60, r=20),
                legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
                paper_bgcolor=COLOR_BLANCO,
                plot_bgcolor=COLOR_BLANCO
            )
            
            st.plotly_chart(fig_proy, use_container_width=True)
            
            # Top materiales del proyecto con mayor desviación
            st.markdown("#### 📦 Materiales con Mayor Desviación")
            
            mat_proy = df_proy.groupby('DESCRIPCION', dropna=False).agg({ # Added dropna=False for consistency
                'Valor materiales (MS/.)': 'sum',
                **{mes_p: 'sum' for mes_p in meses_prev if mes_p in df_proy.columns},
                **{mes_r: 'sum' for mes_r in meses_real if mes_r in df_proy.columns}
            }).reset_index()
            
            mat_proy['Total_Prev'] = mat_proy[[m for m in meses_prev if m in mat_proy.columns]].sum(axis=1)
            mat_proy['Total_Real'] = mat_proy[[m for m in meses_real if m in mat_proy.columns]].sum(axis=1)
            mat_proy['Desviacion'] = mat_proy['Total_Real'] - mat_proy['Total_Prev']
            mat_proy['Pct_Cumpl'] = (mat_proy['Total_Real'] / mat_proy['Total_Prev'] * 100).fillna(0)
            
            # Mostrar top por desviación absoluta
            mat_proy['Desv_Abs'] = mat_proy['Desviacion'].abs()
            mat_proy = mat_proy.sort_values('Desv_Abs', ascending=False).head(10)
            
            tabla_mat = mat_proy[['DESCRIPCION', 'Total_Prev', 'Total_Real', 'Desviacion', 'Pct_Cumpl']].copy()
            tabla_mat.columns = ['Material', 'Previsión', 'Real', 'Desviación', '% Cumpl.']
            tabla_mat['Previsión'] = tabla_mat['Previsión'].apply(lambda x: f"S/ {x:,.0f}")
            tabla_mat['Real'] = tabla_mat['Real'].apply(lambda x: f"S/ {x:,.0f}")
            tabla_mat['Desviación'] = tabla_mat['Desviación'].apply(lambda x: f"S/ {x:,.0f}")
            tabla_mat['% Cumpl.'] = tabla_mat['% Cumpl.'].apply(lambda x: f"{x:.1f}%")
            tabla_mat['Material'] = tabla_mat['Material'].str[:45]
            
            st.dataframe(tabla_mat, use_container_width=True, hide_index=True)
        
        else:
            # Análisis por material
            materiales_unicos = df_comparison['DESCRIPCION'].unique()
            material_select = st.selectbox(
                "Seleccionar Material:",
                materiales_unicos,
                key="material_vs_real"
            )
            
            # Filtrar datos del material from df_comparison
            df_mat = df_comparison[df_comparison['DESCRIPCION'] == material_select]
            
            # Info del material
            unidad = df_mat['UNIDAD'].iloc[0] if 'UNIDAD' in df_mat.columns and len(df_mat) > 0 else 'N/A'
            precio_unit = df_mat['P.U. s/.'].iloc[0] if 'P.U. s/.' in df_mat.columns and len(df_mat) > 0 else 0
            proyectos_involucrados = df_mat['Nombre del proyecto'].unique()
            
            st.markdown(f"**Unidad:** {unidad} | **Precio Unitario:** S/ {precio_unit:,.2f}")
            st.markdown(f"**Usado en {len(proyectos_involucrados)} proyecto(s)**")
            
            # Calcular totales mensuales del material
            prev_mat = []
            real_mat = []
            
            for mes_p, mes_r in zip(meses_prev, meses_real):
                prev_mat.append(df_mat[mes_p].sum() if mes_p in df_mat.columns else 0)
                real_mat.append(df_mat[mes_r].sum() if mes_r in df_mat.columns else 0)
            
            # KPIs del material
            total_prev_mat = sum(prev_mat)
            total_real_mat = sum(real_mat)
            ejec_mat = (total_real_mat / total_prev_mat * 100) if total_prev_mat > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"""
                <div style="background-color: {COLOR_AZUL_OSCURO}; border-radius: 10px; padding: 15px; text-align: center;">
                    <div style="color: {COLOR_BLANCO}; font-size: 0.85rem; opacity: 0.9;">Previsión Total</div>
                    <div style="color: {COLOR_BLANCO}; font-size: 1.2rem; font-weight: bold; margin-top: 5px;">S/ {total_prev_mat:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div style="background-color: {COLOR_VERDE}; border-radius: 10px; padding: 15px; text-align: center;">
                    <div style="color: {COLOR_BLANCO}; font-size: 0.85rem; opacity: 0.9;">Real Total</div>
                    <div style="color: {COLOR_BLANCO}; font-size: 1.2rem; font-weight: bold; margin-top: 5px;">S/ {total_real_mat:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                color_ejec = COLOR_VERDE if ejec_mat >= 90 else COLOR_AMARILLO
                st.markdown(f"""
                <div style="background-color: {color_ejec}; border-radius: 10px; padding: 15px; text-align: center;">
                    <div style="color: {COLOR_AZUL_OSCURO}; font-size: 0.85rem; opacity: 0.9;">% Ejecución</div>
                    <div style="color: {COLOR_AZUL_OSCURO}; font-size: 1.2rem; font-weight: bold; margin-top: 5px;">{ejec_mat:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Gráfico comparativo del material
            fig_mat = go.Figure()
            
            fig_mat.add_trace(go.Bar(
                name='Previsión',
                x=meses,
                y=prev_mat,
                marker_color=COLOR_AZUL_OSCURO
            ))
            
            fig_mat.add_trace(go.Bar(
                name='Real',
                x=meses,
                y=real_mat,
                marker_color=COLOR_VERDE
            ))
            
            fig_mat.update_layout(
                title=dict(text='Previsión vs Real - Material Seleccionado', 
                          x=0.5, font=dict(size=12, color=COLOR_AZUL_OSCURO)),
                barmode='group',
                xaxis_title='Mes',
                yaxis_title='Valor (MS/.)',
                height=350,
                margin=dict(t=50, b=50, l=60, r=20),
                legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
                paper_bgcolor=COLOR_BLANCO,
                plot_bgcolor=COLOR_BLANCO
            )
            
            st.plotly_chart(fig_mat, use_container_width=True)
            
            # Proyectos donde se usa este material
            st.markdown("#### 📋 Uso del Material por Proyecto")
            
            uso_proy = df_mat.groupby('Nombre del proyecto').agg({
                'Total/Cantidad': 'sum',
                'Valor materiales (MS/.)': 'sum',
                **{m: 'sum' for m in meses_prev if m in df_mat.columns},
                **{m: 'sum' for m in meses_real if m in df_mat.columns}
            }).reset_index()
            
            uso_proy['Total_Prev'] = uso_proy[[m for m in meses_prev if m in uso_proy.columns]].sum(axis=1)
            uso_proy['Total_Real'] = uso_proy[[m for m in meses_real if m in uso_proy.columns]].sum(axis=1)
            
            tabla_uso = uso_proy[['Nombre del proyecto', 'Total/Cantidad', 'Total_Prev', 'Total_Real']].copy()
            tabla_uso.columns = ['Proyecto', 'Cantidad', 'Previsión', 'Real']
            tabla_uso['Cantidad'] = tabla_uso['Cantidad'].apply(lambda x: f"{x:,.0f}")
            tabla_uso['Previsión'] = tabla_uso['Previsión'].apply(lambda x: f"S/ {x:,.0f}")
            tabla_uso['Real'] = tabla_uso['Real'].apply(lambda x: f"S/ {x:,.0f}")
            tabla_uso['Proyecto'] = tabla_uso['Proyecto'].str[:50]
            
            st.dataframe(tabla_uso, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Tabla de detalle
        st.subheader("📋 Detalle de Cumplimiento")
        
        detalle_data = []
        # Corrected: Use df_comparison grouped by project to get project-level totals
        for _, row in df_comparison.groupby('Nombre del proyecto', dropna=False).sum(numeric_only=True).reset_index().iterrows():
            proyecto = row['Nombre del proyecto']
            total_prev = row[[mp for mp in meses_prev if mp in row]].sum() # Sum only existing prevision columns
            total_real = row[[mr for mr in meses_real if mr in row]].sum() # Sum only existing real columns
            cumplimiento = (total_real / total_prev * 100) if total_prev > 0 else 0
            
            detalle_data.append({
                'Proyecto': proyecto,
                'Previsión Total': total_prev,
                'Real Total': total_real,
                'Diferencia': total_real - total_prev,
                '% Cumplimiento': cumplimiento
            })
        
        df_detalle = pd.DataFrame(detalle_data)
        df_detalle = df_detalle.sort_values('Previsión Total', ascending=False)
        
        # Formatear
        df_detalle['Previsión Total'] = df_detalle['Previsión Total'].apply(lambda x: f"S/ {x:,.0f}")
        df_detalle['Real Total'] = df_detalle['Real Total'].apply(lambda x: f"S/ {x:,.0f}")
        df_detalle['Diferencia'] = df_detalle['Diferencia'].apply(lambda x: f"S/ {x:,.0f}")
        df_detalle['% Cumplimiento'] = df_detalle['% Cumplimiento'].apply(lambda x: f"{x:.1f}%")
        
        st.dataframe(df_detalle, use_container_width=True, hide_index=True)
    
    else:
        # Mostrar instrucciones si no hay datos
        st.info("👆 Carga un archivo de consumo real o activa los datos de demostración para ver las comparaciones.")
        
        st.markdown("""
        ### 📋 Instrucciones para el archivo de consumo real:
        
        El archivo debe contener las siguientes columnas:
        
        | Columna | Descripción |
        |---------|-------------|
        | Matricula / Matrícula / DESCRIPCION | Identificador del material |
        | Ene, Feb, Mar, ... | Valores de consumo mensual |
        
        **Formatos aceptados:** Excel (.xlsx) o CSV
        
        **Nota:** Los nombres de las columnas deben coincidir con los de la previsión para una correcta comparación.
        """)
