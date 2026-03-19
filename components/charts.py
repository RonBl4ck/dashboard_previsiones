"""
Componentes de gráficos reutilizables
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# Colores corporativos
COLORS = {
    'primary': '#2C539E',
    'secondary': '#A4B6D4',
    'accent': '#FFBE00',
    'success': '#64AA5A',
    'warning': '#FFBE00',
    'colonial': '#5A8CD4',
    'panamericana': '#FFD54F',
    'mt': '#8BC34A',
    'bt': '#C5D6E8',
    'ap': '#FFBE00'
}

PALETTE = ['#2C539E', '#64AA5A', '#FFBE00', '#A4B6D4', '#5A8CD4', 
           '#8BC34A', '#FFD54F', '#C5D6E8', '#8AAEE0', '#A9D36A',
           '#FFE082', '#E8EEF5', '#B0C4DE', '#C8E6C9', '#FFF9C4']


def create_donut_chart(df, column, title, value_column='Valor materiales (MS/.)'):
    """Crea un gráfico de donut para distribución porcentual"""
    
    agg_data = df.groupby(column)[value_column].sum().reset_index()
    agg_data = agg_data.sort_values(value_column, ascending=False)
    
    fig = px.pie(
        agg_data, 
        values=value_column, 
        names=column,
        hole=0.6,
        color_discrete_sequence=PALETTE
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        textfont_size=12,
        marker=dict(line=dict(color='white', width=2))
    )
    
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=16, color=COLORS['primary'])),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(t=50, b=50, l=20, r=20),
        height=400
    )
    
    return fig


def create_treemap(df, path_columns, value_column, title):
    """Crea un treemap para visualización jerárquica"""
    
    # Agregar datos por la ruta especificada
    agg_data = df.groupby(path_columns)[value_column].sum().reset_index()
    agg_data = agg_data[agg_data[value_column] > 0]
    
    fig = px.treemap(
        agg_data,
        path=path_columns,
        values=value_column,
        color=value_column,
        color_continuous_scale=['#E8EEF5', '#A4B6D4', '#5A8CD4', '#2C539E'],
        title=title
    )
    
    fig.update_layout(
        margin=dict(t=50, b=20, l=20, r=20),
        height=500
    )
    
    fig.update_traces(
        textfont=dict(size=14),
        textinfo="label+value+percent root"
    )
    
    return fig


def create_bar_chart(df, category_col, value_col, title, orientation='h', top_n=10):
    """Crea un gráfico de barras (horizontal o vertical)"""
    
    agg_data = df.groupby(category_col)[value_col].sum().reset_index()
    agg_data = agg_data.sort_values(value_col, ascending=(orientation == 'h'))
    
    if top_n:
        agg_data = agg_data.head(top_n)
    
    fig = px.bar(
        agg_data,
        x=category_col if orientation == 'v' else value_col,
        y=value_col if orientation == 'v' else category_col,
        orientation=orientation,
        color=value_col,
        color_continuous_scale=['#E8EEF5', '#A4B6D4', '#5A8CD4', '#2C539E'],
        text_auto='.2s'
    )
    
    fig.update_traces(
        textposition='outside',
        marker=dict(line=dict(color='white', width=1))
    )
    
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=16, color=COLORS['primary'])),
        showlegend=False,
        margin=dict(t=50, b=50, l=150 if orientation == 'h' else 50, r=50),
        height=400,
        xaxis_title=value_col if orientation == 'h' else category_col,
        yaxis_title=category_col if orientation == 'h' else value_col
    )
    
    return fig


def create_line_chart(df, months, values, title, y_label='Valor (MS/.)'):
    """Crea un gráfico de líneas para evolución temporal"""
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=months,
        y=values,
        mode='lines+markers',
        name='Previsión',
        line=dict(color=COLORS['primary'], width=3),
        marker=dict(size=10),
        fill='tozeroy',
        fillcolor='rgba(44, 83, 158, 0.1)'
    ))
    
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=16, color=COLORS['primary'])),
        xaxis_title='Mes',
        yaxis_title=y_label,
        margin=dict(t=50, b=50, l=60, r=20),
        height=400,
        hovermode='x unified'
    )
    
    return fig


def create_stacked_bar(df, index_col, months, title, values_prefix='Valor_'):
    """Crea un gráfico de barras apiladas"""
    
    # Preparar datos
    agg_data = df.groupby(index_col).sum(numeric_only=True).reset_index()
    
    # Seleccionar columnas de meses
    month_cols = [f'{values_prefix}{m}' for m in months]
    
    fig = go.Figure()
    
    colors = PALETTE * 5
    
    for i, month in enumerate(months):
        col = f'{values_prefix}{month}'
        if col in agg_data.columns:
            fig.add_trace(go.Bar(
                name=month,
                x=agg_data[index_col],
                y=agg_data[col],
                marker_color=colors[i % len(colors)]
            ))
    
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=16, color=COLORS['primary'])),
        barmode='stack',
        xaxis_title=index_col,
        yaxis_title='Valor (MS/.)',
        margin=dict(t=50, b=100, l=60, r=20),
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
    )
    
    return fig


def create_heatmap(df, row_col, col_col, value_col, title):
    """Crea un heatmap para visualización de matriz"""
    
    pivot = df.pivot_table(
        values=value_col,
        index=row_col,
        columns=col_col,
        aggfunc='sum',
        fill_value=0
    )
    
    fig = px.imshow(
        pivot,
        labels=dict(x=col_col, y=row_col, color=value_col),
        x=pivot.columns,
        y=pivot.index,
        color_continuous_scale=['#E8EEF5', '#A4B6D4', '#5A8CD4', '#2C539E'],
        aspect="auto"
    )
    
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=16, color=COLORS['primary'])),
        margin=dict(t=50, b=50, l=150, r=20),
        height=500
    )
    
    return fig


def create_comparison_bar(categories, values1, values2, label1, label2, title):
    """Crea un gráfico de barras comparativas (Previsión vs Real)"""
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name=label1,
        x=categories,
        y=values1,
        marker_color=COLORS['primary'],
        text=values1,
        textposition='outside',
        texttemplate='%{text:,.0f}'
    ))
    
    fig.add_trace(go.Bar(
        name=label2,
        x=categories,
        y=values2,
        marker_color=COLORS['accent'],
        text=values2,
        textposition='outside',
        texttemplate='%{text:,.0f}'
    ))
    
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=16, color=COLORS['primary'])),
        barmode='group',
        margin=dict(t=50, b=50, l=60, r=20),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    
    return fig


def create_gauge_chart(value, max_value, title, thresholds=None):
    """Crea un gráfico gauge/speedometer para % de ejecución"""
    
    if thresholds is None:
        thresholds = {'red': 50, 'yellow': 80, 'green': 100}
    
    percentage = (value / max_value * 100) if max_value > 0 else 0
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = percentage,
        title = {'text': title, 'font': {'size': 16, 'color': COLORS['primary']}},
        delta = {'reference': 100},
        gauge = {
            'axis': {'range': [None, 120], 'ticksuffix': '%'},
            'bar': {'color': COLORS['primary']},
            'steps': [
                {'range': [0, thresholds['red']], 'color': '#A4B6D4'},
                {'range': [thresholds['red'], thresholds['yellow']], 'color': '#FFBE00'},
                {'range': [thresholds['yellow'], thresholds['green']], 'color': '#64AA5A'}
            ],
            'threshold': {
                'line': {'color': COLORS['accent'], 'width': 4},
                'thickness': 0.75,
                'value': 100
            }
        }
    ))
    
    fig.update_layout(
        margin=dict(t=50, b=20, l=20, r=20),
        height=300
    )
    
    return fig


def create_area_diff_chart(months, values1, values2, title, label1='Previsión', label2='Real'):
    """Crea un gráfico de área mostrando la diferencia entre dos series"""
    
    diff = [v1 - v2 for v1, v2 in zip(values1, values2)]
    
    fig = go.Figure()
    
    # Área de previsión
    fig.add_trace(go.Scatter(
        x=months, y=values1,
        name=label1,
        mode='lines',
        stackgroup='one',
        line=dict(color=COLORS['primary'], width=2),
        fillcolor='rgba(44, 83, 158, 0.3)'
    ))
    
    # Área de real
    fig.add_trace(go.Scatter(
        x=months, y=values2,
        name=label2,
        mode='lines',
        stackgroup='two',
        line=dict(color=COLORS['accent'], width=2),
        fillcolor='rgba(255, 190, 0, 0.3)'
    ))
    
    # Línea de diferencia
    fig.add_trace(go.Scatter(
        x=months, y=diff,
        name='Diferencia',
        mode='lines+markers',
        line=dict(color=COLORS['success'], width=2, dash='dot'),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=16, color=COLORS['primary'])),
        xaxis_title='Mes',
        yaxis_title='Valor (MS/.)',
        margin=dict(t=50, b=50, l=60, r=20),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    
    return fig
