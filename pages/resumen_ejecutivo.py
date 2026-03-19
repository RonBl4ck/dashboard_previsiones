"""
Página de Resumen Ejecutivo
Muestra KPIs principales y gráficos de distribución
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
sys.path.append('..')
from components.charts import create_donut_chart, create_line_chart
from components.kpis import show_executive_summary_kpis

def _create_materials_donut_chart(mat_filtrados, filtro_unidad):
    """Crea el gráfico de dona para el análisis de materiales con lógica de 'Top N + Otros'."""
    top_n = 15
    mat_grafico = mat_filtrados.head(top_n).copy()

    if len(mat_filtrados) > top_n:
        otros = pd.DataFrame({
            'Material': ['Otros materiales'],
            'Cantidad': [mat_filtrados.iloc[top_n:]['Cantidad'].sum()],
            'Valor': [mat_filtrados.iloc[top_n:]['Valor'].sum()],
            'Unidad': [filtro_unidad if filtro_unidad != 'Todos' else 'Varios'],
            'Proyectos': [mat_filtrados.iloc[top_n:]['Proyectos'].sum()]
        })
        mat_grafico = pd.concat([mat_grafico, otros], ignore_index=True)

    fig_dona = go.Figure(go.Pie(
        labels=mat_grafico['Material'].str[:40],
        values=mat_grafico['Valor'],
        hole=0.55,
        marker_colors=['#2C539E', '#64AA5A', '#FFBE00', '#A4B6D4', '#5A8CD4', 
                       '#8BC34A', '#FFD54F', '#C5D6E8', '#8AAEE0', '#A9D36A',
                       '#FFE082', '#E8EEF5', '#B0C4DE', '#C8E6C9', '#FFF9C4'],
        textinfo='percent',
        textposition='outside',
        textfont=dict(size=10),
        hovertemplate='<b>%{label}</b><br>Valor: S/ %{value:,.0f}<br>%{percent}<extra></extra>'
    ))

    titulo = f'Distribución de Valor - {filtro_unidad}' if filtro_unidad != 'Todos' else 'Distribución de Valor - Todos los Materiales'

    fig_dona.update_layout(
        title=dict(text=titulo, x=0.5, font=dict(size=14, color='#2C539E')),
        height=450,
        margin=dict(t=50, b=20, l=20, r=20),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5, font=dict(size=9))
    )
    return fig_dona

def show(df, apply_filters):
    """Función principal de la página de Resumen Ejecutivo"""
    
    st.title("📊 Resumen Ejecutivo")
    st.markdown("---")
    
    df_filtered = apply_filters(df)
    
    if df_filtered.empty:
        st.warning("No hay datos con los filtros seleccionados")
        return
    
    st.subheader("📈 Indicadores Principales")
    show_executive_summary_kpis(df_filtered)
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Resumen General", "📦 Análisis de Materiales", "📋 Resumen por Proyecto"])

    # Pestaña 1: Resumen General
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏛️ Distribución por Sección")
            fig_seccion = create_donut_chart(
                df_filtered, 
                column='Seccion',
                title='Distribución del Presupuesto por Sección',
                value_column='Valor_Anual'
            )
            st.plotly_chart(fig_seccion, use_container_width=True)
        
        with col2:
            st.subheader("⚡ Distribución por Área")
            fig_area = create_donut_chart(
                df_filtered, 
                column='AREA',
                title='Distribución del Presupuesto por Área Técnica',
                value_column='Valor_Anual'
            )
            st.plotly_chart(fig_area, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("📅 Evolución Mensual de la Previsión")
        
        # Lógica mejorada para meses
        month_map = {'Ene': 1, 'Feb': 2, 'Mar': 3, 'Abr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Ago': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dic': 12}
        
        valor_cols = [col for col in df_filtered.columns if col.startswith('Valor_')]
        monthly_values = {}
        
        for col in valor_cols:
            month_abbr = col.split('_')[1]
            if month_abbr in month_map:
                monthly_values[month_abbr] = df_filtered[col].sum()
        
        # Ordenar por mes
        sorted_months = sorted(monthly_values.keys(), key=lambda m: month_map[m])
        sorted_values = [monthly_values[m] for m in sorted_months]
        
        fig_line = create_line_chart(
            df=df_filtered,
            months=sorted_months,
            values=sorted_values,
            title='Evolución del Presupuesto Mensual 2026',
            y_label='Valor (MS/.)'
        )
        st.plotly_chart(fig_line, use_container_width=True)

    # Pestaña 2: Análisis de Materiales
    with tab2:
        df_mat = df_filtered.copy()
        df_mat['UNIDAD_NORM'] = df_mat['UNIDAD'].str.upper().replace({
            'M': 'Metros', 'METROS': 'Metros',
            'UN': 'Unidades', 'UND': 'Unidades',
            'PZ': 'Piezas', 'PIEZAS': 'Piezas',
            'C/U': 'Cada Uno', 'JG': 'Juegos', 'CA': 'Cajas'
        })
        
        materiales = df_mat.groupby('DESCRIPCION').agg({
            'Total/Cantidad': 'sum',
            'Valor materiales (MS/.)': 'sum',
            'P.U. s/.': 'first',
            'UNIDAD_NORM': 'first',
            'Nombre del proyecto': 'nunique'
        }).reset_index()
        
        materiales.columns = ['Material', 'Cantidad', 'Valor', 'P.U.', 'Unidad', 'Proyectos']
        materiales = materiales.sort_values('Valor', ascending=False)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Materiales", f"{len(materiales)}")
        with col2:
            st.metric("Valor Total", f"S/ {materiales['Valor'].sum():,.0f}")
        with col3:
            st.metric("Tipos de Unidad", f"{materiales['Unidad'].nunique()}")
        
        st.markdown("---")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            unidades_unicas = ['Todos'] + list(materiales['Unidad'].unique())
            filtro_unidad = st.selectbox("Filtrar por Unidad:", unidades_unicas, key="material_unit_filter")
        
        mat_filtrados = materiales[materiales['Unidad'] == filtro_unidad] if filtro_unidad != 'Todos' else materiales
        
        if not mat_filtrados.empty:
            fig_dona_mat = _create_materials_donut_chart(mat_filtrados, filtro_unidad)
            st.plotly_chart(fig_dona_mat, use_container_width=True)
            
            with st.expander("📋 Ver Detalle de Materiales"):
                valor_min = st.number_input("Valor mínimo (MS/.):", 0, int(materiales['Valor'].max()), 0, step=10000)
                
                mat_tabla = mat_filtrados[mat_filtrados['Valor'] >= valor_min].copy()
                
                tabla_display = mat_tabla.head(50).copy()
                tabla_display['Cantidad'] = tabla_display['Cantidad'].apply(lambda x: f"{x:,.0f}")
                tabla_display['Valor'] = tabla_display['Valor'].apply(lambda x: f"S/ {x:,.0f}")
                tabla_display['P.U.'] = tabla_display['P.U.'].apply(lambda x: f"S/ {x:,.2f}")
                tabla_display['Material'] = tabla_display['Material'].str[:55]
                
                st.dataframe(
                    tabla_display[['Material', 'Cantidad', 'Unidad', 'Valor', 'P.U.', 'Proyectos']],
                    use_container_width=True,
                    hide_index=True,
                    height=300
                )
                st.caption(f"Mostrando {len(mat_tabla)} de {len(mat_filtrados)} materiales (máx 50 en tabla)")
        else:
            st.info("No hay materiales para la unidad seleccionada.")

    # Pestaña 3: Resumen por Proyecto
    with tab3:
        resumen_proyecto = df_filtered.groupby('Nombre del proyecto').agg({
            'Valor_Anual': 'sum',
            'DESCRIPCION': 'count'
        }).reset_index()
        
        resumen_proyecto.columns = ['Proyecto', 'Valor Total Anual', 'N° Materiales']
        resumen_proyecto = resumen_proyecto.sort_values('Valor Total Anual', ascending=False)
        
        resumen_proyecto['Valor Total Anual'] = resumen_proyecto['Valor Total Anual'].apply(lambda x: f"S/ {x:,.0f}")
        
        st.dataframe(
            resumen_proyecto,
            use_container_width=True,
            hide_index=True
        )
