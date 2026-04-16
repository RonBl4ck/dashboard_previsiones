import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

SALDOS_COLS = ["Matricula", "Stock", "Valor_Manual", "Visible", "Anotacion",
               "StockQ", "Decimals", "UseK", "UnitSuffix"]

@st.cache_resource
def get_gspread_client():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        st.error(f"Error autenticando con Google Sheets: {e}")
        return None

def init_saldos_sheet():
    """Asegura que la hoja SALDOS exista en PREVISIONES 2026 con todas las columnas necesarias."""
    gc = get_gspread_client()
    if not gc: return None

    try:
        sh = gc.open("PREVISIONES 2026")
        try:
            worksheet = sh.worksheet("SALDOS")
            # Verificar que las columnas nuevas existan; si no, migrar
            existing_headers = worksheet.row_values(1)
            missing = [c for c in SALDOS_COLS if c not in existing_headers]
            if missing:
                # Expandir la cuadrícula con margen extra para evitar futuros errores
                total_cols_needed = max(len(existing_headers) + len(missing), 15)
                worksheet.resize(cols=total_cols_needed)
                # Añadir las columnas faltantes al final del header
                start_col = len(existing_headers) + 1
                for i, col_name in enumerate(missing):
                    worksheet.update_cell(1, start_col + i, col_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="SALDOS", rows="1000", cols=str(len(SALDOS_COLS)))
            worksheet.append_row(SALDOS_COLS)
        return worksheet
    except Exception as e:
        st.error(f"Error accediendo a la hoja PREVISIONES 2026: {e}")
        return None

def get_saldos_data():
    """Obtiene los datos de la hoja SALDOS como un DataFrame."""
    worksheet = init_saldos_sheet()
    if not worksheet: return pd.DataFrame(columns=SALDOS_COLS)
    
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    
    # Asegurar tipos
    if not df.empty:
        df['Matricula'] = df['Matricula'].astype(str)
        df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0)
        df['Valor_Manual'] = pd.to_numeric(df['Valor_Manual'], errors='coerce')
        df['Visible'] = df['Visible'].astype(bool) if 'Visible' in df.columns else False
        df['Anotacion'] = df['Anotacion'].astype(str) if 'Anotacion' in df.columns else ''
        df['StockQ'] = pd.to_numeric(df.get('StockQ', 0), errors='coerce').fillna(0)
        df['Decimals'] = pd.to_numeric(df.get('Decimals', 0), errors='coerce').fillna(0).astype(int)
        df['UseK'] = df['UseK'].astype(str).str.upper().isin(['TRUE', '1', 'YES']) if 'UseK' in df.columns else False
        df['UnitSuffix'] = df['UnitSuffix'].astype(str).replace('nan', '') if 'UnitSuffix' in df.columns else ''
    else:
        df = pd.DataFrame(columns=SALDOS_COLS)
    
    # Asegurar que existan todas las columnas esperadas
    for col in SALDOS_COLS:
        if col not in df.columns:
            df[col] = 0 if col in ('Stock', 'StockQ', 'Decimals') else (False if col in ('Visible', 'UseK') else '')
    
    return df

def update_saldos_batch(updates_df):
    """
    Actualiza la hoja de saldos completamente basado en un dataframe.
    Este método es más seguro y rápido para actualizaciones batch.
    """
    worksheet = init_saldos_sheet()
    if not worksheet: return False
    
    try:
        # Asegurar orden y formato de columnas antes de subir
        upload_df = updates_df.reindex(columns=SALDOS_COLS).copy()
        upload_df = upload_df.fillna('')
        upload_df['Visible'] = upload_df['Visible'].astype(str).str.upper()
        upload_df['UseK'] = upload_df['UseK'].astype(str).str.upper()
        
        # Limpiar la hoja y subir todo de nuevo
        worksheet.clear()
        worksheet.update([SALDOS_COLS] + upload_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error actualizando saldos en Sheets: {e}")
        return False

def init_consumo_notes_sheet():
    """Asegura que la hoja NOTAS_CONSUMO exista en PREVISIONES 2026."""
    gc = get_gspread_client()
    if not gc: return None

    cols = ["Matricula", "Anotacion"]
    try:
        sh = gc.open("PREVISIONES 2026")
        try:
            worksheet = sh.worksheet("NOTAS_CONSUMO")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="NOTAS_CONSUMO", rows="1000", cols=str(len(cols)))
            worksheet.append_row(cols)
        return worksheet
    except Exception as e:
        st.error(f"Error accediendo a la hoja PREVISIONES 2026 (NOTAS_CONSUMO): {e}")
        return None

def get_consumo_notes():
    """Obtiene las anotaciones de consumo como un diccionario {matricula: anotacion}."""
    worksheet = init_consumo_notes_sheet()
    if not worksheet: return {}
    
    try:
        data = worksheet.get_all_records()
        if not data: return {}
        return {str(r['Matricula']).strip(): str(r['Anotacion']).strip() for r in data if 'Matricula' in r}
    except Exception as e:
        st.error(f"Error cargando notas de consumo: {e}")
        return {}

def update_consumo_notes_batch(notes_df):
    """Actualiza la hoja de notas de consumo en batch."""
    worksheet = init_consumo_notes_sheet()
    if not worksheet: return False
    
    try:
        cols = ["Matricula", "Anotacion"]
        upload_df = notes_df[cols].copy()
        upload_df = upload_df.fillna('')
        
        worksheet.clear()
        worksheet.update([cols] + upload_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error actualizando notas de consumo en Sheets: {e}")
        return False
