"""
Página de Resumen Ejecutivo
Muestra KPIs principales y gráficos de distribución
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import sys
from datetime import datetime
sys.path.append('..')
from components.charts import create_line_chart
from components.kpis import show_executive_summary_kpis


JUSTIFICACIONES_SHEET = "Justificaciones Alertas"
SHEETBOOK_NAME = "PREVISIONES 2026"


@st.cache_data(ttl=600)
def load_alert_justifications():
    """Carga las justificaciones guardadas desde Google Sheets.
    Retorna un dict {material_key: justificacion_str} con la más reciente por material."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open(SHEETBOOK_NAME)
        try:
            ws = sh.worksheet(JUSTIFICACIONES_SHEET)
            records = ws.get_all_records()
            if not records:
                return {}
            df_just = pd.DataFrame(records)
            # Quedarse con la entrada más reciente por material
            if 'Material' in df_just.columns and 'Justificación' in df_just.columns:
                df_just = df_just.sort_values('Fecha', ascending=False)
                df_just = df_just.drop_duplicates(subset='Material', keep='first')
                return dict(zip(df_just['Material'].str.strip().str.upper(), df_just['Justificación']))
            return {}
        except gspread.exceptions.WorksheetNotFound:
            return {}
    except Exception:
        return {}


def save_alerts_justifications(df_to_save):
    """Guarda o actualiza las justificaciones en Google Sheets (upsert por material).
    df_to_save: DataFrame con columnas [Material, Máx. Histórico, Previsión 2026, Diferencia, Estado, Justificación].
    Retorna (bool, str).
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open(SHEETBOOK_NAME)

        # Obtener o crear la hoja de justificaciones
        try:
            ws = sh.worksheet(JUSTIFICACIONES_SHEET)
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=JUSTIFICACIONES_SHEET, rows=1000, cols=8)
            ws.append_row(['Fecha', 'Material', 'Máx. Histórico', 'Previsión 2026', 'Diferencia', 'Estado', 'Justificación'])

        # Leer datos actuales para hacer upsert
        existing = ws.get_all_records()
        existing_df = pd.DataFrame(existing) if existing else pd.DataFrame(
            columns=['Fecha', 'Material', 'Máx. Histórico', 'Previsión 2026', 'Diferencia', 'Estado', 'Justificación']
        )

        fecha_hoy = datetime.now().strftime('%Y-%m-%d %H:%M')
        nuevas_filas = []
        materiales_actualizados = []

        for _, row in df_to_save.iterrows():
            material_key = str(row['Material']).strip().upper()
            justificacion = str(row.get('Justificación', '')).strip()
            if not justificacion:
                continue

            nueva_fila = [
                fecha_hoy,
                str(row['Material']).strip(),
                float(row.get('Máx. Histórico', 0)),
                float(row.get('Previsión 2026', 0)),
                float(row.get('Diferencia', 0)),
                str(row.get('Estado', '')),
                justificacion
            ]

            # Upsert: si ya existe ese material, reemplazamos su fila
            if not existing_df.empty and 'Material' in existing_df.columns:
                match_mask = existing_df['Material'].str.strip().str.upper() == material_key
                if match_mask.any():
                    row_number = existing_df[match_mask].index[0] + 2  # +2: header fila 1, 0-indexed
                    ws.update(f'A{row_number}:G{row_number}', [nueva_fila])
                    materiales_actualizados.append(row['Material'])
                    continue

            nuevas_filas.append(nueva_fila)
            materiales_actualizados.append(row['Material'])

        if nuevas_filas:
            ws.append_rows(nuevas_filas, value_input_option='USER_ENTERED')

        if not materiales_actualizados:
            return False, "No había justificaciones con texto para guardar."

        return True, f"✅ Guardadas {len(materiales_actualizados)} justificación(es): {', '.join(materiales_actualizados[:3])}{'...' if len(materiales_actualizados) > 3 else ''}"

    except Exception as e:
        return False, f"Error al guardar en Google Sheets: {e}"

BAR_HEIGHT = 340


def _prepare_ranked_data(df, label_col, value_col, selected_label=None, top_n=7, show_others=True):
    """Devuelve Top N (+ Otros si show_others), garantizando que el seleccionado aparezca en el gráfico."""
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

    if show_others and not restantes.empty:
        top = pd.concat([
            top,
            pd.DataFrame({
                label_col: [f'Otros ({len(restantes)})'],
                value_col: [restantes[value_col].sum()]
            })
        ], ignore_index=True)

    return top.sort_values(value_col, ascending=True)


def _create_ranked_bar(df, label_col, value_col, title, selected_label=None, top_n=7, show_others=True, is_currency=True, height=BAR_HEIGHT):
    plot_df = _prepare_ranked_data(df, label_col, value_col, selected_label, top_n, show_others)
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

    if is_currency:
        text = [f"S/ {v:,.0f}" for v in plot_df[value_col]]
        hovertemplate = '<b>%{y}</b><br>Valor: S/ %{x:,.0f}<extra></extra>'
    else:
        text = [f"{v:,.0f}" for v in plot_df[value_col]]
        hovertemplate = '<b>%{y}</b><br>Cantidad: %{x:,.0f}<extra></extra>'

    fig = go.Figure(go.Bar(
        x=plot_df[value_col],
        y=plot_df[label_col].str[:65],  # Truncar etiquetas largas para mejor visualización
        orientation='h',
        marker_color=colors,
        text=text,
        textposition='outside',
        hovertemplate=hovertemplate
    ))
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=14, color='#2C539E')),
        height=height,
        margin=dict(t=45, b=20, l=20, r=20),
        xaxis_title='Valor' if is_currency else 'Cantidad',
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
            st.subheader("🏛️ Distribución por Zona")
            fig_seccion = _create_custom_donut(
                df_filtered.groupby('Seccion', dropna=False)['Valor_Anual'].sum().reset_index(),
                label_col='Seccion',
                value_col='Valor_Anual',
                title='Distribución por Zona',
                is_currency=True
            )
            st.plotly_chart(fig_seccion, use_container_width=True)
        
        with col2:
            st.subheader("⚡ Distribución por Sección")
            fig_area = _create_custom_donut(
                df_filtered.groupby('AREA', dropna=False)['Valor_Anual'].sum().reset_index(),
                label_col='AREA',
                value_col='Valor_Anual',
                title='Distribución por Sección Técnica',
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
        
        # Agrupamos todos los materiales ignorando la unidad
        materiales = df_mat.groupby('DESCRIPCION').agg({
            'Total/Cantidad': 'sum',
            'Valor materiales (MS/.)': 'sum',
            'P.U. s/.': 'first',
            'Nombre del proyecto': 'nunique'
        }).reset_index()
        
        materiales.columns = ['Material', 'Cantidad', 'Valor', 'P.U.', 'Proyectos']
        materiales = materiales.sort_values('Valor', ascending=False)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Materiales", f"{len(materiales)}")
        with col2:
            st.metric("Valor Total", f"S/ {materiales['Valor'].sum():,.0f}")
        
        st.markdown("---")
        
        if not materiales.empty:
            material_focus = st.selectbox(
                "Seleccionar material para destacar",
                ['Ninguno'] + sorted(materiales['Material'].astype(str).tolist()),
                key='focus_material_analisis'
            )
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                fig_val = _create_ranked_bar(
                    materiales,
                    'Material',
                    'Valor',
                    'Top 10 Materiales por Valor (S/.)',
                    selected_label=None if material_focus == 'Ninguno' else material_focus,
                    top_n=10,
                    show_others=False,
                    is_currency=True,
                    height=450
                )
                st.plotly_chart(fig_val, use_container_width=True)
            with col_chart2:
                fig_cant = _create_ranked_bar(
                    materiales,
                    'Material',
                    'Cantidad',
                    'Top 10 Materiales por Cantidad',
                    selected_label=None if material_focus == 'Ninguno' else material_focus,
                    top_n=10,
                    show_others=False,
                    is_currency=False,
                    height=450
                )
                st.plotly_chart(fig_cant, use_container_width=True)
            
            with st.expander("📋 Ver Detalle de Materiales"):
                valor_min = st.number_input("Valor mínimo (MS/.):", 0, int(materiales['Valor'].max()), 0, step=10000)
                
                mat_tabla = materiales[materiales['Valor'] >= valor_min].copy()
                
                tabla_display = mat_tabla.head(50).copy()
                tabla_display['Material'] = tabla_display['Material'].str[:55]
                
                st.dataframe(
                    tabla_display[['Material', 'Cantidad', 'Valor', 'P.U.', 'Proyectos']],
                    use_container_width=True,
                    hide_index=True,
                    height=300,
                    column_config={
                        'Cantidad': st.column_config.NumberColumn(format="%,.0f"),
                        'Valor': st.column_config.NumberColumn(format="S/ %,.0f"),
                        'P.U.': st.column_config.NumberColumn(format="S/ %,.2f"),
                        'Proyectos': st.column_config.NumberColumn(format="%,d")
                    }
                )
                st.caption(f"Mostrando {len(mat_tabla)} de {len(materiales)} materiales (máx 50 en tabla)")
        else:
            st.info("No hay materiales disponibles.")

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
            selected_label=None if proyecto_focus == 'Ninguno' else proyecto_focus,
            show_others=False,
            top_n=10, # Aumentamos a 10 para compensar
            height=450
        )
        st.plotly_chart(fig_proyecto, use_container_width=True)

        with st.expander("📋 Ver detalle completo de proyectos"):
            st.dataframe(
                resumen_proyecto,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Valor Total Anual': st.column_config.NumberColumn(format="S/ %,.0f"),
                    'N° Materiales': st.column_config.NumberColumn(format="%,d")
                }
            )

    # Pestaña 4: Previsión Mensual
    with tab4:
        from pages import prevision_mensual
        prevision_mensual.show(df, apply_filters)

    # Pestaña 5: Alertas Históricas
    with tab5:
        st.subheader("⚠️ Alertas de Variación Histórica")
        st.markdown("Comparativa entre la Previsión de Cantidad 2026 y el Consumo Máximo Histórico (2023-2025).")
        
        if 'Maximo_Historico' not in df_filtered.columns or df_filtered['Maximo_Historico'].sum() == 0:
            st.info("No hay datos históricos disponibles cargados en el dataset (Consumo 123, 124, 125).")
        else:
            # Agrupar por material para comparar cantidades
            hist_df = df_filtered.groupby('DESCRIPCION').agg({
                'Total/Cantidad': 'sum',
                'Maximo_Historico': 'first',
                'UNIDAD': 'first',
                'Valor_Anual': 'sum',
                'Nombre del proyecto': 'nunique'
            }).reset_index()
            
            # Limpiar casos donde ambos son 0 para no hacer ruido
            hist_df = hist_df[(hist_df['Total/Cantidad'] > 0) | (hist_df['Maximo_Historico'] > 0)].copy()
            
            hist_df['Variacion_Abs'] = hist_df['Total/Cantidad'] - hist_df['Maximo_Historico']
            hist_df['Variacion_Pct'] = np.where(
                hist_df['Maximo_Historico'] > 0,
                (hist_df['Variacion_Abs'] / hist_df['Maximo_Historico']) * 100,
                100.0
            )
            # Marcar nuevo material si historico es 0
            hist_df['Variacion_Pct'] = np.where(hist_df['Maximo_Historico'] == 0, np.inf, hist_df['Variacion_Pct'])
            
            # Clasificar alertas
            hist_df['Alerta'] = 'Normal'
            hist_df.loc[(hist_df['Variacion_Pct'] >= 50) & (hist_df['Total/Cantidad'] > hist_df['Maximo_Historico']), 'Alerta'] = 'Aumento Crítico (>50%)'
            hist_df.loc[(hist_df['Variacion_Pct'] <= -50) & (hist_df['Maximo_Historico'] > hist_df['Total/Cantidad']), 'Alerta'] = 'Reducción Crítica (<-50%)'
            hist_df.loc[hist_df['Maximo_Historico'] == 0, 'Alerta'] = 'Material Nuevo / Sin Histórico'

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
            
            # Controles de Visualización
            col_ctrl_1, col_ctrl_2 = st.columns(2)
            with col_ctrl_1:
                vista_alerta = st.radio("Mostrar gráfico de:", ["🚀 Mayores Aumentos", "📉 Mayores Reducciones"], horizontal=True, key="vista_alertas")
            with col_ctrl_2:
                orden_alerta = st.radio("Ordenar ranking por:", ["Cantidad Absoluta", "Porcentaje (%)"], horizontal=True, key="orden_alertas")
            
            st.markdown("---")
            
            # Filtrar y ordenar datos según selección
            if "Aumentos" in vista_alerta:
                df_grafico = hist_df[hist_df['Variacion_Abs'] > 0].copy()
                color_grafico = '#E94F37'
                titulo_grafico = "Top 15 Aumentos vs Máximo Histórico"
            else:
                df_grafico = hist_df[hist_df['Variacion_Abs'] < 0].copy()
                color_grafico = '#2ECC71'
                titulo_grafico = "Top 15 Reducciones vs Máximo Histórico"
                
            columna_orden = 'Variacion_Abs' if "Cantidad" in orden_alerta else 'Variacion_Pct'
            
            if "Reducciones" in vista_alerta:
                # Ordenar reducciones: más negativo a menos
                df_grafico = df_grafico.sort_values(columna_orden, ascending=True).head(15)
                x_data = df_grafico['Variacion_Abs'].abs()
            else:
                df_grafico = df_grafico.sort_values(columna_orden, ascending=False).head(15)
                x_data = df_grafico['Variacion_Abs']
                
            st.markdown(f"#### {titulo_grafico}")
            
            if not df_grafico.empty:
                fig_alert = go.Figure(go.Bar(
                    x=x_data,
                    y=df_grafico['DESCRIPCION'].str[:45],
                    orientation='h',
                    marker_color=color_grafico,
                    text=df_grafico['Variacion_Pct'].apply(lambda x: f"{x:+.0f}%" if x != np.inf else "Nuevo"),
                    textposition='auto'
                ))
                fig_alert.update_layout(
                    height=450, 
                    margin=dict(l=10, r=10, t=30, b=10), 
                    yaxis={'autorange': 'reversed'}, 
                    xaxis_title='Diferencia'
                )
                st.plotly_chart(fig_alert, use_container_width=True)
            else:
                st.info("No hay registros que coincidan con esta selección.")

            st.markdown("---")
            st.markdown("#### 📋 Base de Datos de Variaciones")
            st.caption("Puedes escribir una justificación en la última columna y guardarla en Google Sheets.")
            
            alerta_filter = st.selectbox("Filtrar por tipo de Alerta:", ['Todas'] + list(hist_df['Alerta'].unique()), key="alerta_filter_var")
            
            display_df = hist_df if alerta_filter == 'Todas' else hist_df[hist_df['Alerta'] == alerta_filter]
            
            display_df = display_df[['DESCRIPCION', 'UNIDAD', 'Maximo_Historico', 'Total/Cantidad', 'Variacion_Abs', 'Variacion_Pct', 'Alerta', 'Valor_Anual']].copy()
            display_df.columns = ['Material', 'Unidad', 'Máx. Histórico', 'Previsión 2026', 'Diferencia', '% Variación', 'Estado', 'Valor 2026 (S/.)']
            
            display_df = display_df.sort_values('Diferencia', key=abs, ascending=False)
            display_df['% Variación'] = display_df['% Variación'].replace(np.inf, np.nan)
            display_df = display_df.reset_index(drop=True)

            # --- Cargar justificaciones guardadas desde Sheets y hacer merge ---
            justificaciones_guardadas = load_alert_justifications()
            display_df['Justificación'] = display_df['Material'].str.strip().str.upper().map(justificaciones_guardadas).fillna('')

            edited_df = st.data_editor(
                display_df,
                use_container_width=True,
                hide_index=True,
                num_rows='fixed',
                column_config={
                    'Material': st.column_config.TextColumn('Material', disabled=True),
                    'Unidad': st.column_config.TextColumn('Unidad', disabled=True),
                    'Máx. Histórico': st.column_config.NumberColumn(format="%,.0f", disabled=True, help="Unidades redondeadas"),
                    'Previsión 2026': st.column_config.NumberColumn(format="%,.0f", disabled=True, help="Unidades redondeadas"),
                    'Diferencia': st.column_config.NumberColumn(format="%+,.0f", disabled=True, help="Diferencia de unidades redondeada"),
                    '% Variación': st.column_config.NumberColumn(format="%.1f%%", disabled=True),
                    'Estado': st.column_config.TextColumn('Estado', disabled=True),
                    'Valor 2026 (S/.)': st.column_config.NumberColumn(format="S/ %,.0f", disabled=True),
                    'Justificación': st.column_config.TextColumn(
                        '📝 Justificación',
                        help='Escribe aquí el motivo de la variación (ej: mayor meta en Proyecto X)',
                        max_chars=300,
                        disabled=False
                    )
                }
            )

            # --- Botón de guardado ---
            if st.button("💾 Guardar Justificaciones", type="primary", key="btn_guardar_justificaciones"):
                filas_con_texto = edited_df[edited_df['Justificación'].str.strip() != '']
                if filas_con_texto.empty:
                    st.warning("Escribe al menos una justificación antes de guardar.")
                else:
                    with st.spinner("Guardando en Google Sheets..."):
                        ok, msg = save_alerts_justifications(filas_con_texto)
                    if ok:
                        st.success(msg)
                        st.cache_data.clear()
                    else:
                        st.error(msg)
