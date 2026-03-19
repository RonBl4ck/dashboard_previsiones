"""
Componentes de KPIs para el dashboard
"""

import streamlit as st
import pandas as pd
from components.charts import COLORS

def show_kpi_cards(kpis_dict, cols=4):
    """
    Muestra tarjetas de KPIs en una fila
    
    Args:
        kpis_dict: Diccionario con {título: valor} o {título: (valor, delta)}
        cols: Número de columnas
    """
    columns = st.columns(cols)
    
    for i, (title, value) in enumerate(kpis_dict.items()):
        with columns[i % cols]:
            if isinstance(value, tuple):
                val, delta = value
                st.metric(label=title, value=val, delta=delta)
            else:
                st.metric(label=title, value=value)


def calculate_main_kpis(df):
    """
    Calcula los KPIs principales del dataframe de previsión
    
    Returns:
        dict: Diccionario con los KPIs calculados
    """
    kpis = {}
    
    # Presupuesto total
    kpis['Presupuesto Total'] = f"S/ {df['Valor_Anual'].sum():,.0f}"
    
    # Promedio mensual
    meses_valor = ['Valor_Ene', 'Valor_Feb', 'Valor_Mar', 'Valor_Abr', 'Valor_May', 'Valor_Jun',
                   'Valor_Jul', 'Valor_Ago', 'Valor_Sep', 'Valor_Oct', 'Valor_Nov', 'Valor_Dic']
    
    valor_mensual = [df[m].sum() for m in meses_valor if m in df.columns]
    if valor_mensual:
        kpis['Promedio Mensual'] = f"S/ {sum(valor_mensual)/len(valor_mensual):,.0f}"
    
    # Número de proyectos
    kpis['Proyectos'] = f"{df['Nombre del proyecto'].nunique()}"
    
    # Número de materiales
    kpis['Materiales'] = f"{df['DESCRIPCION'].nunique()}"
    
    # Mes pico
    if valor_mensual and meses_valor:
        meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        idx_max = valor_mensual.index(max(valor_mensual))
        kpis['Mes Pico'] = meses_nombres[idx_max] if idx_max < len(meses_nombres) else 'N/A'
    
    return kpis


def show_executive_summary_kpis(df):
    """
    Muestra los KPIs principales del resumen ejecutivo
    """
    kpis = calculate_main_kpis(df)
    
    # Primera fila de KPIs
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['secondary']} 100%); 
                    border-radius: 15px; padding: 20px; color: white; text-align: center;">
            <div style="font-size: 0.9rem; opacity: 0.9;">Presupuesto Total</div>
            <div style="font-size: 1.8rem; font-weight: bold; margin: 10px 0;">{kpis.get('Presupuesto Total', 'N/A')}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {COLORS['success']} 0%, #8BC34A 100%); 
                    border-radius: 15px; padding: 20px; color: white; text-align: center;">
            <div style="font-size: 0.9rem; opacity: 0.9;">Proyectos</div>
            <div style="font-size: 1.8rem; font-weight: bold; margin: 10px 0;">{kpis.get('Proyectos', 'N/A')}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {COLORS['accent']} 0%, #FFD54F 100%); 
                    border-radius: 15px; padding: 20px; color: white; text-align: center;">
            <div style="font-size: 0.9rem; opacity: 0.9;">Mes de Mayor Inversión</div>
            <div style="font-size: 1.8rem; font-weight: bold; margin: 10px 0;">{kpis.get('Mes Pico', 'N/A')}</div>
        </div>
        """, unsafe_allow_html=True)
    
    return kpis
