"""
Página de Resumen Ejecutivo
Muestra KPIs principales y gráficos de distribución
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import sys
sys.path.append('..')
from components.charts import create_line_chart
from components.kpis import show_executive_summary_kpis

BAR_HEIGHT = 340


def _prepare_ranked_data(df, label_col, value_col, selected_label=None, top_n=7):
    """Devuelve Top N + Otros, garantizando que el seleccionado aparezca en el gráfico."""
    agg = (
        df.groupby(label_col, dropna=False)[value_col]
        .sum()
        .reset_index()
        .sort_values(value_col, ascending=False)
    )
    agg[label_col] = agg[label_col].fillna('Sin dato').astype(str)

    if agg.empty:
        return agg

    top = agg.head(top_n).copy()
    restantes = agg.iloc[top_n:].copy()

    if selected_label and selected_label in restantes[label_col].values:
        selected_row = restantes[restantes[label_col] == selected_label]
        restantes = restantes[restantes[label_col] != selected_label]
        top = pd.concat([top, selected_row], ignore_index=True)

    if not restantes.empty:
        top = pd.concat([
            top,
            pd.DataFrame({
                label_col: [f'Otros ({len(restantes)})'],
                value_col: [restantes[value_col].sum()]
            })
        ], ignore_index=True)

    return top.sort_values(value_col, ascending=True)


def _create_ranked_bar(df, label_col, value_col, title, selected_label=None, top_n=7):
    plot_df = _prepare_ranked_data(df, label_col, value_col, selected_label, top_n)
    if plot_df.empty:
        return go.Figure()

    otros_mask = plot_df[label_col].astype(str).str.startswith('Otros')
    if otros_mask.any():
        otros_rows = plot_df[otros_mask].copy()
        plot_df = pd.concat([plot_df[~otros_mask], otros_rows], ignore_index=True)

    colors = []
    for label in plot_df[label_col]:
        if label == selected_label:
            colors.append('#E94F37')
        elif label.startswith('Otros'):
            colors.append('#A4B6D4')
        else:
            colors.append('#2C539E')

    fig = go.Figure(go.Bar(
        x=plot_df[value_col],
        y=plot_df[label_col],
        orientation='h',
        marker_color=colors,
        text=[f"S/ {v:,.0f}" for v in plot_df[value_col]],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Valor: S/ %{x:,.0f}<extra></extra>'
    ))
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=14, color='#2C539E')),
        height=BAR_HEIGHT,
        margin=dict(t=45, b=20, l=20, r=20),
        xaxis_title='Valor (S/.)',
        yaxis_title='',
        showlegend=False
    )
    return fig


def _create_custom_donut(df, label_col, value_col, title, is_currency=False, show_legend=True):
    """Crea un gráfico de dona personalizado con lógica de 'Top N + Otros'."""
    top_n = 15
    df_sorted = df.sort_values(value_col, ascending=False).copy()
    df_grafico = df_sorted.head(top_n).copy()

    if len(df_sorted) > top_n:
        otros = pd.DataFrame({
            label_col: [f'Otros materiales ({len(df_sorted) - top_n})'],
            value_col: [df_sorted.iloc[top_n:][value_col].sum()]
        })
        df_grafico = pd.concat([df_grafico, otros], ignore_index=True)

    hovertemplate = '<b>%{label}</b><br>Valor: %{value:,.0f}<br>%{percent}<extra></extra>'
    if is_currency:
        hovertemplate = '<b>%{label}</b><br>Valor: S/ %{value:,.0f}<br>%{percent}<extra></extra>'

    fig_dona = go.Figure(go.Pie(
        labels=df_grafico[label_col].astype(str).str[:40],
        values=df_grafico[value_col],
        hole=0.55,
        marker_colors=['#2C539E', '#64AA5A', '#FFBE00', '#A4B6D4', '#5A8CD4', 
                       '#8BC34A', '#FFD54F', '#C5D6E8', '#8AAEE0', '#A9D36A',
                       '#FFE082', '#E8EEF5', '#B0C4DE', '#C8E6C9', '#FFF9C4'],
        textinfo='percent',
        textposition='outside',
        textfont=dict(size=10),
        hovertemplate=hovertemplate
    ))

    fig_dona.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=14, color='#2C539E')),
        height=450,
        margin=dict(t=50, b=20, l=20, r=20),
        showlegend=show_legend,
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

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Resumen General", "📦 Análisis de Materiales", "📋 Resumen por Proyecto", "📅 Previsión Mensual", "⚠️ Alertas Históricas"])

    # Pestaña 1: Resumen General
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏛️ Distribución por Sección")
            fig_seccion = _create_custom_donut(
                df_filtered.groupby('Seccion', dropna=False)['Valor_Anual'].sum().reset_index(),
                label_col='Seccion',
                value_col='Valor_Anual',
                title='Distribución del Presupuesto por Sección',
                is_currency=True
            )
            st.plotly_chart(fig_seccion, use_container_width=True)
        
        with col2:
            st.subheader("⚡ Distribución por Área")
            fig_area = _create_custom_donut(
                df_filtered.groupby('AREA', dropna=False)['Valor_Anual'].sum().reset_index(),
                label_col='AREA',
                value_col='Valor_Anual',
                title='Distribución del Presupuesto por Área Técnica',
                is_currency=True
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
        fig_line.update_layout(height=360)
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
            if filtro_unidad == 'Todos':
                df_unidad = mat_filtrados.groupby('Unidad')['Valor'].sum().reset_index()
                fig_unidad = _create_custom_donut(
                    df_unidad,
                    'Unidad',
                    'Valor',
                    'Distribución Económica por Tipo de Unidad',
                    is_currency=True,
                    show_legend=False
                )
                st.plotly_chart(fig_unidad, use_container_width=True)
            else:
                col_chart1, col_chart2 = st.columns(2)
                material_focus = st.selectbox(
                    "Destacar material",
                    ['Ninguno'] + sorted(mat_filtrados['Material'].astype(str).tolist()),
                    key='focus_material_valor'
                )
                with col_chart1:
                    fig_val = _create_custom_donut(
                        mat_filtrados.sort_values(
                            'Valor',
                            ascending=False,
                            key=lambda s: s.where(mat_filtrados['Material'] != material_focus, s.max() + 1)
                        ),
                        'Material',
                        'Valor',
                        f'Distribución por Valor (S/.) - {filtro_unidad}',
                        is_currency=True,
                        show_legend=False
                    )
                    st.plotly_chart(fig_val, use_container_width=True)
                with col_chart2:
                    fig_cant = _create_custom_donut(
                        mat_filtrados.sort_values(
                            'Cantidad',
                            ascending=False,
                            key=lambda s: s.where(mat_filtrados['Material'] != material_focus, s.max() + 1)
                        ),
                        'Material',
                        'Cantidad',
                        f'Distribución por Cantidad - {filtro_unidad}',
                        is_currency=False,
                        show_legend=False
                    )
                    st.plotly_chart(fig_cant, use_container_width=True)
            
            with st.expander("📋 Ver Detalle de Materiales"):
                valor_min = st.number_input("Valor mínimo (MS/.):", 0, int(materiales['Valor'].max()), 0, step=10000)
                
                mat_tabla = mat_filtrados[mat_filtrados['Valor'] >= valor_min].copy()
                
                tabla_display = mat_tabla.head(50).copy()
                tabla_display['Material'] = tabla_display['Material'].str[:55]
                
                st.dataframe(
                    tabla_display[['Material', 'Cantidad', 'Unidad', 'Valor', 'P.U.', 'Proyectos']],
                    use_container_width=True,
                    hide_index=True,
                    height=300,
                    column_config={
                        'Cantidad': st.column_config.NumberColumn(format="%.0f"),
                        'Valor': st.column_config.NumberColumn(format="S/ %.0f"),
                        'P.U.': st.column_config.NumberColumn(format="S/ %.2f"),
                        'Proyectos': st.column_config.NumberColumn(format="%d")
                    }
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
        resumen_proyecto_chart = resumen_proyecto.copy()
        proyecto_focus = st.selectbox(
            "Destacar proyecto",
            ['Ninguno'] + resumen_proyecto['Proyecto'].astype(str).tolist(),
            key='focus_resumen_proyecto'
        )
        fig_proyecto = _create_ranked_bar(
            resumen_proyecto_chart.rename(columns={'Proyecto': 'Nombre del proyecto', 'Valor Total Anual': 'Valor_Anual'}),
            label_col='Nombre del proyecto',
            value_col='Valor_Anual',
            title='Top Proyectos por Presupuesto',
            selected_label=None if proyecto_focus == 'Ninguno' else proyecto_focus
        )
        st.plotly_chart(fig_proyecto, use_container_width=True)

        with st.expander("📋 Ver detalle completo de proyectos"):
            st.dataframe(
                resumen_proyecto,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Valor Total Anual': st.column_config.NumberColumn(format="S/ %.0f"),
                    'N° Materiales': st.column_config.NumberColumn(format="%d")
                }
            )

    # Pestaña 4: Previsión Mensual
    with tab4:
        from pages import prevision_mensual
        prevision_mensual.show(df, apply_filters)

    # Pestaña 5: Alertas Históricas
    with tab5:
        st.subheader("⚠️ Alertas de Variación Histórica")
        st.markdown("Comparativa entre la Previsión de Cantidad 2026 y el Consumo Promedio Histórico (2023-2025).")
        
        if 'Promedio_Historico' not in df_filtered.columns or df_filtered['Promedio_Historico'].sum() == 0:
            st.info("No hay datos históricos disponibles cargados en el dataset (Consumo 123, 124, 125).")
        else:
            # Agrupar por material para comparar cantidades
            hist_df = df_filtered.groupby('DESCRIPCION').agg({
                'Total/Cantidad': 'sum',
                'Promedio_Historico': 'first',
                'UNIDAD': 'first',
                'Valor_Anual': 'sum',
                'Nombre del proyecto': 'nunique'
            }).reset_index()
            
            # Limpiar casos donde ambos son 0 para no hacer ruido
            hist_df = hist_df[(hist_df['Total/Cantidad'] > 0) | (hist_df['Promedio_Historico'] > 0)].copy()
            
            hist_df['Variacion_Abs'] = hist_df['Total/Cantidad'] - hist_df['Promedio_Historico']
            hist_df['Variacion_Pct'] = np.where(
                hist_df['Promedio_Historico'] > 0,
                (hist_df['Variacion_Abs'] / hist_df['Promedio_Historico']) * 100,
                100.0
            )
            # Marcar nuevo material si historico es 0
            hist_df['Variacion_Pct'] = np.where(hist_df['Promedio_Historico'] == 0, np.inf, hist_df['Variacion_Pct'])
            
            # Clasificar alertas
            hist_df['Alerta'] = 'Normal'
            hist_df.loc[(hist_df['Variacion_Pct'] >= 50) & (hist_df['Total/Cantidad'] > hist_df['Promedio_Historico']), 'Alerta'] = 'Aumento Crítico (>50%)'
            hist_df.loc[(hist_df['Variacion_Pct'] <= -50) & (hist_df['Promedio_Historico'] > hist_df['Total/Cantidad']), 'Alerta'] = 'Reducción Crítica (<-50%)'
            hist_df.loc[hist_df['Promedio_Historico'] == 0, 'Alerta'] = 'Material Nuevo / Sin Histórico'

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Materiales Analizados", len(hist_df))
            with col2:
                aumentos = len(hist_df[hist_df['Alerta'] == 'Aumento Crítico (>50%)'])
                st.metric("Aumentos Críticos", aumentos, delta=aumentos, delta_color="inverse")
            with col3:
                reducciones = len(hist_df[hist_df['Alerta'] == 'Reducción Crítica (<-50%)'])
                st.metric("Reducciones Críticas", reducciones, delta=-reducciones, delta_color="inverse")
                
            st.markdown("---")
            
            # Top Variaciones Absolutas
            top_aumentos = hist_df[hist_df['Variacion_Abs'] > 0].sort_values('Variacion_Abs', ascending=False).head(15)
            top_reducciones = hist_df[hist_df['Variacion_Abs'] < 0].sort_values('Variacion_Abs', ascending=True).head(15)
            
            colA, colB = st.columns(2)
            with colA:
                st.markdown("#### 🚀 Mayores Aumentos (Cantidad Absoluta)")
                if not top_aumentos.empty:
                    fig_up = go.Figure(go.Bar(
                        x=top_aumentos['Variacion_Abs'],
                        y=top_aumentos['DESCRIPCION'].str[:35],
                        orientation='h',
                        marker_color='#E94F37',
                        text=top_aumentos['Variacion_Pct'].apply(lambda x: f"+{x:.0f}%" if x != np.inf else "Nuevo"),
                        textposition='auto'
                    ))
                    fig_up.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), yaxis={'autorange': 'reversed'})
                    st.plotly_chart(fig_up, use_container_width=True)
                else:
                    st.info("No hay aumentos registrados.")
                    
            with colB:
                st.markdown("#### 📉 Mayores Reducciones (Cantidad Absoluta)")
                if not top_reducciones.empty:
                    fig_down = go.Figure(go.Bar(
                        x=top_reducciones['Variacion_Abs'].abs(),
                        y=top_reducciones['DESCRIPCION'].str[:35],
                        orientation='h',
                        marker_color='#2ECC71',
                        text=top_reducciones['Variacion_Pct'].apply(lambda x: f"{x:.0f}%"),
                        textposition='auto'
                    ))
                    fig_down.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), yaxis={'autorange': 'reversed'})
                    st.plotly_chart(fig_down, use_container_width=True)
                else:
                    st.info("No hay reducciones registradas.")

            st.markdown("---")
            st.markdown("#### 📋 Base de Datos de Variaciones")
            
            alerta_filter = st.selectbox("Filtrar por tipo de Alerta:", ['Todas'] + list(hist_df['Alerta'].unique()), key="alerta_filter_var")
            
            display_df = hist_df if alerta_filter == 'Todas' else hist_df[hist_df['Alerta'] == alerta_filter]
            
            display_df = display_df[['DESCRIPCION', 'UNIDAD', 'Promedio_Historico', 'Total/Cantidad', 'Variacion_Abs', 'Variacion_Pct', 'Alerta', 'Valor_Anual']].copy()
            display_df.columns = ['Material', 'Unidad', 'Prom. Histórico', 'Previsión 2026', 'Diferencia', '% Variación', 'Estado', 'Valor 2026 (S/.)']
            
            display_df = display_df.sort_values('Diferencia', key=abs, ascending=False)
            
            display_df['% Variación'] = display_df['% Variación'].replace(np.inf, np.nan)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Prom. Histórico': st.column_config.NumberColumn(format="%.1f"),
                    'Previsión 2026': st.column_config.NumberColumn(format="%.1f"),
                    'Diferencia': st.column_config.NumberColumn(format="%+.1f"),
                    '% Variación': st.column_config.NumberColumn(format="%.1f%%"),
                    'Valor 2026 (S/.)': st.column_config.NumberColumn(format="S/ %.0f")
                }
            )

