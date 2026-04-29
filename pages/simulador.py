"""
Pagina del Simulador de Presupuesto (Multi-Proyecto)
Permite simular cambios masivos en el presupuesto y ver su impacto global y granular.
"""

import io
import re
import sys
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.append('..')
from components.charts import PALETTE
from utils.google_sheets_helper import get_manual_factors, update_manual_factors_batch, get_custom_kits, update_custom_kits_batch

# --- FUNCIONES DE SOPORTE ---

@st.cache_data
def to_excel(df_or_dict):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if isinstance(df_or_dict, pd.DataFrame):
            df_or_dict.to_excel(writer, index=False, sheet_name='Simulacion')
        elif isinstance(df_or_dict, dict):
            for sheet_name, df_sheet in df_or_dict.items():
                df_sheet.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def _normalize_code(val):
    return str(val).strip().upper().replace('.0', '')

def _find_col(df, keywords):
    for kw in keywords:
        for c in df.columns:
            if kw in c.lower():
                return c
    return None

import math

def apply_custom_rounding(data, columns=None, multiple=1, round_up=False):
    """Aplica redondeo por arrastre de decimales con regla: <= 0.5 redondea abajo.
    Si round_up=True, redondea hacia arriba al múltiplo especificado.
    Soporta tanto un DataFrame como una lista de valores.
    """
    multiple = float(multiple) if multiple > 0 else 1.0
    
    def _round_list(vals):
        carry = 0.0
        res = []
        for v_raw in vals:
            try:
                val = float(v_raw) + carry
                
                if val <= 0 and round_up:
                    res.append(0.0)
                    carry = val
                    continue
                    
                if round_up:
                    # Redondeo hacia arriba al múltiplo especificado
                    rounded = math.ceil(val / multiple) * multiple
                else:
                    # Redondeo normal (Regla: <= 0.7 hacia abajo)
                    base = math.floor(val / multiple) * multiple
                    diff = val - base
                    # Si el excedente es mayor al 70% del múltiplo, redondea arriba
                    rounded = base + multiple if diff > (0.7 * multiple) else base
                    
                res.append(rounded)
                carry = val - rounded
            except (ValueError, TypeError):
                res.append(v_raw)
        return res

    if isinstance(data, pd.DataFrame):
        if data.empty or columns is None: return data
        df_rounded = data.copy()
        for idx, row in df_rounded.iterrows():
            # Extraer solo los valores de las columnas indicadas
            vals_to_round = [row[c] for c in columns if c in df_rounded.columns]
            rounded_vals = _round_list(vals_to_round)
            
            # Reasignar al dataframe
            j = 0
            for c in columns:
                if c in df_rounded.columns:
                    df_rounded.at[idx, c] = rounded_vals[j]
                    j += 1
        return df_rounded
    else:
        # Asumimos que data es una lista o iterable
        return _round_list(data)


def get_desc_map(df_main=None):
    """Crea un mapa de Matricula -> Descripcion usando df_main y EMITIDO."""
    mapping = {}
    # 1. Desde el DataFrame principal del dashboard
    if df_main is not None and not df_main.empty and 'Matricula_Clean' in df_main.columns:
        # Intentar extraer solo la parte de texto si DESCRIPCION tiene formato "MAT - DESC"
        for mat, full_desc in zip(df_main['Matricula_Clean'], df_main['DESCRIPCION']):
            desc_text = str(full_desc)
            if ' - ' in desc_text:
                desc_text = desc_text.split(' - ', 1)[1]
            mapping[str(mat).strip()] = desc_text

    # 2. Desde la hoja EMITIDO (Seguimiento)
    try:
        from pages.prevision_vs_real import load_ejecutado
        df_real = load_ejecutado()
        if df_real is not None and not df_real.empty:
            id_col = None
            desc_col = None
            for c in df_real.columns:
                cl = c.lower()
                if cl in ['matricula', 'mat./prest.']: id_col = c
                if any(k in cl for k in ['descrip', 'breve', 'nombre']): desc_col = c
            
            if id_col and desc_col:
                for mat, desc in zip(df_real[id_col], df_real[desc_col]):
                    m_clean = str(mat).strip().replace('.0', '')
                    if m_clean not in mapping:
                        mapping[m_clean] = str(desc).strip()
    except Exception:
        pass
    return mapping

# --- BATCH UPDATE ---
def update_previsiones_sheet_batch(ratios_por_pi, kits_to_add=None, df_main=None):
    """Actualiza las cantidades mensuales en la hoja PREVISIONES 2026 y añade nuevos kits.
    
    kits_to_add: dict {pi_code: {materiales: [...], name: "...", series: [12 values]}}
    """
    gc = get_gspread_client()
    if not gc: return False, "Error autenticación Gspread"

    try:
        sh = gc.open("PREVISIONES 2026")
        worksheet = sh.worksheet("Hoja 1")
        all_data = worksheet.get_values(value_render_option='UNFORMATTED_VALUE')
        if len(all_data) < 2: return False, "Hoja vacía"

        headers = [str(h) for h in all_data[1]]
        codigo_idx = _find_col_idx(headers, ["codigo del proyecto", "proyecto"])
        año_idx = _find_col_idx(headers, ["año", "a±o"])
        
        # Columnas de Valor (ene2, feb3...)
        VAL_COLS = ["ene2","feb3","mar4","abr5","may6","jun7","jul8","ago9","Sep30","oct11","nov12","dic13"]
        val_indices = [_find_col_idx(headers, [v]) for v in VAL_COLS]
        
        ratios_norm = {str(k).strip().upper(): v for k, v in ratios_por_pi.items()}
        cells_to_update = []
        filas_actualizadas = 0
        existing_pis = set()

        # 1. ACTUALIZAR FILAS EXISTENTES
        for row_idx, row in enumerate(all_data):
            if row_idx < 2: continue # Saltar headers y helper
            
            if codigo_idx is not None and codigo_idx < len(row):
                pi_raw = str(row[codigo_idx]).strip().upper().replace('.0', '')
                existing_pis.add(pi_raw)
                
                if pi_raw in ratios_norm:
                    # Verificar que sea año 2026
                    if año_idx is not None and año_idx < len(row):
                        if str(row[año_idx]) == "2026":
                            filas_actualizadas += 1
                            ratio_data = ratios_norm[pi_raw]
                            for m_idx, col_idx in enumerate(val_indices):
                                if col_idx is not None and col_idx < len(row):
                                    val_orig = float(row[col_idx]) if row[col_idx] else 0
                                    # ratio_data es un dict {mes: ratio} o un valor global
                                    val_nuevo = val_orig * (ratio_data if isinstance(ratio_data, float) else 1.0)
                                    cells_to_update.append(
                                        gspread.Cell(row=row_idx + 1, col=col_idx + 1, value=val_nuevo)
                                    )

        if cells_to_update:
            worksheet.update_cells(cells_to_update, value_input_option='RAW')

        # 2. AÑADIR NUEVOS KITS
        filas_añadidas = 0
        if kits_to_add:
            desc_map = get_desc_map(df_main)
            new_rows = []
            
            idx_pi = codigo_idx
            idx_nombre = _find_col_idx(headers, ["nombre del proyecto"])
            idx_mat = _find_col_idx(headers, ["matricula"])
            idx_desc = _find_col_idx(headers, ["descripcion"])
            idx_año = año_idx
            idx_pu = _find_col_idx(headers, ["p.u. s/."])
            qty_cols = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
            qty_indices = [_find_col_idx(headers, [q]) for q in qty_cols]

            for pi_code, kit in kits_to_add.items():
                pi_clean = pi_code.strip().upper()
                if pi_clean not in existing_pis:
                    series_money = kit.get('series', [0]*12)
                    total_pi_money = sum(series_money)
                    
                    for m_item in kit['materiales']:
                        mat = str(m_item['Material']).strip().replace('.0', '')
                        desc = desc_map.get(mat, f"NUEVO MATERIAL - {mat}")
                        qty_total = float(m_item.get('Cantidad', 0))
                        pu = float(m_item.get('Precio_Unitario', 0))
                        
                        new_row = [""] * len(headers)
                        if idx_pi is not None: new_row[idx_pi] = pi_code
                        if idx_nombre is not None: new_row[idx_nombre] = kit['name']
                        if idx_mat is not None: new_row[idx_mat] = mat
                        if idx_desc is not None: new_row[idx_desc] = desc
                        if idx_año is not None: new_row[idx_año] = 2026
                        if idx_pu is not None: new_row[idx_pu] = pu
                        
                        # 1. Calcular proporciones y cantidades brutas para los 12 meses
                        raw_qtys = []
                        for i in range(12):
                            if total_pi_money > 0:
                                prop = series_money[i] / total_pi_money
                                raw_qtys.append(qty_total * prop)
                            else:
                                raw_qtys.append(0.0)
                        
                        # 2. Aplicar redondeo por arrastre a las cantidades (Regla: 0.5 al más cercano)
                        m_val = 1
                        rounded_qtys = apply_custom_rounding(raw_qtys, multiple=m_val, round_up=False)
                        
                        # 3. Asignar valores a la fila (Cantidades y Montos proporcionales a lo redondeado)
                        for i in range(12):
                            m_qty = rounded_qtys[i]
                            m_money = m_qty * pu
                            
                            if i < len(qty_indices) and qty_indices[i] is not None:
                                new_row[qty_indices[i]] = m_qty
                            if i < len(val_indices) and val_indices[i] is not None:
                                new_row[val_indices[i]] = m_money

                        
                        new_rows.append(new_row)
                        filas_añadidas += 1
            
            if new_rows:
                worksheet.append_rows(new_rows, value_input_option='RAW')

        return True, f"✅ Guardado exitoso: {filas_actualizadas} filas actualizadas y {filas_añadidas} filas nuevas añadidas."
    except Exception as e:
        return False, f"Error actualizando Google Sheets: {e}"

def _find_col_idx(headers, keywords):
    for kw in keywords:
        for i, h in enumerate(headers):
            if kw.lower() in str(h).lower():
                return i
    return None

# --- CARGA DE DATOS ---

@st.cache_data(ttl=3600)
def load_all_factors():
    """Carga factores de materiales para todos los PIs desde el archivo '2025'."""
    import gspread
    from google.oauth2.service_account import Credentials
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        gc = gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
        sh = gc.open("2025")
        ws = sh.get_worksheet(0)
        data = ws.get(value_render_option='UNFORMATTED_VALUE')
        if not data: return {}
        
        df = pd.DataFrame(data[1:], columns=[str(h) for h in data[0]])
        precio_col = _find_col(df, ['precio total ed', 'precio total e', 'precio total'])
        tipo_col = _find_col(df, ['tipo'])
        pi_col = next((c for c in ['PI', 'Codigo del Proyecto', 'Código del Proyecto'] if c in df.columns), None)
        
        if not pi_col or not precio_col: return {}

        df[precio_col] = pd.to_numeric(df[precio_col], errors='coerce').fillna(0)
        df['_pi_clean'] = df[pi_col].apply(_normalize_code)
        
        factors = {}
        for pi, g in df.groupby('_pi_clean'):
            total = g[precio_col].sum()
            if total > 0:
                if tipo_col:
                    mask_mat = g[tipo_col].astype(str).str.lower().str.contains('material', na=False)
                    mat = g.loc[mask_mat, precio_col].sum()
                    factors[pi] = mat / total
                else:
                    factors[pi] = 1.0 # Default si no hay columna tipo
            else:
                factors[pi] = 0.7 # Default fallback
        return factors
    except Exception:
        return {}

@st.cache_data(ttl=3600)
def load_all_emitido():
    """Carga toda la base de EMITIDO."""
    import gspread
    from google.oauth2.service_account import Credentials
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        gc = gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
        sh = gc.open("EMITIDO")
        ws = sh.get_worksheet(0)
        data = ws.get(value_render_option='UNFORMATTED_VALUE')
        if not data: return pd.DataFrame()
        return pd.DataFrame(data[1:], columns=[str(h) for h in data[0]])
    except Exception:
        return pd.DataFrame()

def get_emitido_series(df_emitido, pi_code, meses):
    result = {m: 0.0 for m in meses}
    if df_emitido is None or df_emitido.empty: return result
    
    val_col = _find_col(df_emitido, ['precio total ed', 'precio total e', 'precio total'])
    fecha_col = _find_col(df_emitido, ['fecha'])
    pi_col = next((c for c in ['Codigo del Proyecto', 'Código del Proyecto', 'PI', 'elemento pep'] if c in df_emitido.columns), None)
    
    if not val_col or not fecha_col or not pi_col: return result

    de = df_emitido.copy()
    
    # Limpiar columna valor (puede traer S/ u otros caracteres si el render option falló)
    cleaned_val = de[val_col].astype(str).str.replace(r'^S/\s*', '', regex=True)
    cleaned_val = cleaned_val.str.replace(',', '.', regex=False).str.strip()
    de[val_col] = pd.to_numeric(cleaned_val, errors='coerce').fillna(0)
    
    de = de[de[pi_col].apply(_normalize_code) == _normalize_code(pi_code)]
    
    if de.empty: return result

    # Procesar fechas
    fechas_num = pd.to_numeric(de[fecha_col], errors='coerce')
    mask_serial = fechas_num > 30000
    fc = pd.to_datetime(fechas_num[mask_serial] - 2, unit='D', origin='1900-01-01')
    ft = pd.to_datetime(de.loc[~mask_serial, fecha_col].astype(str), dayfirst=True, errors='coerce')
    de['_f'] = pd.concat([fc, ft])
    de = de.dropna(subset=['_f'])
    
    # Regla: Dic 2025 -> Ene 2026
    de['Year'] = de['_f'].dt.year
    de['Month'] = de['_f'].dt.month
    de.loc[(de['Year'] == 2025) & (de['Month'] == 12), 'Month'] = 1
    
    month_map = {i+1: m for i, m in enumerate(meses)}
    de['_m'] = de['Month'].map(month_map)
    
    for m in meses:
        result[m] = de.loc[de['_m'] == m, val_col].sum()
    return result

# --- LOGICA DE SIMULACION ---

def build_pi_series(df_pi_original, emitido_dict, pres_mat_simulado, cutoff_idx, meses, perfil='Original', mes_fin='Dic'):
    orig = [df_pi_original[f'Valor_{m}'].sum() if f'Valor_{m}' in df_pi_original.columns else 0.0 for m in meses]
    
    # --- APLICAR PERFIL SINTÉTICO SI NO ES ORIGINAL ---
    if perfil != 'Original':
        try:
            mes_fin_idx = meses.index(mes_fin)
        except ValueError:
            mes_fin_idx = 11
        
        # Reiniciar orig a 0 para construirlo sintéticamente
        orig = [0.0] * 12
        
        # Llenar la curva solo en el tramo [cutoff_idx+1 ... mes_fin_idx]
        for i in range(cutoff_idx + 1, mes_fin_idx + 1):
            if perfil == 'Lineal':
                orig[i] = 1.0  # Pesos iguales
            elif perfil == 'Creciente':
                # Sucesión aritmética: 1, 2, 3...
                orig[i] = float(i - cutoff_idx)
            elif perfil == 'Montaña':
                # Lógica 10-80-10 para los meses en el rango
                total_meses_futuros = mes_fin_idx - cutoff_idx
                idx_en_rango = i - (cutoff_idx + 1)
                
                if total_meses_futuros == 3:
                    pesos_montana = [0.10, 0.80, 0.10]
                    orig[i] = pesos_montana[idx_en_rango]
                elif total_meses_futuros < 3:
                    orig[i] = 1.0 # Lineal si hay poco espacio
                else:
                    # Si hay más de 3, poner el pico en el medio
                    mid = total_meses_futuros // 2
                    if idx_en_rango == mid:
                        orig[i] = 0.80
                    else:
                        orig[i] = 0.20 / (total_meses_futuros - 1)
    
    serie = []
    total_real = 0.0
    
    for i, m in enumerate(meses):
        if i <= cutoff_idx:
            v = emitido_dict.get(m, 0.0)
            serie.append(v)
            total_real += v
        else:
            serie.append(None)

    saldo = pres_mat_simulado - total_real
    saldo_calculo = max(0.0, saldo)
    rest_idx = list(range(cutoff_idx + 1, len(meses)))
    pesos = [orig[i] for i in rest_idx]
    total_pesos = sum(pesos)
    
    ratios = {}

    for j, i in enumerate(rest_idx):
        if total_pesos > 0:
            w = pesos[j] / total_pesos
        else:
            # Fallback: Distribución equitativa si no hay pesos definidos
            w = 1.0 / len(rest_idx) if rest_idx else 0.0
        serie[i] = saldo_calculo * w

    for i, m in enumerate(meses):
        if i <= cutoff_idx:
            v_orig = orig[i]
            ratios[m] = (emitido_dict.get(m, 0.0) / v_orig) if v_orig > 0 else 1.0
        else:
            if perfil != 'Original':
                # Para perfiles sintéticos: ratio = peso normalizado de la curva (fracción del total futuro)
                # Así Sim_m = qty_total_futuro * ratio[m] → preserva el total, solo redistribuye
                total_serie_futuro = sum(serie[j] for j in range(cutoff_idx + 1, len(meses)))
                ratios[m] = (serie[i] / total_serie_futuro) if total_serie_futuro > 0 else 0.0
            else:
                # Para perfil Original: ratio = dinero_simulado / dinero_planificado_original
                v_orig = orig[i]
                ratios[m] = (serie[i] / v_orig) if v_orig > 0 else 0.0

    is_synthetic = (perfil != 'Original')
    return serie, orig, total_real, saldo, ratios, is_synthetic

# --- INTERFAZ PRINCIPAL ---

def show(df, apply_filters):
    st.title("Gestor de Previsiones")
    MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
    df_f = apply_filters(df).copy()
    if df_f.empty:
        st.warning("No hay datos con los filtros seleccionados.")
        return

    # 1. Configuración Global
    col_c1, col_c2, col_upd = st.columns([2, 2, 1])
    MESES_OPCIONES = ["Ninguno"] + MESES
    with col_c1:
        mes_corte = st.selectbox("📅 Mes de Corte (Límite ejecución real):", MESES_OPCIONES, index=3) # Por defecto Mar (index 3)
    
    if mes_corte == "Ninguno":
        cutoff_idx = -1
    else:
        cutoff_idx = MESES.index(mes_corte)
    
    with col_upd:
        st.write("")
        st.write("")
        if st.button("🔄 Refrescar Sheets"):
            load_all_factors.clear()
            load_all_emitido.clear()
            st.rerun()

    # --- SECCIÓN: CONFIGURACIONES AVANZADAS ---
    with st.expander("⚙️ Configuraciones Avanzadas (Factores Manuales y Kits)"):
        st.markdown("Ajustes permanentes que se guardan en la base de datos (Google Sheets).")
        
        tab_factores, tab_kits = st.tabs(["📊 Factores Manuales", "📦 Kits de Materiales"])
        
        with tab_factores:
            st.markdown("**Prioridad Alta:** Si un PI está aquí, se ignora el factor automático.")
            if 'manual_factors' not in st.session_state:
                with st.spinner("Cargando factores guardados..."):
                    st.session_state['manual_factors'] = get_manual_factors()
            
            overrides_df = st.data_editor(
                st.session_state['manual_factors'],
                column_config={
                    "PI_Code": st.column_config.TextColumn("Código PI"),
                    "Factor_Manual": st.column_config.NumberColumn("Factor (0.0 a 1.0)", format="%.4f", min_value=0.0, max_value=1.0, step=0.0001)
                },
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                key="overrides_editor"
            )
            st.session_state['manual_factors'] = overrides_df
            
            col_save_f, _ = st.columns([1, 2])
            with col_save_f:
                if st.button("💾 Guardar Factores en Drive", use_container_width=True):
                    if update_manual_factors_batch(overrides_df):
                        st.success("Factores guardados permanentemente.")
                        st.rerun()

            manual_map = dict(zip(
                overrides_df['PI_Code'].apply(_normalize_code), 
                overrides_df['Factor_Manual']
            ))

        with tab_kits:
            st.markdown("**Proyectos Nuevos:** Define el 'ADN' de materiales para PIs que no tienen previsión base.")
            if 'custom_kits' not in st.session_state:
                with st.spinner("Cargando kits personalizados..."):
                    st.session_state['custom_kits'] = get_custom_kits()

            # --- CARGA MASIVA ---
            with st.expander("🚀 Carga Masiva de Materiales", expanded=False):
                st.markdown("""
                Pega datos directamente desde Excel. El formato esperado es **7 columnas sin encabezado**:
                
                `PI` | `Proyecto` | `Sección` | `Matrícula` | `Descripción` | `Cant.` | `Precio Unit.`
                
                > **Tip:** Selecciona las celdas en Excel y pega aquí (Ctrl+V). Si no tienes sección o proyecto, deja la celda vacía en Excel.
                """)
                raw_paste = st.text_area(
                    "Pega los datos aquí:",
                    height=180,
                    placeholder="PI-001\tNombre Proy\tSección A\tMAT001\tCABLE 10mm\t50\t12.5",
                    key="bulk_paste_area"
                )
                col_bulk_btn, col_bulk_msg = st.columns([1, 3])
                with col_bulk_btn:
                    procesar_bulk = st.button("⚡ Procesar y Añadir", use_container_width=True, key="btn_bulk_load")
                
                if procesar_bulk and bulk_paste_area.strip():
                    nuevas_filas = []
                    errores = []
                    lineas = bulk_paste_area.strip().splitlines()
                    for i, linea in enumerate(lineas):
                        # Aceptar separación por tab (Excel) o punto y coma
                        partes = linea.replace(";", "\t").split("\t")
                        partes = [p.strip() for p in partes]
                        
                        # Limpiar celdas vacías al final que a veces vienen de Excel
                        if len(partes) > 5 and all(not p for p in partes[5:]):
                            partes = partes[:5]
                            
                        if len(partes) < 2: # Saltar líneas vacías
                            continue
                            
                        if len(partes) < 5:
                            errores.append(f"Línea {i+1}: Se esperan al menos 5 columnas (PI, Matrícula, Desc, Cant, Precio) o idealmente 7 (PI, Proyecto, Sección, Matrícula, Desc, Cant, Precio). Encontradas: {len(partes)}")
                            continue
                            
                        try:
                            # Manejar formatos de número con comas y puntos
                            def clean_num(val):
                                if not val: return 0.0
                                return float(str(val).replace("S/", "").replace("S/.", "").replace(" ", "").replace(",", ".").strip())

                            if len(partes) >= 7:
                                pi_code = partes[0].upper().replace(".0", "")
                                proyecto = partes[1].strip()
                                seccion = partes[2].strip()
                                matricula = partes[3].strip().replace(".0", "")
                                descripcion = partes[4].strip()
                                cantidad = clean_num(partes[5])
                                precio = clean_num(partes[6])
                            else:
                                # Fallback a 5 columnas (PI, Matrícula, Desc, Cant, Precio)
                                pi_code = partes[0].upper().replace(".0", "")
                                proyecto = ""
                                seccion = ""
                                matricula = partes[1].strip().replace(".0", "")
                                descripcion = partes[2].strip()
                                cantidad = clean_num(partes[3])
                                precio = clean_num(partes[4])
                            
                            nuevas_filas.append({
                                "PI_Code": pi_code,
                                "Proyecto": proyecto,
                                "Seccion": seccion,
                                "Material": matricula,
                                "Descripcion": descripcion,
                                "Cantidad": cantidad,
                                "Precio_Unitario": precio
                            })
                        except Exception as e:
                            errores.append(f"Línea {i+1}: Error en datos ({partes}) — {e}")
                    
                    if nuevas_filas:
                        df_preview = pd.DataFrame(nuevas_filas)
                        st.session_state['bulk_preview_df'] = df_preview
                        
                if 'bulk_preview_df' in st.session_state:
                    st.markdown("### 🔍 Previsualización de Carga")
                    st.dataframe(st.session_state['bulk_preview_df'], use_container_width=True, hide_index=True)
                    
                    col_conf, col_can = st.columns(2)
                    with col_conf:
                        if st.button("✅ Confirmar y Añadir a la Tabla", use_container_width=True):
                            existing = st.session_state.get('custom_kits', pd.DataFrame())
                            st.session_state['custom_kits'] = pd.concat([existing, st.session_state['bulk_preview_df']], ignore_index=True)
                            del st.session_state['bulk_preview_df']
                            st.success("¡Datos añadidos! No olvides guardar en Drive al finalizar.")
                            st.rerun()
                    with col_can:
                        if st.button("❌ Cancelar", use_container_width=True):
                            del st.session_state['bulk_preview_df']
                            st.rerun()
                            
                    if errores:
                        with col_bulk_msg:
                            for e in errores:
                                st.warning(e)

            kits_df = st.data_editor(
                st.session_state['custom_kits'],
                column_config={
                    "PI_Code": st.column_config.TextColumn("Código PI"),
                    "Proyecto": st.column_config.TextColumn("Nombre del Proyecto"),
                    "Seccion": st.column_config.TextColumn("Sección"),
                    "Material": st.column_config.TextColumn("Matrícula"),
                    "Descripcion": st.column_config.TextColumn("Descripción del Material"),
                    "Cantidad": st.column_config.NumberColumn("Cant. Base", min_value=0.0, format="%.2f"),
                    "Precio_Unitario": st.column_config.NumberColumn("Precio Unitario (S/.)", min_value=0.0, format="S/ %.2f")
                },
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                key="kits_editor"
            )
            st.session_state['custom_kits'] = kits_df
            
            col_save_k, _ = st.columns([1, 2])
            with col_save_k:
                if st.button("💾 Guardar Kits en Drive", use_container_width=True):
                    if update_custom_kits_batch(kits_df):
                        st.success("Kits guardados permanentemente.")
                        st.rerun()

    with st.spinner("Cargando referencias de Google Sheets (2025 y EMITIDO)..."):
        factors_map = load_all_factors()
        df_emitido_all = load_all_emitido()

    # 2. Preparar datos de la tabla
    if 'Codigo del Proyecto' not in df_f.columns:
        st.error("Falta la columna 'Codigo del Proyecto' en la base.")
        return

    df_f['_pi_code'] = df_f['Codigo del Proyecto'].apply(_normalize_code)
    
    # Agrupar por PI para la tabla
    pi_data = df_f.groupby(['_pi_code', 'Nombre del proyecto']).agg({
        'Valor_Anual': 'sum'
    }).reset_index()
    
    # Filter out empty or null project codes
    pi_data = pi_data[pi_data['_pi_code'] != '']
    
    # --- INYECTAR PIs DE KITS NUEVOS ---
    if 'custom_kits' in st.session_state and not st.session_state['custom_kits'].empty:
        # Obtener mapeo de PI -> Nombre de Proyecto desde la tabla de kits
        kit_meta = st.session_state['custom_kits'][['PI_Code', 'Proyecto']].dropna().drop_duplicates(subset=['PI_Code'])
        kit_meta['PI_Code'] = kit_meta['PI_Code'].apply(_normalize_code)
        kit_meta_dict = dict(zip(kit_meta['PI_Code'], kit_meta['Proyecto']))
        
        kit_pis = st.session_state['custom_kits']['PI_Code'].dropna().astype(str).unique()
        existing_pis = pi_data['_pi_code'].values
        
        missing_pis = [pi for pi in kit_pis if _normalize_code(pi) not in existing_pis and _normalize_code(pi) != '']
        
        if missing_pis:
            new_rows = pd.DataFrame({
                '_pi_code': [_normalize_code(pi) for pi in missing_pis],
                'Nombre del proyecto': [kit_meta_dict.get(_normalize_code(pi), "(Nuevo Proyecto desde Kit)") for pi in missing_pis],
                'Valor_Anual': [0.0] * len(missing_pis)
            })
            pi_data = pd.concat([pi_data, new_rows], ignore_index=True)
            
    # Factorizar para evitar divisiones por cero
    # Primero aplicamos el factor de Sheets, luego el manual (que manda)
    pi_data['Factor Materiales'] = pi_data['_pi_code'].map(factors_map).fillna(0.7)
    
    # Aplicar Overrides Manuales si existen
    for pi_c, f_m in manual_map.items():
        mask = pi_data['_pi_code'] == pi_c
        if mask.any():
            pi_data.loc[mask, 'Factor Materiales'] = f_m

    # Evitar ceros exactos para la división
    pi_data['Factor Seguro'] = pi_data['Factor Materiales'].replace(0, 0.0001)
    
    pi_data = pi_data.rename(columns={'Valor_Anual': 'Presupuesto Actual'})
    
    # Limpiar el nombre del proyecto para visualización (quitar el [PI] si existe)
    pi_data['Nombre del proyecto'] = pi_data['Nombre del proyecto'].str.replace(r'^\[.*?\]\s*', '', regex=True)
    
    # Inicializar columnas editables con valores por defecto.
    # El st.data_editor con key persistirá los cambios del usuario automáticamente.
    pi_data['Nuevo Presupuesto Total'] = None
    pi_data['Restar a Materiales'] = None
    pi_data['Perfil Curva'] = 'Original'
    pi_data['Mes Fin'] = 'Dic'
    
    # 3. Editor de Datos
    st.subheader("Panel de Ajuste Presupuestario")
    st.markdown("Edita la columna **Nuevo Total PI** para simular escenarios. Los proyectos seleccionados se sumarán en el gráfico global.")
    
    edited_df = st.data_editor(
        pi_data,
        column_config={
            "_pi_code": st.column_config.TextColumn("PI", disabled=True),
            "Nombre del proyecto": st.column_config.TextColumn("Proyecto", disabled=True, width="large"),
            "Factor Materiales": st.column_config.NumberColumn("Factor Mat.", format="%.2f", disabled=True),
            "Factor Seguro": None,  # Ocultar columna interna
            "Presupuesto Actual": st.column_config.NumberColumn("Presup. Mat. Orig (S/.)", format="S/ %,.0f", disabled=True),
            "Nuevo Presupuesto Total": st.column_config.NumberColumn("Nuevo Total PI (S/.)", format="S/ %,.0f", min_value=0.0),
            "Restar a Materiales": st.column_config.NumberColumn("Restar a Mat. (S/.)", format="S/ %,.0f", min_value=0.0),
            "Perfil Curva": st.column_config.SelectboxColumn("Perfil Curva", options=["Original", "Lineal", "Creciente", "Montaña"]),
            "Mes Fin": st.column_config.SelectboxColumn("Mes Fin", options=MESES[max(0, cutoff_idx+1):])
        },
        hide_index=True,
        use_container_width=True,
        height=400,
        key="sim_table_editor"
    )

    # Calcular Simulado Materiales
    # Si ingresó un Nuevo Total, se usa (Total * Factor). Si está vacío, se mantiene el Presupuesto Actual intacto.
    import numpy as np
    cond_modificado = edited_df['Nuevo Presupuesto Total'].notna() & (edited_df['Nuevo Presupuesto Total'] > 0)
    base_materiales = np.where(
        cond_modificado,
        edited_df['Nuevo Presupuesto Total'] * edited_df['Factor Materiales'],
        edited_df['Presupuesto Actual']
    )
    
    valor_restar = edited_df['Restar a Materiales'].fillna(0)
    edited_df['Simulado Materiales'] = base_materiales - valor_restar
    edited_df['Simulado Materiales'] = edited_df['Simulado Materiales'].clip(lower=0)
    
    # Identificar filas que han sido modificadas comparando con Presupuesto Actual
    # Asumimos que la simulación es para los que se ha modificado el Nuevo Presupuesto,
    # pero mostraremos la simulación global considerando los valores editados de todos.
    
    # 4. Cálculo Global para Gráfico Superior
    # --- PROCESAMIENTO 100% EMPRESA (Sin Filtros) ---
    global_orig = [0.0]*12
    global_real = [0.0]*12
    
    # 1. Base 100% Original
    for i, m in enumerate(MESES):
        col_m = f'Valor_{m}'
        if col_m in df.columns:
            global_orig[i] = df[col_m].sum()

    # 2. Base 100% Real Emitido (Monto Bruto Total)
    global_real = [0.0]*12
    if df_emitido_all is not None and not df_emitido_all.empty:
        val_col_e = _find_col(df_emitido_all, ['precio total ed', 'precio total e', 'precio total'])
        fecha_col_e = _find_col(df_emitido_all, ['fecha'])
        if val_col_e and fecha_col_e:
            de_all = df_emitido_all.copy()
            cleaned_val = de_all[val_col_e].astype(str).str.replace(r'^S/\s*', '', regex=True)
            cleaned_val = cleaned_val.str.replace(',', '.', regex=False).str.strip()
            de_all[val_col_e] = pd.to_numeric(cleaned_val, errors='coerce').fillna(0)
            
            fechas_num = pd.to_numeric(de_all[fecha_col_e], errors='coerce')
            mask_serial = fechas_num > 30000
            fc = pd.to_datetime(fechas_num[mask_serial] - 2, unit='D', origin='1900-01-01')
            ft = pd.to_datetime(de_all.loc[~mask_serial, fecha_col_e].astype(str), dayfirst=True, errors='coerce')
            de_all['_f'] = pd.concat([fc, ft])
            de_all = de_all.dropna(subset=['_f'])
            
            de_all['Year'] = de_all['_f'].dt.year
            de_all['Month'] = de_all['_f'].dt.month
            de_all.loc[(de_all['Year'] == 2025) & (de_all['Month'] == 12), 'Month'] = 1
            
            month_map = {i+1: m for i, m in enumerate(MESES)}
            de_all['_m'] = de_all['Month'].map(month_map)
            
            for i, m in enumerate(MESES):
                if i <= cutoff_idx:
                    global_real[i] = de_all.loc[de_all['_m'] == m, val_col_e].sum()

    # 3. Base Simulado Inicial (Macro Auto-corrección Bruta 100% Empresa)
    global_sim_only = [0.0]*12
    
    total_global_orig = sum(global_orig)
    total_global_real = sum(global_real)
    global_saldo = total_global_orig - total_global_real
    futuro_orig_sum = sum(global_orig[cutoff_idx+1:])
    
    macro_k = (global_saldo / futuro_orig_sum) if futuro_orig_sum > 0 else 0.0
    
    # Mostrar métricas globales antes del gráfico
    st.markdown(f"### Resumen Global hasta {mes_corte}")
    st.caption("Comparativa del presupuesto total planificado vs el gasto real acumulado.")
    g0, g1, g2, g3 = st.columns(4)
    
    g0.metric("Presupuesto General (Anual)", f"S/ {total_global_orig:,.0f}")
    
    previsto_hasta_corte = sum(global_orig[:cutoff_idx+1])
    g1.metric(f"Plan Original (Ene-{mes_corte})", f"S/ {previsto_hasta_corte:,.0f}")
    
    # Si mes_corte es Ninguno, el emitido a mostrar es 0 para el periodo de "corte"
    emitido_hasta_corte = total_global_real if cutoff_idx >= 0 else 0.0
    g2.metric(f"Emitido Bruto (Ene-{mes_corte})", f"S/ {emitido_hasta_corte:,.0f}")
    
    # Si emitido > previsto, el desvío es positivo (sobregasto)
    desvio_monto = emitido_hasta_corte - previsto_hasta_corte
    # En delta, si el monto es positivo (sobregasto), queremos que salga en ROJO.
    # Por eso usamos delta_color="inverse".
    g3.metric("Desvío Acumulado", f"S/ {abs(desvio_monto):,.0f}", 
              delta=f"{'+' if desvio_monto > 0 else '-'}$ {abs(desvio_monto):,.0f}" if mes_corte != "Ninguno" else None, 
              delta_color="inverse")
    
    for i in range(cutoff_idx + 1, 12):
        if futuro_orig_sum > 0:
            global_sim_only[i] = global_orig[i] * macro_k
        else:
            rest_months = 12 - (cutoff_idx + 1)
            global_sim_only[i] = global_saldo / rest_months if rest_months > 0 else 0.0

    global_export_list = []
    all_materials_export = []
    ratios_batch_update = {}
    
    def extract_mat_desc(val, df_ref):
        val_str = str(val).strip()
        parts = val_str.split(' - ', 1)
        matricula = parts[0]
        descripcion = parts[1] if len(parts) > 1 else ""
        unidad = "UND"
        
        if 'Matricula_Clean' in df_ref.columns:
            match = df_ref[df_ref['Matricula_Clean'] == matricula]
            if not match.empty:
                full_desc = match['DESCRIPCION'].iloc[0]
                desc_parts = str(full_desc).split(' - ', 1)
                descripcion = desc_parts[1] if len(desc_parts) > 1 else str(full_desc)
                if 'UNIDAD' in df_ref.columns:
                    u_val = match['UNIDAD'].iloc[0]
                    if pd.notna(u_val) and str(u_val).strip() != "":
                        unidad = str(u_val).strip()
        
        if not descripcion:
            descripcion = val_str
            
        return matricula, descripcion, unidad
    
    # 4. Iterar sobre la tabla para aplicar los deltas de la simulación manual
    for _, row in edited_df.iterrows():
        pi = row['_pi_code']
        pi_norm = _normalize_code(pi)
        
        # Buscar en df completo
        pi_col_df = next((c for c in ['PI', 'Codigo del Proyecto', 'Código del Proyecto'] if c in df.columns), None)
        if pi_col_df:
            df_pi = df[df[pi_col_df].apply(_normalize_code) == pi_norm]
        else:
            df_pi = pd.DataFrame()
            
        emitido_pi = get_emitido_series(df_emitido_all, pi, MESES)
        
        perfil_curva = row.get('Perfil Curva', 'Original')
        mes_fin = row.get('Mes Fin', 'Dic')
        
        # Verificar si el usuario ha modificado este PI manualmente
        es_modificado = (pd.notna(row.get('Nuevo Presupuesto Total')) and row['Nuevo Presupuesto Total'] > 0) or \
                        (pd.notna(row.get('Restar a Materiales')) and row['Restar a Materiales'] > 0) or \
                        (perfil_curva != 'Original') or \
                        (mes_fin != 'Dic')
        
        serie_pi, orig_pi, _, saldo_pi_val, ratios_pi, is_synthetic_pi = build_pi_series(
            df_pi, emitido_pi, row['Simulado Materiales'], cutoff_idx, MESES, perfil_curva, mes_fin
        )
        
        # --- RECOLECTAR PARA EXCEL GLOBAL ---
        total_emitido_pi = sum(emitido_pi.get(m, 0.0) for i, m in enumerate(MESES) if i <= cutoff_idx)
        exp_item = {
            'PI': pi,
            'Proyecto': row['Nombre del proyecto'],
            'Factor Aplicado': row['Factor Materiales'],
            'Presup. Original Mat.': row['Presupuesto Actual'],
            'Total Emitido (Ene-Corte)': total_emitido_pi,
            'Nuevo Presup. Mat.': row['Simulado Materiales'],
            'Saldo a Distribuir': saldo_pi_val,
            'Perfil': perfil_curva,
            'Mes Fin': mes_fin
        }
        for i, m in enumerate(MESES):
            exp_item[m] = serie_pi[i]
        global_export_list.append(exp_item)
        
        # --- RECOLECTAR MATERIALES PARA EXCEL GLOBAL ---
        df_mat_g = df_pi.copy()
        col_seccion_g = next((c for c in df_mat_g.columns if 'SECCION' in c.upper() or 'SECCIÓN' in c.upper()), None)
        
        valor_anual_base_g = df_mat_g[[f'Valor_{m}' for m in MESES if f'Valor_{m}' in df_mat_g.columns]].sum().sum() if not df_mat_g.empty else 0.0
        saldo_a_distribuir_g = saldo_pi_val if saldo_pi_val > 0 else 0.0

        if valor_anual_base_g == 0:
            kits_state_g = st.session_state.get('custom_kits', pd.DataFrame())
            pi_kit_g = kits_state_g[kits_state_g['PI_Code'] == pi_norm].copy()
            if not pi_kit_g.empty:
                pi_kit_g['Cantidad'] = pd.to_numeric(pi_kit_g['Cantidad'], errors='coerce').fillna(0).astype(float)
                pi_kit_g['Precio_Unitario'] = pd.to_numeric(pi_kit_g['Precio_Unitario'], errors='coerce').fillna(0).astype(float)
                pi_kit_g['Costo_Total'] = pi_kit_g['Cantidad'] * pi_kit_g['Precio_Unitario']
                
                costo_total_kit_g = pi_kit_g['Costo_Total'].sum()
                if costo_total_kit_g > 0:
                    pi_kit_g['Participacion'] = pi_kit_g['Costo_Total'] / costo_total_kit_g
                else:
                    total_qty_kit = pi_kit_g['Cantidad'].sum()
                    pi_kit_g['Participacion'] = (pi_kit_g['Cantidad'] / total_qty_kit) if total_qty_kit > 0 else 0.0

                for _, k_row in pi_kit_g.iterrows():
                    mat_val = k_row['Material']
                    # Si el kit tiene descripción propia, usarla; si no, buscar en base
                    if pd.notna(k_row.get('Descripcion')) and str(k_row['Descripcion']).strip() != "":
                        matricula = str(mat_val)
                        descripcion = str(k_row['Descripcion'])
                        unidad = "UND" # O intentar inferir si es crítico
                    else:
                        matricula, descripcion, unidad = extract_mat_desc(mat_val, df)
                        
                    mat_item = {
                        'PI': pi,
                        'SECCION': k_row.get('Seccion', 'KIT NUEVO'),
                        'MATRICULA': matricula,
                        'DESCRIPCION': descripcion,
                        'UNIDADES': unidad,
                        'PRECIO UNITARIO': k_row['Precio_Unitario']
                    }
                    total_pi_money = sum(serie_pi)
                    raw_qtys = []
                    for i, m in enumerate(MESES):
                        if k_row['Precio_Unitario'] > 0:
                            raw_qtys.append((serie_pi[i] * k_row['Participacion']) / k_row['Precio_Unitario'])
                        else:
                            dist_prop = (serie_pi[i] / total_pi_money) if total_pi_money > 0 else 0.0
                            raw_qtys.append(k_row['Cantidad'] * dist_prop)
                    
                    m_val = 1
                    rounded_qtys = apply_custom_rounding(raw_qtys, multiple=m_val, round_up=False)
                    for i, m in enumerate(MESES):
                        mat_item[m] = rounded_qtys[i]
                    all_materials_export.append(mat_item)
        else:
            col_multiplo = next((c for c in df_mat_g.columns if 'MULTIPLO' in c.upper() or 'REDONDEO' in c.upper()), None)
            if col_multiplo:
                df_mat_g['MULT'] = pd.to_numeric(df_mat_g[col_multiplo], errors='coerce').fillna(1).apply(lambda x: max(1, x))
            else:
                df_mat_g['MULT'] = 1.0

            for i, m in enumerate(MESES):
                col_cant = f'Cant_{m}'
                if col_cant in df_mat_g.columns:
                    if is_synthetic_pi:
                        # Perfil sintético: preservar total de cantidades, solo redistribuir por pesos de la curva
                        # Se calcula abajo por fila después del groupby
                        df_mat_g[f'Sim_{m}'] = df_mat_g[col_cant]  # placeholder, se sobreescribe
                    else:
                        df_mat_g[f'Sim_{m}'] = df_mat_g[col_cant] * ratios_pi[m]
                else:
                    df_mat_g[f'Sim_{m}'] = 0.0

            # Para perfil sintético: calcular qty_total_futuro por material y redistribuir
            if is_synthetic_pi:
                future_cant_cols = [f'Cant_{m}' for i, m in enumerate(MESES) if i > cutoff_idx and f'Cant_{m}' in df_mat_g.columns]
                df_mat_g['_qty_fut_total'] = df_mat_g[future_cant_cols].sum(axis=1) if future_cant_cols else 0.0
                # Calcular el factor global de escala del presupuesto
                valor_cols_fut = [f'Valor_{m}' for i, m in enumerate(MESES) if i > cutoff_idx and f'Valor_{m}' in df_mat_g.columns]
                total_money_orig_fut = df_mat_g[valor_cols_fut].sum().sum() if valor_cols_fut else 0.0
                budget_scale = (saldo_pi_val / total_money_orig_fut) if total_money_orig_fut > 0 else 1.0
                for i, m in enumerate(MESES):
                    if i > cutoff_idx:
                        df_mat_g[f'Sim_{m}'] = df_mat_g['_qty_fut_total'] * budget_scale * ratios_pi.get(m, 0.0)
                    else:
                        df_mat_g[f'Sim_{m}'] = 0.0

            agg_dict = {f'Sim_{m}': 'sum' for m in MESES}
            if 'P.U. s/.' in df_mat_g.columns:
                df_mat_g['PRECIO_UNITARIO'] = pd.to_numeric(df_mat_g['P.U. s/.'], errors='coerce').fillna(0)
            else:
                df_mat_g['PRECIO_UNITARIO'] = 0.0
            
            group_cols = ['DESCRIPCION', 'PRECIO_UNITARIO', 'MULT']
            if col_seccion_g:
                group_cols.append(col_seccion_g)
                
            res_mat_g = df_mat_g.groupby(group_cols).agg(agg_dict).reset_index()
            for _, r in res_mat_g.iterrows():
                mat_val = r['DESCRIPCION']
                matricula, descripcion, unidad = extract_mat_desc(mat_val, df)
                mat_item = {
                    'PI': pi,
                    'SECCION': r[col_seccion_g] if col_seccion_g else "N/A",
                    'MATRICULA': matricula,
                    'DESCRIPCION': descripcion,
                    'UNIDADES': unidad,
                    'PRECIO UNITARIO': r['PRECIO_UNITARIO']
                }
                raw_qtys = [r[f'Sim_{m}'] for m in MESES]
                multiple_val = float(r['MULT'])
                rounded_qtys = apply_custom_rounding(raw_qtys, multiple=multiple_val, round_up=False)
                
                for i, m in enumerate(MESES):
                    mat_item[m] = rounded_qtys[i]
                all_materials_export.append(mat_item)
        
        if es_modificado:
            # El aporte por defecto de este PI al macro era orig_pi[i] * macro_k
            # Se lo restamos al global y le sumamos su nueva serie manual
            for i in range(cutoff_idx + 1, 12):
                aporte_macro_default = orig_pi[i] * macro_k if futuro_orig_sum > 0 else 0.0
                global_sim_only[i] = global_sim_only[i] - aporte_macro_default + (serie_pi[i] if serie_pi[i] else 0.0)
            
            ratios_batch_update[pi] = ratios_pi
        else:
            # Si no fue modificado, el gráfico global YA tiene su aporte macro correcto.
            # Solo aseguramos que los ratios para Google Sheets reflejen este escalamiento macro.
            ratios_macro = {}
            pres_mat = row['Presupuesto Actual']
            for i, m in enumerate(MESES):
                if i <= cutoff_idx:
                    ratios_macro[m] = (emitido_pi.get(m, 0.0) / pres_mat) if pres_mat > 0 else 0.0
                else:
                    ratios_macro[m] = ((orig_pi[i] * macro_k) / pres_mat) if pres_mat > 0 else 0.0
            ratios_batch_update[pi] = ratios_macro

    # Gráfico Global
    fig_global = go.Figure()
    # Las barras reales se muestran hasta el mes de corte
    real_y = global_real[:cutoff_idx+1]
    fig_global.add_trace(go.Bar(
        name='✅ Real Emitido', 
        x=MESES[:cutoff_idx+1], 
        y=real_y, 
        marker_color='#2C539E',
        text=[f"S/. {v:,.0f}" if v > 0 else "" for v in real_y],
        textposition='auto'
    ))
    # Las barras simuladas empiezan DESPUÉS del corte
    sim_y = global_sim_only[cutoff_idx+1:]
    fig_global.add_trace(go.Bar(
        name='🔮 Simulado (Ajustado)', 
        x=MESES[cutoff_idx+1:], 
        y=sim_y, 
        marker_color='#FFBE00',
        text=[f"S/. {v:,.0f}" if v > 0 else "" for v in sim_y],
        textposition='auto'
    ))
    
    # La línea original debe mostrarse todo el año para comparar
    fig_global.add_trace(go.Scatter(
        name='📋 Plan Original (Suma)', 
        x=MESES, 
        y=global_orig, 
        mode='lines+markers+text', 
        line=dict(color='#E94F37', dash='dot'),
        text=[f"S/. {v:,.0f}" if v > 0 else "" for v in global_orig],
        textposition='top center'
    ))
    
    if cutoff_idx >= 0:
        fig_global.add_vline(x=cutoff_idx, line_dash="dash", line_color="gray", annotation_text=f"Corte: {mes_corte}", annotation_position="top left")
    fig_global.update_layout(title="Impacto Presupuestario Global (100% Empresa)", barmode='stack', height=400, yaxis_title="S/.")
    st.plotly_chart(fig_global, use_container_width=True)

    # 5. Detalle por Proyecto
    st.markdown("---")
    st.subheader("🔍 Detalle Individual")
    
    opciones_pi = (edited_df['_pi_code'] + " - " + edited_df['Nombre del proyecto']).tolist()
    if opciones_pi:
        pi_sel = st.selectbox("Seleccionar Proyecto para ver impacto granular:", opciones_pi)
        sel_code = pi_sel.split(" - ")[0]
        sel_row = edited_df[edited_df['_pi_code'] == sel_code].iloc[0]
        
        df_pi_sel = df_f[df_f['_pi_code'] == sel_code]
        emitido_sel = get_emitido_series(df_emitido_all, sel_code, MESES)
        perfil_s = sel_row.get('Perfil Curva', 'Original')
        mes_fin_s = sel_row.get('Mes Fin', 'Dic')
        
        serie_s, orig_s, real_c, saldo_s, ratios_s, is_synthetic_s = build_pi_series(
            df_pi_sel, emitido_sel, sel_row['Simulado Materiales'], cutoff_idx, MESES, perfil_s, mes_fin_s
        )
        
        orig_up_to_cutoff = sum(orig_s[i] for i in range(cutoff_idx + 1))
        diff_cutoff = orig_up_to_cutoff - real_c
        
        st.markdown(f"#### 💰 Análisis de Emisión hasta {mes_corte}")
        st.caption(f"La diferencia se distribuirá automáticamente en los {12 - (cutoff_idx + 1)} meses restantes.")
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Previsto (Ene-{mes_corte})", f"S/ {orig_up_to_cutoff:,.0f}")
        m2.metric(f"Emitido (Ene-{mes_corte})", f"S/ {real_c:,.0f}")
        m3.metric("Diferencia (Saldo a favor/contra)", f"S/ {diff_cutoff:,.0f}", delta=f"S/ {diff_cutoff:,.0f}", delta_color="normal")
        st.markdown("---")
        
        if saldo_s < 0:
            st.error(f"⚠️ **¡Sobregiro detectado!** El proyecto ya ha emitido **S/ {abs(saldo_s):,.0f}** más que el presupuesto simulado. Las simulaciones futuras se mantendrán en S/ 0 y no restarán del gráfico global.")
            
        col_d1, col_d2 = st.columns([2, 1])
        with col_d1:
            fig_sel = go.Figure()
            real_s_y = [serie_s[i] if i <= cutoff_idx else 0 for i in range(12)]
            fig_sel.add_trace(go.Bar(
                name='✅ Real Emitido', 
                x=MESES, 
                y=real_s_y, 
                marker_color='#2C539E',
                text=[f"S/. {v:,.0f}" if v > 0 else "" for v in real_s_y],
                textposition='auto'
            ))
            sim_s_y = [0 if i <= cutoff_idx else serie_s[i] for i in range(12)]
            fig_sel.add_trace(go.Bar(
                name='🔮 Simulado', 
                x=MESES, 
                y=sim_s_y, 
                marker_color='#FFBE00',
                text=[f"S/. {v:,.0f}" if v > 0 else "" for v in sim_s_y],
                textposition='auto'
            ))
            fig_sel.add_trace(go.Scatter(
                name='Original', 
                x=MESES, 
                y=orig_s, 
                mode='lines+markers+text', 
                line=dict(color='#E94F37', dash='dot'),
                text=[f"S/. {v:,.0f}" if v > 0 else "" for v in orig_s],
                textposition='top center'
            ))
            if cutoff_idx >= 0:
                fig_sel.add_vline(x=cutoff_idx, line_dash="dash", line_color="gray")
            fig_sel.update_layout(title=f"Evolución PI: {sel_code}", height=350, barmode='stack')
            st.plotly_chart(fig_sel, use_container_width=True)
        
        with col_d2:
            st.metric("Factor Aplicado", f"{sel_row['Factor Materiales']:.2%}")
            st.metric(f"Emitido hasta {mes_corte}", f"S/ {real_c:,.0f}")
            delta_saldo = f"{saldo_s/sel_row['Simulado Materiales']*100:+.1f}%" if sel_row['Simulado Materiales'] > 0 else None
            st.metric("Saldo Proyectado Restante", f"S/ {saldo_s:,.0f}", delta=delta_saldo, delta_color="inverse" if saldo_s < 0 else "normal")

        # Tabla de Materiales - ENFOQUE A FUTURO
        with st.expander(f"Ver impacto en cantidades de materiales (A FUTURO — {mes_corte} en adelante)"):
            df_mat = df_pi_sel.copy()
            
            # Verificar si el proyecto no tiene previsión original (Valor_Anual == 0 o vacío)
            valor_anual_base = df_mat[[f'Valor_{m}' for m in MESES if f'Valor_{m}' in df_mat.columns]].sum().sum() if not df_mat.empty else 0.0
            
            if valor_anual_base == 0:
                # --- PROYECTO SIN PREVISIÓN (Usa Kit Personalizado) ---
                kits_state = st.session_state.get('custom_kits', pd.DataFrame())
                pi_kit = kits_state[kits_state['PI_Code'] == sel_code].copy()
                
                if pi_kit.empty:
                    st.warning(f"⚠️ El PI {sel_code} no tiene previsión original. Por favor, asigna un Kit Personalizado en la sección superior para ver el desglose de materiales.")
                    res_mat = pd.DataFrame(columns=["Plan Futuro Orig.", "Plan Futuro Sim.", "Diferencia Futura"])
                else:
                    st.info("💡 Usando Kit Personalizado para calcular materiales.")
                    
                    # Asegurar tipos numéricos para evitar errores de cálculo
                    pi_kit['Cantidad'] = pd.to_numeric(pi_kit['Cantidad'], errors='coerce').fillna(0).astype(float)
                    pi_kit['Precio_Unitario'] = pd.to_numeric(pi_kit['Precio_Unitario'], errors='coerce').fillna(0).astype(float)
                    
                    saldo_a_distribuir = saldo_s if saldo_s > 0 else 0.0
                    
                    if saldo_a_distribuir == 0:
                        st.warning("⚠️ El 'Nuevo Total PI' de este proyecto es 0 o está vacío en la tabla principal. Por eso las cantidades simuladas son 0. Escribe un presupuesto en la tabla para ver las cantidades calculadas.")
                    
                    # Calcular participación con fallback para precio 0
                    pi_kit['Costo_Total'] = pi_kit['Cantidad'] * pi_kit['Precio_Unitario']
                    costo_total_kit = pi_kit['Costo_Total'].sum()
                    
                    if costo_total_kit > 0:
                        pi_kit['Participacion'] = pi_kit['Costo_Total'] / costo_total_kit
                    else:
                        # Si todo es precio 0, usamos participación por cantidad para visualización
                        total_qty_k = pi_kit['Cantidad'].sum()
                        pi_kit['Participacion'] = (pi_kit['Cantidad'] / total_qty_k) if total_qty_k > 0 else (1.0 / len(pi_kit))

                    res_mat = pd.DataFrame()
                    res_mat['Descripción'] = pi_kit['Material'].values
                    res_mat['Plan Futuro Orig.'] = 0.0
                    res_mat = res_mat.reset_index(drop=True)
                    pi_kit = pi_kit.reset_index(drop=True)

                    # --- CALCULAR DESGLOSE MENSUAL CON REDONDEO ---
                    total_pres_s = sel_row['Simulado Materiales']
                    sim_futura_list = []
                    
                    for idx_k in range(len(pi_kit)):
                        pu_k = pi_kit.at[idx_k, 'Precio_Unitario']
                        part_k = pi_kit.at[idx_k, 'Participacion']
                        cant_k = pi_kit.at[idx_k, 'Cantidad']
                        
                        raw_qtys = []
                        for i in range(12):
                            if pu_k > 0:
                                raw_qtys.append((serie_s[i] * part_k) / pu_k)
                            else:
                                ratio_t = (serie_s[i] / total_pres_s) if total_pres_s > 0 else 0.0
                                raw_qtys.append(cant_k * ratio_t)
                        
                        # Aplicar redondeo con arrastre (Regla: 0.5 al más cercano)
                        m_val = 1
                        rounded_qtys = apply_custom_rounding(raw_qtys, multiple=m_val, round_up=False)
                        
                        # Guardar en el dataframe
                        for i, m in enumerate(MESES):
                            res_mat.at[idx_k, m] = rounded_qtys[i]
                        
                        # Suma futura para el resumen
                        sim_futura_list.append(sum(rounded_qtys[i] for i in range(12) if i > cutoff_idx))

                    res_mat['Plan Futuro Sim.'] = sim_futura_list
                    res_mat['Diferencia Futura'] = res_mat['Plan Futuro Sim.'] - res_mat['Plan Futuro Orig.']
            else:
                # --- PROYECTO NORMAL (Usa base 2025) ---
                col_seccion_s = next((c for c in df_mat.columns if 'SECCION' in c.upper() or 'SECCIÓN' in c.upper()), None)
                col_multiplo = next((c for c in df_mat.columns if 'MULTIPLO' in c.upper() or 'REDONDEO' in c.upper()), None)
                if col_multiplo:
                    df_mat['MULT'] = pd.to_numeric(df_mat[col_multiplo], errors='coerce').fillna(1).apply(lambda x: max(1, x))
                else:
                    df_mat['MULT'] = 1.0

                for i, m in enumerate(MESES):
                    col_cant = f'Cant_{m}'
                    if col_cant in df_mat.columns:
                        if i > cutoff_idx:
                            df_mat[f'Orig_{m}'] = df_mat[col_cant]
                            if is_synthetic_s:
                                # Placeholder: se recalcula abajo por el método de qty_total
                                df_mat[f'Sim_{m}'] = df_mat[col_cant]
                            else:
                                df_mat[f'Sim_{m}'] = df_mat[col_cant] * ratios_s[m]
                        else:
                            df_mat[f'Orig_{m}'] = 0.0
                            df_mat[f'Sim_{m}'] = 0.0
                    else:
                        df_mat[f'Orig_{m}'] = 0.0
                        df_mat[f'Sim_{m}'] = 0.0

                # Para perfil sintético: preservar total de cantidades y redistribuir por pesos de la curva
                if is_synthetic_s:
                    future_cant_cols_s = [f'Cant_{m}' for i, m in enumerate(MESES) if i > cutoff_idx and f'Cant_{m}' in df_mat.columns]
                    df_mat['_qty_fut_total'] = df_mat[future_cant_cols_s].sum(axis=1) if future_cant_cols_s else 0.0
                    valor_cols_fut_s = [f'Valor_{m}' for i, m in enumerate(MESES) if i > cutoff_idx and f'Valor_{m}' in df_mat.columns]
                    total_money_orig_fut_s = df_mat[valor_cols_fut_s].sum().sum() if valor_cols_fut_s else 0.0
                    budget_scale_s = (saldo_s / total_money_orig_fut_s) if total_money_orig_fut_s > 0 else 1.0
                    for i, m in enumerate(MESES):
                        if i > cutoff_idx:
                            df_mat[f'Sim_{m}'] = df_mat['_qty_fut_total'] * budget_scale_s * ratios_s.get(m, 0.0)
                        else:
                            df_mat[f'Sim_{m}'] = 0.0

                agg_dict_m = {f'Orig_{m}': 'sum' for m in MESES}
                agg_dict_m.update({f'Sim_{m}': 'sum' for m in MESES})
                
                group_cols_s = ['DESCRIPCION', 'MULT']
                if col_seccion_s:
                    group_cols_s.append(col_seccion_s)
                    
                res_mat = df_mat.groupby(group_cols_s).agg(agg_dict_m).reset_index()
                res_mat['Plan Futuro Orig.'] = res_mat[[f'Orig_{m}' for m in MESES]].sum(axis=1)
                
                sim_futura_list = []
                for idx_row, row_mat in res_mat.iterrows():
                    raw_qtys = [row_mat[f'Sim_{m}'] for m in MESES]
                    m_val = float(row_mat['MULT'])
                    rounded_qtys = apply_custom_rounding(raw_qtys, multiple=m_val, round_up=False)
                    sim_futura_list.append(sum(rounded_qtys[i] for i in range(12) if i > cutoff_idx))
                    for idx_m, m in enumerate(MESES):
                        res_mat.at[idx_row, m] = rounded_qtys[idx_m]

                res_mat['Plan Futuro Sim.'] = sim_futura_list
                res_mat['Diferencia Futura'] = res_mat['Plan Futuro Sim.'] - res_mat['Plan Futuro Orig.']
                res_mat = res_mat.rename(columns={'DESCRIPCION': 'Descripción'})
                
                final_cols = ['Descripción']
                if col_seccion_s:
                    final_cols.append(col_seccion_s)
                final_cols += ['Plan Futuro Orig.', 'Plan Futuro Sim.', 'Diferencia Futura'] + MESES
                
                res_mat = res_mat[final_cols]
            
            # Filtrar materiales vacíos, pero conservar los de precio 0 (placeholders)
            if not res_mat.empty:
                res_mat = res_mat[
                    (res_mat['Plan Futuro Orig.'] > 0) | 
                    (res_mat['Plan Futuro Sim.'] > 0) |
                    (res_mat['Descripción'].astype(str).str.strip() != '')
                ].copy()

                # El res_mat ya contiene los meses redondeados por material con su múltiplo
                res_mat_final = res_mat.copy()
                
                # Asegurar que las columnas de resumen sean enteros para la visualización
                for col in ['Plan Futuro Orig.', 'Plan Futuro Sim.', 'Diferencia Futura']:
                    if col in res_mat_final.columns:
                        res_mat_final[col] = pd.to_numeric(res_mat_final[col], errors='coerce').fillna(0).round(0).astype(int)

                col_t1, col_t2 = st.columns([3, 1])
                with col_t1:
                    st.dataframe(
                        res_mat_final, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "Plan Futuro Orig.": st.column_config.NumberColumn(format="%,.0f", help="Cantidad original planeada desde el mes siguiente al corte"),
                            "Plan Futuro Sim.": st.column_config.NumberColumn(format="%,.0f", help="Nueva cantidad proyectada con el ajuste de budget"),
                            "Diferencia Futura": st.column_config.NumberColumn(format="%+,.0f"),
                        }
                    )
                with col_t2:
                    st.download_button(
                        label="📥 Descargar Detalle (Excel)",
                        data=to_excel(res_mat_final),
                        file_name=f"Detalle_Materiales_{sel_code}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"dl_pi_{sel_code}"
                    )

    # 6. Guardar Cambios (BATCH UPDATE)
    st.markdown("---")
    st.subheader("💾 Guardar Simulación")
    
    # --- BOTÓN DE DESCARGA GLOBAL ---
    if global_export_list:
        df_export_g = pd.DataFrame(global_export_list)
        
        # Procesar df_materials_export
        df_materials_export = pd.DataFrame(all_materials_export)
        if not df_materials_export.empty:
            df_materials_export['CANTIDAD TOTAL'] = df_materials_export[MESES].sum(axis=1)
            # Filtrar materiales sin cantidad, pero conservar los de precio 0 (placeholders)
            df_materials_export = df_materials_export[
                (df_materials_export['CANTIDAD TOTAL'] > 0) | 
                (df_materials_export['PRECIO UNITARIO'] == 0)
            ].copy()
            
        if not df_materials_export.empty:
            df_materials_export['PRECIO TOTAL'] = df_materials_export['CANTIDAD TOTAL'] * df_materials_export['PRECIO UNITARIO']
            
            # Reordenar columnas
            column_order = ['PI', 'SECCION', 'MATRICULA', 'DESCRIPCION', 'UNIDADES', 'PRECIO UNITARIO'] + MESES + ['CANTIDAD TOTAL', 'PRECIO TOTAL']
            df_materials_export = df_materials_export[column_order]
            
            # Redondeo de cantidades (Ene-Dic y Cantidad Total)
            cols_to_round = MESES + ['CANTIDAD TOTAL']
            df_materials_export = apply_custom_rounding(df_materials_export, cols_to_round)
            
            # Redondear PRECIO TOTAL para consistencia visual (arrastre no aplica aquí)
            df_materials_export['PRECIO TOTAL'] = df_materials_export['PRECIO TOTAL'].apply(lambda x: int(x) + 1 if (x - int(x)) > 0.5 else int(x))
            
            excel_data = to_excel({"Resumen PIs": df_export_g, "Materiales": df_materials_export})
        else:
            excel_data = to_excel({"Resumen PIs": df_export_g})

        st.download_button(
            label="📥 Descargar Resumen General de Simulación (Excel)",
            data=excel_data,
            file_name="Simulacion_Global_Budget.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_global_sim"
        )
        st.write("")

    st.warning("⚠️ **Atención**: Al actualizar la base de datos, se aplicarán las distribuciones calculadas a todos los proyectos visibles en la tabla, reescribiendo la hoja 'PREVISIONES 2026'.")
    
    if st.button("Actualizar Base de Datos (Todos los PIs)", type="primary", use_container_width=True):
        st.session_state['confirm_batch_update'] = True
        
    if st.session_state.get('confirm_batch_update', False):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("✅ Confirmar y Escribir en Drive", use_container_width=True):
                with st.spinner("Ejecutando actualización masiva en Google Sheets..."):
                    # Preparar data de kits para inserción de nuevas filas
                    kits_info = {}
                    
                    # 1. Obtener los kits desde custom_kits (lo que el usuario ve en la tabla superior)
                    df_custom = st.session_state.get('custom_kits', pd.DataFrame())
                    if not df_custom.empty:
                        # Necesitamos los nombres de los proyectos. Podemos sacarlos de pi_data o edited_df
                        # Para simplificar, usaremos un mapa PI -> Nombre
                        pi_names = dict(zip(edited_df['_pi_code'], edited_df['Nombre del proyecto']))
                        
                        for pi_code, group in df_custom.groupby('PI_Code'):
                            pi_clean = _normalize_code(pi_code)
                            
                            # Buscar la serie simulada en edited_df o res_sim_global (si existe)
                            # res_sim_global se usaba en versiones anteriores, aquí usaremos la lógica local
                            # ya que estamos dentro del mismo contexto.
                            
                            # Buscar en global_export_list que ya fue construido antes de este botón
                            serie_match = next((item for item in global_export_list if _normalize_code(item['PI']) == pi_clean), None)
                            
                            if serie_match:
                                series_values = [serie_match[m] for m in MESES]
                                
                                materiales_list = []
                                for _, m_row in group.iterrows():
                                    materiales_list.append({
                                        'Material': m_row['Material'],
                                        'Cantidad': m_row['Cantidad'],
                                        'Precio_Unitario': m_row['Precio_Unitario']
                                    })
                                    
                                kits_info[pi_clean] = {
                                    'materiales': materiales_list,
                                    'name': pi_names.get(pi_clean, f"Proyecto {pi_clean}"),
                                    'series': series_values
                                }

                    success, msg = update_previsiones_sheet_batch(
                        ratios_batch_update, 
                        kits_to_add=kits_info, 
                        df_main=df
                    )
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
                st.session_state['confirm_batch_update'] = False
        with col_c2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state['confirm_batch_update'] = False
                st.rerun()
