"""
Página de Saldos y Ajustes
Permite cargar saldos del año anterior y calcular necesidades netas
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import sys
sys.path.append('..')


def show(df, apply_filters):
    """Función principal de la página de Saldos y Ajustes"""
    
    st.title("📦 Saldos y Ajustes")
    st.markdown("---")
    
    # Aplicar filtros
    df_filtered = apply_filters(df)
    
    if df_filtered.empty:
        st.warning("No hay datos con los filtros seleccionados")
        return
    
    # Introducción
    st.markdown("""
    <div style="background-color: #E9ECEF; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
        <p style="margin: 0;">Esta sección permite integrar los <strong>saldos de materiales del año anterior</strong> 
        con la previsión actual, calculando las <strong>necesidades netas</strong> de compra.</p>
        <p style="margin: 10px 0 0 0;"><strong>Fórmula:</strong> Necesidad Neta = Previsión 2026 - Saldo 2025</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sección de carga de saldos
    st.subheader("📁 Cargar Archivo de Saldos")
    
    st.markdown("""
    **Formato esperado del archivo:**
    - Columna de identificación: Matricula, Matrícula o DESCRIPCION
    - Columna de saldo: Saldo, Stock, Cantidad o Cantidad_Disponible
    - Formato: Excel (.xlsx) o CSV
    """)
    
    uploaded_file = st.file_uploader(
        "Seleccionar archivo de saldos:",
        type=['xlsx', 'csv'],
        help="Sube un archivo Excel o CSV con los saldos de materiales del año anterior"
    )
    
    # Opción de usar datos de demostración
    use_demo = st.checkbox("Usar datos de demostración (simular saldos)", value=False)
    
    df_saldos = None
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_saldos = pd.read_csv(uploaded_file)
            else:
                df_saldos = pd.read_excel(uploaded_file)
            
            st.success(f"✅ Archivo cargado: {uploaded_file.name}")
            st.write(f"Filas: {len(df_saldos)}, Columnas: {len(df_saldos.columns)}")
            
            with st.expander("Vista previa del archivo de saldos"):
                st.dataframe(df_saldos.head(10), use_container_width=True)
                
        except Exception as e:
            st.error(f"Error al cargar el archivo: {e}")
    
    elif use_demo:
        st.info("📊 Usando datos de demostración simulados")
        
        # Simular saldos como un porcentaje aleatorio de la previsión
        np.random.seed(42)
        
        # Obtener materiales únicos
        materiales = df_filtered.groupby('DESCRIPCION').agg({
            'Total/Cantidad': 'sum',
            'Valor materiales (MS/.)': 'sum',
            'P.U. s/.': 'first'
        }).reset_index()
        
        # Simular saldos (entre 5% y 30% de la previsión)
        materiales['Saldo_Cantidad'] = materiales['Total/Cantidad'] * np.random.uniform(0.05, 0.3, len(materiales))
        materiales['Saldo_Valor'] = materiales['Saldo_Cantidad'] * materiales['P.U. s/.']
        
        df_saldos = materiales[['DESCRIPCION', 'Saldo_Cantidad', 'Saldo_Valor']].copy()
        
        st.success(f"✅ Saldos simulados para {len(df_saldos)} materiales")
    
    st.markdown("---")
    
    # Si hay saldos (cargados o simulados), mostrar análisis
    if df_saldos is not None:
        
        # Identificar columna de material
        col_material = None
        for col in ['DESCRIPCION', 'Matricula', 'Matrícula', 'Material']:
            if col in df_saldos.columns:
                col_material = col
                break
        
        # Identificar columna de saldo
        col_saldo = None
        for col in ['Saldo', 'Stock', 'Cantidad', 'Cantidad_Disponible', 'Saldo_Cantidad']:
            if col in df_saldos.columns:
                col_saldo = col
                break
        
        if col_material is None:
            st.error("No se encontró columna de identificación de material")
            return
        
        if col_saldo is None:
            st.error("No se encontró columna de saldo/cantidad")
            return
        
        # Preparar datos de previsión por material
        prevision_material = df_filtered.groupby('DESCRIPCION').agg({
            'Total/Cantidad': 'sum',
            'Valor materiales (MS/.)': 'sum',
            'P.U. s/.': 'first',
            'UNIDAD': 'first'
        }).reset_index()
        
        # Unir prevision_material con saldos (cargados o simulados)
        if use_demo:
            # If using demo, df_saldos already has 'DESCRIPCION' and 'Saldo_Cantidad'
            df_merged = prevision_material.merge(
                df_saldos[['DESCRIPCION', 'Saldo_Cantidad']],
                on='DESCRIPCION',
                how='left'
            ).rename(columns={'Saldo_Cantidad': 'Saldo'})
        else:
            # For uploaded file, ensure col_material is 'DESCRIPCION' for merge
            # Rename the identified material column in df_saldos to 'DESCRIPCION' for consistent merging
            df_saldos_temp = df_saldos.rename(columns={col_material: 'DESCRIPCION'})
            df_merged = prevision_material.merge(
                df_saldos_temp[['DESCRIPCION', col_saldo]],
                on='DESCRIPCION',
                how='left'
            ).rename(columns={col_saldo: 'Saldo'}) # Rename the identified saldo column to 'Saldo'
        
        # Calcular necesidades netas
        df_merged['Saldo'] = df_merged['Saldo'].fillna(0)
        df_merged['Necesidad_Neta'] = df_merged['Total/Cantidad'] - df_merged['Saldo']
        df_merged['Necesidad_Neta'] = df_merged['Necesidad_Neta'].clip(lower=0)  # No negativos
        
        # Calcular valores
        df_merged['Valor_Saldo'] = df_merged['Saldo'] * df_merged['P.U. s/.']
        df_merged['Valor_Necesidad'] = df_merged['Necesidad_Neta'] * df_merged['P.U. s/.']
        
        # ============================================
        # RESUMEN GENERAL
        # ============================================
        st.subheader("📊 Resumen General")
        
        total_prevision = df_merged['Valor materiales (MS/.)'].sum()
        total_saldo = df_merged['Valor_Saldo'].sum()
        total_necesidad = df_merged['Valor_Necesidad'].sum()
        ahorro_potencial = total_saldo
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Previsión Total",
                f"S/ {total_prevision:,.0f}"
            )
        
        with col2:
            st.metric(
                "Saldos Disponibles",
                f"S/ {total_saldo:,.0f}"
            )
        
        with col3:
            st.metric(
                "Necesidad Neta",
                f"S/ {total_necesidad:,.0f}",
                delta=f"-{ahorro_potencial:,.0f}"
            )
        
        with col4:
            pct_cobertura = (total_saldo / total_prevision * 100) if total_prevision > 0 else 0
            st.metric(
                "% Cobertura con Saldos",
                f"{pct_cobertura:.1f}%"
            )
        
        st.markdown("---")
        
        # ============================================
        # GRÁFICO DE DISTRIBUCIÓN
        # ============================================
        st.subheader("📈 Distribución: Previsión vs Saldo vs Necesidad Neta")
        
        # Top 15 materiales por valor
        df_top = df_merged.nlargest(15, 'Valor materiales (MS/.)')
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Previsión',
            y=df_top['DESCRIPCION'].str[:40],
            x=df_top['Valor materiales (MS/.)'],
            orientation='h',
            marker_color='#1B3F66'
        ))
        
        fig.add_trace(go.Bar(
            name='Saldo Disponible',
            y=df_top['DESCRIPCION'].str[:40],
            x=df_top['Valor_Saldo'],
            orientation='h',
            marker_color='#2ECC71'
        ))
        
        fig.add_trace(go.Bar(
            name='Necesidad Neta',
            y=df_top['DESCRIPCION'].str[:40],
            x=df_top['Valor_Necesidad'],
            orientation='h',
            marker_color='#E94F37'
        ))
        
        fig.update_layout(
            barmode='group',
            xaxis_title='Valor (MS/.)',
            margin=dict(t=30, b=30, l=250, r=20),
            height=600,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # ============================================
        # MATERIALES CON EXCEDENTES
        # ============================================
        st.subheader("✅ Materiales con Saldo Suficiente (Excedentes)")
        
        df_excedentes = df_merged[df_merged['Saldo'] >= df_merged['Total/Cantidad']].copy()
        df_excedentes['Excedente_Cantidad'] = df_excedentes['Saldo'] - df_excedentes['Total/Cantidad']
        df_excedentes['Excedente_Valor'] = df_excedentes['Excedente_Cantidad'] * df_excedentes['P.U. s/.']
        df_excedentes = df_excedentes.sort_values('Excedente_Valor', ascending=False)
        
        if len(df_excedentes) > 0:
            st.success(f"🎉 Se encontraron {len(df_excedentes)} materiales con excedentes")
            
            total_excedente = df_excedentes['Excedente_Valor'].sum()
            st.info(f"**Valor total de excedentes: S/ {total_excedente:,.0f}**")
            
            # Gráfico de excedentes
            fig_exc = px.bar(
                df_excedentes.head(10),
                x='Excedente_Valor',
                y=df_excedentes.head(10)['DESCRIPCION'].str[:40],
                orientation='h',
                color='Excedente_Valor',
                color_continuous_scale='Greens',
                title='Top 10 Materiales con Mayor Excedente'
            )
            
            fig_exc.update_layout(
                xaxis_title='Valor Excedente (MS/.)',
                yaxis_title='',
                margin=dict(t=50, b=30, l=250, r=20),
                height=400
            )
            
            st.plotly_chart(fig_exc, use_container_width=True)
            
            # Tabla de excedentes
            tabla_exc = df_excedentes[['DESCRIPCION', 'Total/Cantidad', 'Saldo', 'Excedente_Cantidad', 'Excedente_Valor']].copy()
            tabla_exc.columns = ['Material', 'Previsión', 'Saldo', 'Excedente', 'Valor Excedente']
            
            for col in ['Previsión', 'Saldo', 'Excedente']:
                tabla_exc[col] = tabla_exc[col].apply(lambda x: f"{x:,.0f}")
            tabla_exc['Valor Excedente'] = tabla_exc['Valor Excedente'].apply(lambda x: f"S/ {x:,.0f}")
            
            with st.expander("📋 Ver detalle de materiales con excedentes"):
                st.dataframe(tabla_exc, use_container_width=True, hide_index=True)
        else:
            st.info("No hay materiales con excedentes")
        
        st.markdown("---")
        
        # ============================================
        # MATERIALES CON DÉFICIT
        # ============================================
        st.subheader("⚠️ Materiales con Déficit (Requieren Compra)")
        
        df_deficit = df_merged[df_merged['Necesidad_Neta'] > 0].copy()
        df_deficit = df_deficit.sort_values('Valor_Necesidad', ascending=False)
        
        if len(df_deficit) > 0:
            st.warning(f"📊 Se requieren comprar {len(df_deficit)} materiales diferentes")
            
            total_deficit = df_deficit['Valor_Necesidad'].sum()
            st.info(f"**Valor total de compras necesarias: S/ {total_deficit:,.0f}**")
            
            # Gráfico de déficit
            fig_def = px.bar(
                df_deficit.head(15),
                x='Valor_Necesidad',
                y=df_deficit.head(15)['DESCRIPCION'].str[:40],
                orientation='h',
                color='Valor_Necesidad',
                color_continuous_scale='Reds',
                title='Top 15 Materiales con Mayor Necesidad de Compra'
            )
            
            fig_def.update_layout(
                xaxis_title='Valor Necesidad Neta (MS/.)',
                yaxis_title='',
                margin=dict(t=50, b=30, l=250, r=20),
                height=500
            )
            
            st.plotly_chart(fig_def, use_container_width=True)
        else:
            st.success("🎉 ¡Todos los materiales tienen saldo suficiente!")
        
        st.markdown("---")
        
        # ============================================
        # TABLA COMPLETA
        # ============================================
        st.subheader("📋 Detalle Completo de Materiales")
        
        # Preparar tabla
        tabla_completa = df_merged[['DESCRIPCION', 'UNIDAD', 'Total/Cantidad', 'Saldo', 
                                    'Necesidad_Neta', 'P.U. s/.', 'Valor materiales (MS/.)', 
                                    'Valor_Saldo', 'Valor_Necesidad']].copy()
        
        tabla_completa.columns = ['Material', 'Unidad', 'Previsión Cant.', 'Saldo Cant.', 
                                  'Necesidad Neta', 'P.U. (S/.)', 'Valor Previsión', 
                                  'Valor Saldo', 'Valor Necesidad']
        
        # Formatear
        for col in ['Previsión Cant.', 'Saldo Cant.', 'Necesidad Neta']:
            tabla_completa[col] = tabla_completa[col].apply(lambda x: f"{x:,.0f}")
        
        tabla_completa['P.U. (S/.)'] = tabla_completa['P.U. (S/.)'].apply(lambda x: f"{x:,.2f}")
        
        for col in ['Valor Previsión', 'Valor Saldo', 'Valor Necesidad']:
            tabla_completa[col] = tabla_completa[col].apply(lambda x: f"S/ {x:,.0f}")
        
        # Agregar indicador de estado
        def indicar_estado(row):
            try:
                necesidad = float(row['Necesidad Neta'].replace(',', ''))
                saldo = float(row['Saldo Cant.'].replace(',', ''))
                if saldo >= float(row['Previsión Cant.'].replace(',', '')):
                    return '✅ Excedente'
                elif necesidad > 0:
                    return '⚠️ Requiere Compra'
                else:
                    return '✅ Cubierto'
            except:
                return '-'
        
        tabla_completa['Estado'] = tabla_completa.apply(indicar_estado, axis=1)
        
        st.dataframe(tabla_completa, use_container_width=True, hide_index=True)
        
        # Botón de exportar
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("📥 Exportar Análisis a Excel", use_container_width=True):
                st.success("✅ Funcionalidad de exportación lista para implementar")
                st.info("En una implementación completa, esto exportaría el análisis a Excel con las columnas de necesidades netas.")
    
    else:
        # Mostrar instrucciones si no hay datos
        st.info("👆 Carga un archivo de saldos o activa los datos de demostración para ver el análisis.")
        
        st.markdown("""
        ### 📋 Beneficios de Integrar Saldos:
        
        1. **Optimización de Compras**: Identificar qué materiales ya tienen stock disponible
        2. **Ahorro de Costos**: Evitar compras innecesarias de materiales con excedentes
        3. **Planificación Eficiente**: Calcular las necesidades reales de adquisición
        4. **Identificación de Excedentes**: Materiales que pueden redistribuirse a otros proyectos
        
        ### 🔄 Flujo de Trabajo Sugerido:
        
        1. Cargar archivo de saldos del año anterior
        2. Revisar materiales con excedentes
        3. Identificar materiales con déficit
        4. Exportar lista de compras necesarias
        """)


# ============================================
# FUNCIÓN DE EXPORTACIÓN (para implementar)
# ============================================
def exportar_analisis(df_merged):
    """
    Función para exportar el análisis a Excel
    (Para implementación futura)
    """
    from io import BytesIO
    import openpyxl
    
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_merged.to_excel(writer, sheet_name='Análisis Saldos', index=False)
    
    output.seek(0)
    return output
