import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

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
    """Asegura que la hoja SALDOS exista en PREVISIONES 2026."""
    gc = get_gspread_client()
    if not gc: return None

    try:
        sh = gc.open("PREVISIONES 2026")
        try:
            worksheet = sh.worksheet("SALDOS")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="SALDOS", rows="1000", cols="5")
            worksheet.append_row(["Matricula", "Stock", "Valor_Manual", "Visible", "Anotacion"])
        return worksheet
    except Exception as e:
        st.error(f"Error accediendo a la hoja PREVISIONES 2026: {e}")
        return None

def get_saldos_data():
    """Obtiene los datos de la hoja SALDOS como un DataFrame."""
    worksheet = init_saldos_sheet()
    if not worksheet: return pd.DataFrame(columns=["Matricula", "Stock", "Valor_Manual", "Visible", "Anotacion"])
    
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    
    # Asegurar tipos
    if not df.empty:
        df['Matricula'] = df['Matricula'].astype(str)
        df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0)
        df['Valor_Manual'] = pd.to_numeric(df['Valor_Manual'], errors='coerce')
        df['Visible'] = df['Visible'].astype(bool) if 'Visible' in df.columns else False
        df['Anotacion'] = df['Anotacion'].astype(str)
    else:
        df = pd.DataFrame(columns=["Matricula", "Stock", "Valor_Manual", "Visible", "Anotacion"])
    
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
        cols = ["Matricula", "Stock", "Valor_Manual", "Visible", "Anotacion"]
        upload_df = updates_df[cols].copy()
        upload_df = upload_df.fillna('')
        upload_df['Visible'] = upload_df['Visible'].astype(str).str.upper()
        
        # Limpiar la hoja y subir todo de nuevo
        worksheet.clear()
        worksheet.update([cols] + upload_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error actualizando saldos en Sheets: {e}")
        return False
