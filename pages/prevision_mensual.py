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
from components.charts import COLORS, PALETTE


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
        height=360,
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

    st.subheader("📚 Distribución Mensual por Proyecto")
    proyectos_agg = df_filtered.groupby('Nombre del proyecto').sum(numeric_only=True).reset_index()
    proyectos_agg['Total'] = proyectos_agg[[c for c in meses_col if c in proyectos_agg.columns]].sum(axis=1)
    proyectos_agg = proyectos_agg.sort_values('Total', ascending=False)

    proyecto_focus = st.selectbox(
        "Destacar proyecto",
        ['Ninguno'] + proyectos_agg['Nombre del proyecto'].astype(str).tolist(),
        key='focus_prevision_mensual_proyecto'
    )

    proyectos_select = st.multiselect(
        "Seleccionar proyectos para comparar",
        options=proyectos_agg['Nombre del proyecto'].tolist(),
        default=proyectos_agg['Nombre del proyecto'].head(6).tolist()
    )

    if proyectos_select:
        compare_df = proyectos_agg[proyectos_agg['Nombre del proyecto'].isin(proyectos_select)].copy()
        fig_dist = go.Figure()
        for i, (_, row) in enumerate(compare_df.iterrows()):
            proyecto_name = row['Nombre del proyecto']
            short_name = proyecto_name[:35] + '...' if len(proyecto_name) > 35 else proyecto_name
            fig_dist.add_trace(go.Scatter(
                name=short_name,
                x=meses,
                y=[row[col] if col in compare_df.columns else 0 for col in meses_col],
                mode='lines',
                stackgroup='one',
                line=dict(
                    width=1,
                    color='#E94F37' if proyecto_name == proyecto_focus else PALETTE[i % len(PALETTE)]
                ),
                fillcolor='#E94F37' if proyecto_name == proyecto_focus else PALETTE[i % len(PALETTE)],
                hovertemplate='<b>%{fullData.name}</b><br>Mes: %{x}<br>Valor: S/ %{y:,.0f}<extra></extra>'
            ))

        fig_dist.update_layout(
            title=dict(text='Distribución Mensual por Proyecto', x=0.5, font=dict(size=14, color=COLORS['primary'])),
            height=420,
            margin=dict(t=40, b=20, l=20, r=20),
            xaxis_title='Mes',
            yaxis_title='Valor (S/.)',
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
            hovermode='x unified'
        )
        st.plotly_chart(fig_dist, use_container_width=True)
    
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
    
    with st.expander("📋 Ver detalle mensual completo"):
        st.dataframe(
            tabla_mensual,
            use_container_width=True,
            hide_index=True,
            column_config={col: st.column_config.NumberColumn(format="%.0f") for col in cols_numericas + ['Total']}
        )
