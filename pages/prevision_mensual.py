"""
Página de Previsión Mensual
Muestra la evolución temporal y distribución mensual
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
sys.path.append('..')
from components.charts import (
    create_line_chart, create_stacked_bar, create_heatmap, COLORS, PALETTE
)


def show(df, apply_filters):
    """Función principal de la página de Previsión Mensual"""
    
    st.title("📅 Previsión Mensual")
    st.markdown("---")
    
    # Aplicar filtros
    df_filtered = apply_filters(df)
    
    if df_filtered.empty:
        st.warning("No hay datos con los filtros seleccionados")
        return
    
    # Forzar la vista a valores monetarios para evitar sumar unidades distintas
    view_type = "Valores Monetarios"
    
    prefix = 'Valor_'
    y_label = 'Valor (MS/.)'
    
    meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    meses_col = [f'{prefix}{m}' for m in meses]
    
    st.markdown("---")
    
    # Evolución mensual general
    st.subheader("📈 Evolución Mensual General")
    
    valores_mensuales = []
    for m in meses_col:
        if m in df_filtered.columns:
            valores_mensuales.append(df_filtered[m].sum())
        else:
            valores_mensuales.append(0)
    
    # Crear gráfico de líneas con área
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=meses,
        y=valores_mensuales,
        mode='lines+markers+text',
        name='Previsión',
        line=dict(color=COLORS['primary'], width=3),
        marker=dict(size=12, color=COLORS['primary']),
        fill='tozeroy',
        fillcolor='rgba(44, 83, 158, 0.15)',
        text=[f'{v:,.0f}' for v in valores_mensuales],
        textposition='top center',
        textfont=dict(size=10)
    ))
    
    # Añadir línea de promedio
    promedio = sum(valores_mensuales) / len(valores_mensuales) if valores_mensuales else 0
    fig.add_hline(
        y=promedio,
        line_dash="dash",
        line_color=COLORS['accent'],
        annotation_text=f"Promedio: {promedio:,.0f}",
        annotation_position="right"
    )
    
    fig.update_layout(
        title=dict(text='Previsión Mensual 2026', x=0.5, font=dict(size=16, color=COLORS['primary'])),
        xaxis_title='Mes',
        yaxis_title=y_label,
        margin=dict(t=50, b=50, l=60, r=100),
        height=450,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Métricas del período
    col1, col2, col3, col4 = st.columns(4)
    
    total = sum(valores_mensuales)
    max_val = max(valores_mensuales) if valores_mensuales else 0
    min_val = min(valores_mensuales) if valores_mensuales else 0
    
    with col1:
        st.metric("Total Anual", f"{total:,.0f}")
    with col2:
        st.metric("Promedio Mensual", f"{promedio:,.0f}")
    with col3:
        st.metric("Mes Máximo", f"{max_val:,.0f}")
    with col4:
        st.metric("Mes Mínimo", f"{min_val:,.0f}")
    
    st.markdown("---")
    
    # Distribución por proyecto y mes - ÁREAS APILADAS
    st.subheader("📊 Distribución Mensual por Proyecto")
    
    # Selector de proyectos
    proyectos = df_filtered['Nombre del proyecto'].unique()
    proyectos_select = st.multiselect(
        "Seleccionar proyectos (máx 10 para mejor visualización):",
        options=proyectos,
        default=list(proyectos)[:6] if len(proyectos) > 6 else list(proyectos)
    )
    
    if proyectos_select:
        df_proyectos = df_filtered[df_filtered['Nombre del proyecto'].isin(proyectos_select)]
        
        # Agregar datos por proyecto
        agg_data = df_proyectos.groupby('Nombre del proyecto').sum(numeric_only=True).reset_index()
        
        # Colores corporativos
        colors = PALETTE
        
        # Crear gráfico de áreas apiladas
        fig2 = go.Figure()
        
        for i, (_, row) in enumerate(agg_data.iterrows()):
            # Obtener valores mensuales
            valores = []
            for mes in meses:
                col_name = f'{prefix}{mes}'
                if col_name in agg_data.columns:
                    valores.append(row[col_name])
                else:
                    valores.append(0)
            
            # Acortar nombre del proyecto si es muy largo
            proyecto_name = row['Nombre del proyecto']
            if len(proyecto_name) > 35:
                proyecto_name = proyecto_name[:35] + '...'
            
            fig2.add_trace(go.Scatter(
                x=meses,
                y=valores,
                name=proyecto_name,
                mode='lines',
                stackgroup='one',  # Apilar áreas
                line=dict(width=0.5, color=colors[i % len(colors)]),
                fillcolor=colors[i % len(colors)],
                hovertemplate='<b>%{fullData.name}</b><br>Mes: %{x}<br>Valor: %{y:,.0f}<extra></extra>'
            ))
        
        fig2.update_layout(
            title=dict(
                text='Evolución Acumulada por Proyecto',
                x=0.5,
                font=dict(size=14, color=COLORS['primary'])
            ),
            xaxis_title='Mes',
            yaxis_title=y_label,
            margin=dict(t=60, b=50, l=60, r=20),
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            hovermode='x unified',  # Muestra todos los valores al pasar mouse
            xaxis=dict(
                tickmode='array',
                tickvals=meses,
                ticktext=meses
            )
        )
        
        # Añadir línea de promedio
        valores_totales = []
        for mes in meses:
            col_name = f'{prefix}{mes}'
            if col_name in agg_data.columns:
                valores_totales.append(agg_data[col_name].sum())
            else:
                valores_totales.append(0)
        
        promedio = sum(valores_totales) / len(valores_totales) if valores_totales else 0
        
        fig2.add_hline(
            y=promedio,
            line_dash="dash",
            line_color=COLORS['accent'],
            opacity=0.7,
            annotation_text=f"Promedio: {promedio:,.0f}",
            annotation_position="right",
            annotation_font=dict(size=10, color=COLORS['accent'])
        )
        
        st.plotly_chart(fig2, use_container_width=True)
        
        # Mostrar resumen de proyectos seleccionados
        with st.expander("📋 Ver resumen de proyectos seleccionados"):
            resumen = agg_data[['Nombre del proyecto']].copy()
            resumen['Total'] = resumen['Nombre del proyecto'].apply(
                lambda x: sum([df_proyectos[df_proyectos['Nombre del proyecto'] == x][f'{prefix}{m}'].sum() 
                              for m in meses if f'{prefix}{m}' in df_proyectos.columns])
            )
            resumen = resumen.sort_values('Total', ascending=False)
            resumen['Participación %'] = (resumen['Total'] / resumen['Total'].sum() * 100).round(1)
            resumen['Total'] = resumen['Total'].apply(lambda x: f"S/ {x:,.0f}")
            resumen['Participación %'] = resumen['Participación %'].apply(lambda x: f"{x}%")
            resumen.columns = ['Proyecto', 'Total Anual', 'Participación']
            
            st.dataframe(resumen, use_container_width=True, hide_index=True)
    
    st.markdown("---")
        
    # Tabla detallada mensual
    st.subheader("📋 Detalle Mensual")
    
    # Crear tabla pivote
    tabla_mensual = df_filtered.groupby('Nombre del proyecto').sum(numeric_only=True).reset_index()
    
    # Seleccionar columnas relevantes
    cols_mostrar = ['Nombre del proyecto'] + [f'{prefix}{m}' for m in meses if f'{prefix}{m}' in tabla_mensual.columns]
    tabla_mensual = tabla_mensual[cols_mostrar]
    
    # Añadir columna de total
    cols_numericas = [c for c in tabla_mensual.columns if c != 'Nombre del proyecto']
    tabla_mensual['Total'] = tabla_mensual[cols_numericas].sum(axis=1)
    
    # Ordenar por total
    tabla_mensual = tabla_mensual.sort_values('Total', ascending=False)
    
    # Formatear
    for col in cols_numericas + ['Total']:
        tabla_mensual[col] = tabla_mensual[col].apply(lambda x: f"{x:,.0f}")
    
    st.dataframe(
        tabla_mensual,
        use_container_width=True,
        hide_index=True
    )
