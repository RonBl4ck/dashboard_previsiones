
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.google_sheets_helper import get_presupuesto_historico, update_presupuesto_historico_batch

def show(df):
    st.title("Histórico de Presupuestos")

    MESES_H = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    # 1. Cargar datos históricos
    if 'history_df' not in st.session_state:
        with st.spinner("Cargando historial desde Google Sheets..."):
            st.session_state['history_df'] = get_presupuesto_historico()

    history_df = st.session_state['history_df']

    # 2. Calcular valores actuales desde el DataFrame principal
    # Agrupamos por PI para obtener el valor total actual
    def _normalize_code(val):
        return str(val).strip().upper().replace('.0', '')

    current_budgets = []
    if not df.empty and 'Codigo del Proyecto' in df.columns:
        # El presupuesto total del proyecto suele estar en 'Valor материалов (MS/.)' 
        # o sumando todas las previsiones. Según app.py, Valor_Anual es la suma de los meses.
        # El usuario pidió el "presupuesto que nos dieron", que suele ser el valor total del PI.
        
        # Agrupar por código de proyecto
        df_clean = df.copy()
        df_clean['_pi_code'] = df_clean['Codigo del Proyecto'].apply(_normalize_code)
        
        # Usamos Valor_Anual como el "Presupuesto de esta actualización"
        pi_totals = df_clean.groupby('_pi_code').agg({
            'Valor_Anual': 'sum',
            'Nombre del proyecto': 'first'
        }).reset_index()
        
        current_budgets = pi_totals.to_dict('records')

    # 4. Editor de Tabla
    st.subheader("📊 Tabla de Historial")
    
    # Limpiar el nombre del proyecto para visualización (quitar el [PI] si existe)
    if not history_df.empty and 'Proyecto' in history_df.columns:
        history_df['Proyecto'] = history_df['Proyecto'].str.replace(r'^\[.*?\]\s*', '', regex=True)
    
    # Configuración de columnas para el editor
    column_config = {
        "PI_Code": st.column_config.TextColumn("PI", disabled=True),
        "Proyecto": st.column_config.TextColumn("Nombre del Proyecto", width="large"),
    }
    for m in MESES_H:
        column_config[m] = st.column_config.NumberColumn(m, format="S/ %,.0f", min_value=0.0)

    edited_history = st.data_editor(
        history_df,
        column_config=column_config,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key="history_editor"
    )

    col_save, col_clear = st.columns([1, 4])
    with col_save:
        if st.button("💾 Guardar Cambios Manuales", use_container_width=True):
            if update_presupuesto_historico_batch(edited_history):
                st.session_state['history_df'] = edited_history
                st.success("Cambios guardados correctamente.")
                st.rerun()

    # 5. Análisis de Variación
    st.markdown("---")
    st.subheader("📊 Análisis de Variación entre Actualizaciones")
    
    # Usar las columnas reales que hay en la base
    dynamic_cols = [c for c in history_df.columns if c not in ["PI_Code", "Proyecto"]]
    
    if len(dynamic_cols) >= 2:
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            mes_base = st.selectbox("Mes Base (Anterior):", dynamic_cols, index=max(0, len(dynamic_cols)-2))
        with col_v2:
            mes_comp = st.selectbox("Mes de Comparación (Nuevo):", dynamic_cols, index=len(dynamic_cols)-1)

        if not edited_history.empty:
            # Calcular variaciones
            var_df = edited_history.copy()
            var_df['Val_Base'] = var_df[mes_base].fillna(0)
            var_df['Val_Comp'] = var_df[mes_comp].fillna(0)
            var_df['Delta'] = var_df['Val_Comp'] - var_df['Val_Base']
            var_df['Delta_%'] = (var_df['Delta'] / var_df['Val_Base'] * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
            
            # Métricas Globales
            total_base = var_df['Val_Base'].sum()
            total_comp = var_df['Val_Comp'].sum()
            total_delta = total_comp - total_base
            total_delta_pct = (total_delta / total_base * 100) if total_base > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric(f"Total {mes_base}", f"S/ {total_base:,.0f}")
            m2.metric(f"Total {mes_comp}", f"S/ {total_comp:,.0f}")
            m3.metric("Variación Total", f"S/ {total_delta:,.0f}", delta=f"{total_delta_pct:.1f}%")
            
            # Mostrar solo filas con cambios significativos o filtrar
            show_all = st.checkbox("Mostrar todos los PIs (incluyendo los sin cambio)", value=False)
            
            if not show_all:
                disp_var = var_df[var_df['Delta'].abs() > 1].copy()
            else:
                disp_var = var_df.copy()
                
            if not disp_var.empty:
                st.dataframe(
                    disp_var[['PI_Code', 'Proyecto', 'Val_Base', 'Val_Comp', 'Delta', 'Delta_%']],
                    column_config={
                        "PI_Code": "PI",
                        "Val_Base": f"Presup. {mes_base}",
                        "Val_Comp": f"Presup. {mes_comp}",
                        "Delta": st.column_config.NumberColumn("Variación (S/.)", format="S/ %,.0f"),
                        "Delta_%": st.column_config.NumberColumn("Var. %", format="%.1f%%")
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info(f"No hay variaciones registradas entre {mes_base} y {mes_comp}.")

    # 6. Visualización Gráfica
    if not edited_history.empty:
        st.markdown("---")
        st.subheader("📈 Evolución de Presupuestos por Actualización")
        
        # Selección de PIs para graficar
        selected_pis = st.multiselect(
            "Selecciona PIs para comparar su evolución:",
            options=edited_history['PI_Code'].tolist(),
            default=edited_history['PI_Code'].head(3).tolist()
        )
        
        if selected_pis:
            fig = go.Figure()
            for pi in selected_pis:
                row = edited_history[edited_history['PI_Code'] == pi].iloc[0]
                values = [row[m] for m in dynamic_cols]
                
                # Filtrar solo meses que tengan valor > 0 para que la línea no caiga a cero en meses futuros
                display_months = []
                display_values = []
                for m, v in zip(dynamic_cols, values):
                    if v > 0:
                        display_months.append(m)
                        display_values.append(v)
                
                if display_values:
                    fig.add_trace(go.Scatter(
                        x=display_months,
                        y=display_values,
                        mode='lines+markers+text',
                        name=f"PI {pi}",
                        text=[f"S/ {v/1e3:.0f}k" for v in display_values],
                        textposition="top center"
                    ))
            
            fig.update_layout(
                title="Presupuesto Asignado por Actualización",
                xaxis_title="Actualización",
                yaxis_title="Presupuesto Total (S/.)",
                legend_title="Proyecto",
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Gráfico de Total Global del Presupuesto
            st.subheader("🏢 Presupuesto Total Empresa (Suma de PIs en Historial)")
            total_por_mes = []
            for m in dynamic_cols:
                total_por_mes.append(edited_history[m].sum())
            
            # Filtrar meses con total > 0
            final_months = []
            final_totals = []
            for m, t in zip(dynamic_cols, total_por_mes):
                if t > 0:
                    final_months.append(m)
                    final_totals.append(t)
            
            if final_totals:
                fig_total = go.Figure()
                fig_total.add_trace(go.Bar(
                    x=final_months,
                    y=final_totals,
                    text=[f"S/ {t:,.0f}" for t in final_totals],
                    textposition='auto',
                    marker_color='#1B3F66'
                ))
                fig_total.update_layout(
                    title="Evolución del Presupuesto Total de la Empresa",
                    xaxis_title="Actualización",
                    yaxis_title="S/.",
                    height=400
                )
                st.plotly_chart(fig_total, use_container_width=True)
    else:
        st.info("Añade al menos dos actualizaciones para ver el análisis de variación y gráficos.")
    
