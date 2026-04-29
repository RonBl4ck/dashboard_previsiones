import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

SALDOS_COLS = ["Matricula", "Stock", "Valor_Manual", "Visible", "Anotacion",
               "StockQ", "Decimals", "UseK", "UnitSuffix", "RoundTo"]

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
        df['RoundTo'] = pd.to_numeric(df.get('RoundTo', 1), errors='coerce').fillna(1).astype(int)
    else:
        df = pd.DataFrame(columns=SALDOS_COLS)
    
    # Asegurar que existan todas las columnas esperadas
    for col in SALDOS_COLS:
        if col not in df.columns:
            df[col] = 0 if col in ('Stock', 'StockQ', 'Decimals') else (1 if col == 'RoundTo' else (False if col in ('Visible', 'UseK') else ''))
    
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

# --- FACTORES MANUALES ---

def init_manual_factors_sheet():
    """Asegura que la hoja FACTORES_MANUALES exista en PREVISIONES 2026."""
    gc = get_gspread_client()
    if not gc: return None

    cols = ["PI_Code", "Factor_Manual"]
    try:
        sh = gc.open("PREVISIONES 2026")
        try:
            worksheet = sh.worksheet("FACTORES_MANUALES")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="FACTORES_MANUALES", rows="1000", cols=str(len(cols)))
            worksheet.append_row(cols)
        return worksheet
    except Exception as e:
        st.error(f"Error accediendo a la hoja PREVISIONES 2026 (FACTORES_MANUALES): {e}")
        return None

def get_manual_factors():
    """Obtiene los factores manuales guardados usando valores sin formato para evitar errores de decimales."""
    worksheet = init_manual_factors_sheet()
    if not worksheet: return pd.DataFrame(columns=["PI_Code", "Factor_Manual"])
    
    try:
        # Usar UNFORMATTED_VALUE para obtener el número real (0.14) y no el texto formateado ("0,14")
        rows = worksheet.get_all_values(value_render_option='UNFORMATTED_VALUE')
        if len(rows) <= 1:
            df = pd.DataFrame(columns=["PI_Code", "Factor_Manual"])
        else:
            headers = rows[0]
            data = rows[1:]
            df = pd.DataFrame(data, columns=headers)
        
        if not df.empty:
            df['PI_Code'] = df['PI_Code'].astype(str)
            # Limpiar y convertir a float de forma segura
            df['Factor_Manual'] = pd.to_numeric(df['Factor_Manual'], errors='coerce').fillna(0.7).astype(float)
        
        # Asegurar tipo float incluso si está vacío
        df['Factor_Manual'] = df['Factor_Manual'].astype(float)
        return df
    except Exception as e:
        st.error(f"Error cargando factores manuales (UNFORMATTED): {e}")
        return pd.DataFrame(columns=["PI_Code", "Factor_Manual"])

def update_manual_factors_batch(factors_df):
    """Guarda los factores manuales en batch."""
    worksheet = init_manual_factors_sheet()
    if not worksheet: return False
    
    try:
        cols = ["PI_Code", "Factor_Manual"]
        upload_df = factors_df[cols].copy()
        upload_df = upload_df.fillna('')
        
        worksheet.clear()
        worksheet.update([cols] + upload_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error actualizando factores manuales en Sheets: {e}")
        return False

# --- KITS PERSONALIZADOS (PROYECTOS NUEVOS) ---

def init_custom_kits_sheet():
    """Asegura que la hoja KITS_NUEVOS exista en PREVISIONES 2026."""
    gc = get_gspread_client()
    if not gc: return None

    cols = ["PI_Code", "Proyecto", "Seccion", "Material", "Descripcion", "Cantidad", "Precio_Unitario"]
    try:
        sh = gc.open("PREVISIONES 2026")
        try:
            worksheet = sh.worksheet("KITS_NUEVOS")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="KITS_NUEVOS", rows="1000", cols=str(len(cols)))
            worksheet.append_row(cols)
        return worksheet
    except Exception as e:
        st.error(f"Error accediendo a la hoja PREVISIONES 2026 (KITS_NUEVOS): {e}")
        return None

def get_custom_kits():
    """Obtiene los kits personalizados guardados."""
    worksheet = init_custom_kits_sheet()
    target_cols = ["PI_Code", "Proyecto", "Seccion", "Material", "Descripcion", "Cantidad", "Precio_Unitario"]
    if not worksheet: return pd.DataFrame(columns=target_cols)
    
    try:
        rows = worksheet.get_all_values(value_render_option='UNFORMATTED_VALUE')
        if len(rows) <= 1:
            df = pd.DataFrame(columns=target_cols)
        else:
            headers = rows[0]
            data = rows[1:]
            df = pd.DataFrame(data, columns=headers)
            
            # Asegurar que todas las columnas objetivo existan
            for c in target_cols:
                if c not in df.columns:
                    df[c] = ""
            
            # Reordenar para consistencia
            df = df[target_cols]
        
        if not df.empty:
            df['PI_Code'] = df['PI_Code'].astype(str)
            df['Material'] = df['Material'].astype(str)
            df['Proyecto'] = df['Proyecto'].astype(str)
            df['Seccion'] = df['Seccion'].astype(str)
            df['Descripcion'] = df['Descripcion'].astype(str)
            df['Cantidad'] = pd.to_numeric(df['Cantidad'], errors='coerce').fillna(0).astype(float)
            df['Precio_Unitario'] = pd.to_numeric(df['Precio_Unitario'], errors='coerce').fillna(0).astype(float)
        
        return df
    except Exception as e:
        st.error(f"Error cargando kits personalizados: {e}")
        return pd.DataFrame(columns=target_cols)

def update_custom_kits_batch(kits_df):
    """Guarda los kits personalizados en batch."""
    worksheet = init_custom_kits_sheet()
    if not worksheet: return False
    
    try:
        cols = ["PI_Code", "Proyecto", "Seccion", "Material", "Descripcion", "Cantidad", "Precio_Unitario"]
        # Asegurar que todas existan antes de filtrar
        for c in cols:
            if c not in kits_df.columns:
                kits_df[c] = ""
                
        upload_df = kits_df[cols].copy()
        upload_df = upload_df.fillna('')
        
        worksheet.clear()
        worksheet.update([cols] + upload_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error actualizando kits personalizados en Sheets: {e}")
        return False
# --- KITS DE INGENIERIA (CALCULADORA DE PROPORCIONES) ---

def init_engineering_kits_sheet():
    """Asegura que la hoja KITS_INGENIERIA exista en PREVISIONES 2026."""
    gc = get_gspread_client()
    if not gc: return None

    cols = ["Nombre_Kit", "Matricula", "Descripcion", "Tipo", "Multiplicador", "Intervalo", "Factor", "Display"]
    try:
        sh = gc.open("PREVISIONES 2026")
        try:
            worksheet = sh.worksheet("KITS_INGENIERIA")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="KITS_INGENIERIA", rows="1000", cols=str(len(cols)))
            worksheet.append_row(cols)
        return worksheet
    except Exception as e:
        st.error(f"Error accediendo a la hoja PREVISIONES 2026 (KITS_INGENIERIA): {e}")
        return None

def get_engineering_kits():
    """Obtiene los kits de ingeniería guardados."""
    worksheet = init_engineering_kits_sheet()
    cols = ["Nombre_Kit", "Matricula", "Descripcion", "Tipo", "Multiplicador", "Intervalo", "Factor", "Display"]
    if not worksheet: return pd.DataFrame(columns=cols)
    
    try:
        rows = worksheet.get_all_values(value_render_option='UNFORMATTED_VALUE')
        if len(rows) <= 1:
            df = pd.DataFrame(columns=cols)
        else:
            headers = rows[0]
            data = rows[1:]
            df = pd.DataFrame(data, columns=headers)
        
        if not df.empty:
            df['Multiplicador'] = pd.to_numeric(df['Multiplicador'], errors='coerce').fillna(1.0).astype(float)
            df['Intervalo'] = pd.to_numeric(df['Intervalo'], errors='coerce').fillna(100.0).astype(float)
            df['Factor'] = pd.to_numeric(df['Factor'], errors='coerce').fillna(1.0).astype(float)
            
            # Ensure Display exists for backward compatibility with old saves
            if 'Display' not in df.columns:
                df['Display'] = df['Matricula'].astype(str) + " - " + df['Descripcion'].astype(str).str[:50]
        
        # Ensure the dataframe always returns the expected columns
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        
        return df
    except Exception as e:
        st.error(f"Error cargando kits de ingeniería: {e}")
        return pd.DataFrame(columns=cols)

def update_engineering_kits_batch(kits_df):
    """Guarda los kits de ingeniería en batch."""
    worksheet = init_engineering_kits_sheet()
    if not worksheet: return False
    
    try:
        cols = ["Nombre_Kit", "Matricula", "Descripcion", "Tipo", "Multiplicador", "Intervalo", "Factor", "Display"]
        upload_df = kits_df[cols].copy()
        upload_df = upload_df.fillna('')
        
        worksheet.clear()
        worksheet.update([cols] + upload_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error actualizando kits de ingeniería en Sheets: {e}")
        return False

# --- HISTORICO PRESUPUESTO POR PI ---

def init_presupuesto_historico_sheet():
    """Asegura que la hoja HISTORICO_PRESUPUESTO exista en PREVISIONES 2026."""
    gc = get_gspread_client()
    if not gc: return None

    cols = ["PI_Code", "Proyecto", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    try:
        sh = gc.open("PREVISIONES 2026")
        try:
            worksheet = sh.worksheet("HISTORICO_PRESUPUESTO")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="HISTORICO_PRESUPUESTO", rows="1000", cols=str(len(cols)))
            worksheet.append_row(cols)
        return worksheet
    except Exception as e:
        st.error(f"Error accediendo a la hoja PREVISIONES 2026 (HISTORICO_PRESUPUESTO): {e}")
        return None

def get_presupuesto_historico():
    """Obtiene el histórico de presupuestos por PI de forma dinámica según las columnas de la hoja."""
    worksheet = init_presupuesto_historico_sheet()
    if not worksheet: return pd.DataFrame()
    
    try:
        rows = worksheet.get_all_values(value_render_option='UNFORMATTED_VALUE')
        
        if len(rows) <= 1:
            # Si está vacío, retornamos la estructura base
            cols = ["PI_Code", "Proyecto", "Ene", "Feb", "Mar", "Abr"]
            return pd.DataFrame(columns=cols)
        else:
            headers = rows[0]
            data = rows[1:]
            df = pd.DataFrame(data, columns=headers)
            
            # Asegurar que PI_Code y Proyecto existan
            if "PI_Code" not in df.columns: df["PI_Code"] = ""
            if "Proyecto" not in df.columns: df["Proyecto"] = ""
            
            # Convertir columnas numéricas (todo lo que no sea PI_Code o Proyecto)
            for col in df.columns:
                if col not in ["PI_Code", "Proyecto"]:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        if not df.empty:
            df['PI_Code'] = df['PI_Code'].astype(str)
            df['Proyecto'] = df['Proyecto'].astype(str)
            
        return df
    except Exception as e:
        st.error(f"Error cargando histórico de presupuestos: {e}")
        return pd.DataFrame()

def update_presupuesto_historico_batch(history_df):
    """Guarda el histórico de presupuestos respetando las columnas actuales del DataFrame."""
    worksheet = init_presupuesto_historico_sheet()
    if not worksheet: return False
    
    try:
        # Usar las columnas que vienen en el DataFrame (esto permite borrar/añadir columnas en la base)
        cols = list(history_df.columns)
        
        upload_df = history_df.copy()
        upload_df = upload_df.fillna(0)
        
        worksheet.clear()
        worksheet.update([cols] + upload_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error actualizando histórico de presupuestos en Sheets: {e}")
        return False

def update_materials_prevision(pi_code, updates):
    """
    Actualiza o añade materiales en la hoja principal 'Hoja 1' de PREVISIONES 2026.
    
    updates: lista de dicts {
        'matricula': str,
        'descripcion': str,
        'pu': float,
        'total_qty': float, # Cantidad anual nueva
        'total_valor': float, # Valor anual nuevo
        'is_new': bool
    }
    """
    gc = get_gspread_client()
    if not gc: return False, "Error de conexión"

    try:
        sh = gc.open("PREVISIONES 2026")
        worksheet = sh.worksheet("Hoja 1")
        all_data = worksheet.get_all_values(value_render_option='UNFORMATTED_VALUE')
        if len(all_data) < 2: return False, "Hoja vacía"

        headers = [str(h) for h in all_data[1]]
        
        # Encontrar índices de columnas clave
        def find_idx(keywords):
            for kw in keywords:
                for i, h in enumerate(headers):
                    if kw.lower() in str(h).lower(): return i
            return None

        idx_pi = find_idx(["codigo del proyecto", "proyecto"])
        idx_mat = find_idx(["matricula"])
        idx_desc = find_idx(["descripcion"])
        idx_año = find_idx(["año", "a±o"])
        idx_pu = find_idx(["p.u. s/."])
        idx_nombre = find_idx(["nombre del proyecto"])
        
        # Columnas de Cantidad (Ene, Feb...)
        MESES_COLS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        qty_indices = [find_idx([m]) for m in MESES_COLS]
        
        # Columnas de Valor (ene2, feb3...) - Siguiendo lógica de app.py y simulador.py
        VAL_COLS = ["ene2","feb3","mar4","abr5","may6","jun7","jul8","ago9","Sep30","oct11","nov12","dic13"]
        val_indices = [find_idx([v]) for v in VAL_COLS]

        cells_to_update = []
        new_rows = []
        
        pi_target = str(pi_code).strip().upper()
        
        # 1. Identificar filas existentes para los materiales en la lista de updates
        # Mapeo de matricula -> dict de update
        updates_map = {str(u['matricula']).strip(): u for u in updates}
        found_matriculas = set()

        for row_idx, row in enumerate(all_data):
            if row_idx < 2: continue # Saltar headers
            
            if idx_pi is not None and idx_pi < len(row):
                curr_pi = str(row[idx_pi]).strip().upper().replace('.0', '')
                if curr_pi == pi_target:
                    # Verificar año 2026
                    if idx_año is not None and idx_año < len(row) and str(row[idx_año]) == "2026":
                        curr_mat = str(row[idx_mat]).strip().replace('.0', '') if idx_mat is not None else ""
                        
                        if curr_mat in updates_map:
                            upd = updates_map[curr_mat]
                            found_matriculas.add(curr_mat)
                            
                            # Actualizar P.U.
                            if idx_pu is not None:
                                cells_to_update.append(gspread.Cell(row=row_idx+1, col=idx_pu+1, value=upd['pu']))
                            
                            # Distribuir cantidad y valor anual entre 12 meses
                            m_qty = upd['total_qty'] / 12
                            m_val = upd['total_valor'] / 12
                            
                            for i in range(12):
                                if qty_indices[i] is not None:
                                    cells_to_update.append(gspread.Cell(row=row_idx+1, col=qty_indices[i]+1, value=m_qty))
                                if val_indices[i] is not None:
                                    cells_to_update.append(gspread.Cell(row=row_idx+1, col=val_indices[i]+1, value=m_val))

        # 2. Manejar materiales nuevos que no se encontraron
        for mat, upd in updates_map.items():
            if mat not in found_matriculas:
                # Crear nueva fila
                new_row = [""] * len(headers)
                if idx_pi is not None: new_row[idx_pi] = pi_code
                if idx_mat is not None: new_row[idx_mat] = mat
                if idx_desc is not None: new_row[idx_desc] = upd['descripcion']
                if idx_año is not None: new_row[idx_año] = 2026
                if idx_pu is not None: new_row[idx_pu] = upd['pu']
                
                # Nombre del proyecto: intentar obtenerlo de la primera fila del PI encontrada
                # (O dejarlo vacío si no es crítico, o pasarlo como parámetro)
                
                m_qty = upd['total_qty'] / 12
                m_val = upd['total_valor'] / 12
                for i in range(12):
                    if qty_indices[i] is not None: new_row[qty_indices[i]] = m_qty
                    if val_indices[i] is not None: new_row[val_indices[i]] = m_val
                
                new_rows.append(new_row)

        # Ejecutar actualizaciones
        if cells_to_update:
            worksheet.update_cells(cells_to_update, value_input_option='RAW')
        
        if new_rows:
            worksheet.append_rows(new_rows, value_input_option='RAW')
            
        return True, "Cambios guardados correctamente."
    except Exception as e:
        return False, f"Error al guardar: {e}"
