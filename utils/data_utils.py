"""
Utilidades para procesamiento de datos
"""

import pandas as pd
import numpy as np
from pathlib import Path


def clean_numeric_column(df, column):
    """Limpia una columna numérica, convirtiendo a float"""
    df[column] = pd.to_numeric(df[column], errors='coerce')
    return df


def format_currency(value, currency='S/'):
    """Formatea un valor como moneda"""
    if pd.isna(value):
        return '-'
    return f"{currency} {value:,.0f}"


def format_number(value, decimals=0):
    """Formatea un número con separadores de miles"""
    if pd.isna(value):
        return '-'
    if decimals == 0:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"


def calculate_percentage(value, total):
    """Calcula el porcentaje de un valor respecto al total"""
    if total == 0 or pd.isna(total):
        return 0
    return (value / total) * 100


def get_month_columns(prefix='Valor_'):
    """Retorna la lista de columnas mensuales"""
    meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
             'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    return [f'{prefix}{m}' for m in meses]


def aggregate_by_period(df, group_cols, value_cols, period='month'):
    """
    Agrega datos por período de tiempo
    
    Args:
        df: DataFrame con los datos
        group_cols: Columnas para agrupar
        value_cols: Columnas de valores a sumar
        period: 'month', 'quarter' o 'year'
    
    Returns:
        DataFrame agregado
    """
    agg_dict = {col: 'sum' for col in value_cols}
    return df.groupby(group_cols).agg(agg_dict).reset_index()


def calculate_cumulative(df, value_cols):
    """
    Calcula valores acumulados
    
    Args:
        df: DataFrame con los datos
        value_cols: Columnas para calcular acumulado
    
    Returns:
        DataFrame con columnas acumuladas
    """
    for col in value_cols:
        df[f'{col}_Acum'] = df[col].cumsum()
    return df


def export_to_excel(df, filename, sheet_name='Datos'):
    """
    Exporta un DataFrame a Excel
    
    Args:
        df: DataFrame a exportar
        filename: Nombre del archivo
        sheet_name: Nombre de la hoja
    
    Returns:
        True si se exportó correctamente
    """
    try:
        df.to_excel(filename, sheet_name=sheet_name, index=False)
        return True
    except Exception as e:
        print(f"Error exportando a Excel: {e}")
        return False


def validate_upload_file(df, required_columns):
    """
    Valida que un archivo subido tenga las columnas requeridas
    
    Args:
        df: DataFrame del archivo
        required_columns: Lista de columnas requeridas
    
    Returns:
        (bool, list): (es_válido, columnas_faltantes)
    """
    df_columns = [col.lower().strip() for col in df.columns]
    missing = []
    
    for req_col in required_columns:
        if req_col.lower().strip() not in df_columns:
            missing.append(req_col)
    
    return len(missing) == 0, missing


def calculate_kpi_summary(df):
    """
    Calcula un resumen de KPIs principales
    
    Returns:
        dict: Diccionario con los KPIs
    """
    kpis = {
        'total_presupuesto': df['Valor materiales (MS/.)'].sum() if 'Valor materiales (MS/.)' in df.columns else 0,
        'total_cantidad': df['Total/Cantidad'].sum() if 'Total/Cantidad' in df.columns else 0,
        'num_proyectos': df['Nombre del proyecto'].nunique() if 'Nombre del proyecto' in df.columns else 0,
        'num_materiales': df['DESCRIPCION'].nunique() if 'DESCRIPCION' in df.columns else 0,
    }
    
    # Calcular promedio mensual
    month_cols = get_month_columns('Valor_')
    monthly_values = [df[col].sum() for col in month_cols if col in df.columns]
    
    if monthly_values:
        kpis['promedio_mensual'] = sum(monthly_values) / len(monthly_values)
        kpis['mes_max'] = max(monthly_values)
        kpis['mes_min'] = min(monthly_values)
    
    return kpis
