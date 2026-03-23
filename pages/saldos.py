"""
Página de Saldos y Ajustes
Permite cargar saldos y priorizar materiales por saldo disponible
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import sys

sys.path.append('..')


def _build_demo_saldos(df_filtered):
    base = df_filtered.groupby('DESCRIPCION').agg({
        'UNIDAD': 'first',
        'P.U. s/.': 'first'
    }).reset_index()
    np.random.seed(42)
    base['Saldo'] = np.random.uniform(50, 5000, len(base))
    base['Valor_Saldo'] = base['Saldo'] * base['P.U. s/.'].fillna(0)
    return base[['DESCRIPCION', 'UNIDAD', 'Saldo', 'Valor_Saldo']]


def show(df, apply_filters):
    """Función principal de la página de Saldos y Ajustes"""

    st.title("📦 Saldos y Ajustes")
    st.markdown("---")

    df_filtered = apply_filters(df)
    if df_filtered.empty:
        st.warning("No hay datos con los filtros seleccionados")
        return

    st.markdown("""
    <div style="background-color: #E9ECEF; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
        <p style="margin: 0;">Esta sección se enfoca solo en los <strong>saldos disponibles</strong> para identificar
        qué materiales conviene priorizar por volumen de stock.</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("📁 Cargar Archivo de Saldos")
    st.markdown("""
    **Formato esperado del archivo:**
    - Columna de identificación: DESCRIPCION, Matricula, Matrícula o Material
    - Columna de saldo: Saldo, Stock, Cantidad o Cantidad_Disponible
    - Columnas opcionales: UNIDAD, Valor_Saldo
    - Formato: Excel (.xlsx) o CSV
    """)

    uploaded_file = st.file_uploader(
        "Seleccionar archivo de saldos:",
        type=['xlsx', 'csv'],
        help="Sube un archivo Excel o CSV con los saldos disponibles"
    )
    use_demo = st.checkbox("Usar datos de demostración (simular saldos)", value=False)

    df_saldos = None
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_saldos = pd.read_csv(uploaded_file)
            else:
                df_saldos = pd.read_excel(uploaded_file)
            st.success(f"✅ Archivo cargado: {uploaded_file.name}")
            with st.expander("Vista previa del archivo de saldos"):
                st.dataframe(df_saldos.head(10), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error al cargar el archivo: {e}")
            return
    elif use_demo:
        df_saldos = _build_demo_saldos(df_filtered)
        st.success(f"✅ Saldos simulados para {len(df_saldos)} materiales")

    st.markdown("---")
    if df_saldos is None:
        st.info("👉 Carga un archivo de saldos o activa los datos de demostración para ver el análisis.")
        return

    col_material = next((col for col in ['DESCRIPCION', 'Matricula', 'Matrícula', 'Material'] if col in df_saldos.columns), None)
    col_saldo = next((col for col in ['Saldo', 'Stock', 'Cantidad', 'Cantidad_Disponible'] if col in df_saldos.columns), None)
    col_unidad = next((col for col in ['UNIDAD', 'Unidad'] if col in df_saldos.columns), None)
    col_valor = next((col for col in ['Valor_Saldo', 'Valor', 'Monto'] if col in df_saldos.columns), None)

    if col_material is None or col_saldo is None:
        st.error("El archivo debe contener al menos una columna de material y una columna de saldo.")
        return

    saldo_df = df_saldos.copy()
    saldo_df = saldo_df.rename(columns={col_material: 'Material', col_saldo: 'Saldo'})
    if col_unidad:
        saldo_df = saldo_df.rename(columns={col_unidad: 'Unidad'})
    else:
        saldo_df['Unidad'] = ''

    saldo_df['Material'] = saldo_df['Material'].astype(str).str.strip()
    saldo_df['Saldo'] = pd.to_numeric(saldo_df['Saldo'], errors='coerce').fillna(0)
    saldo_df = saldo_df[saldo_df['Saldo'] > 0].copy()

    if col_valor:
        saldo_df = saldo_df.rename(columns={col_valor: 'Valor_Saldo'})
        saldo_df['Valor_Saldo'] = pd.to_numeric(saldo_df['Valor_Saldo'], errors='coerce').fillna(0)
    else:
        saldo_df['Valor_Saldo'] = saldo_df['Saldo']

    saldo_df = saldo_df.groupby(['Material', 'Unidad'], dropna=False).agg({
        'Saldo': 'sum',
        'Valor_Saldo': 'sum'
    }).reset_index()

    total_saldo = saldo_df['Saldo'].sum()
    total_items = len(saldo_df)
    saldo_max = saldo_df['Saldo'].max() if not saldo_df.empty else 0
    material_top = saldo_df.sort_values('Saldo', ascending=False).iloc[0]['Material'] if not saldo_df.empty else 'N/A'

    st.subheader("📊 Resumen General")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Saldo Total", f"{total_saldo:,.0f}")
    with col2:
        st.metric("Materiales con Saldo", f"{total_items}")
    with col3:
        st.metric("Saldo Máximo", f"{saldo_max:,.0f}")
    with col4:
        st.metric("Material Prioritario", material_top[:24] + ("..." if len(material_top) > 24 else ""))

    st.markdown("---")

    material_focus = st.selectbox(
        "Destacar material",
        ['Ninguno'] + saldo_df['Material'].astype(str).tolist(),
        key='focus_saldos_material'
    )

    plot_df = saldo_df[['Material', 'Saldo', 'Valor_Saldo']].sort_values('Saldo', ascending=False)
    top_plot = plot_df.head(10).copy()
    restantes = plot_df.iloc[10:].copy()
    if material_focus != 'Ninguno' and material_focus in restantes['Material'].values:
        selected_row = restantes[restantes['Material'] == material_focus]
        top_plot = pd.concat([top_plot, selected_row], ignore_index=True)

    top_plot = top_plot.sort_values('Saldo', ascending=True)
    colors = [
        '#E94F37' if name == material_focus else '#1B3F66'
        for name in top_plot['Material']
    ]

    st.subheader("📈 Materiales con Mayor Saldo")
    fig_top = go.Figure(go.Bar(
        x=top_plot['Saldo'],
        y=top_plot['Material'].str[:45],
        orientation='h',
        marker_color=colors,
        text=[f"{v:,.0f}" for v in top_plot['Saldo']],
        textposition='outside',
        customdata=top_plot[['Valor_Saldo']].to_numpy(),
        hovertemplate='<b>%{y}</b><br>Saldo: %{x:,.0f}<br>Valor: S/ %{customdata[0]:,.0f}<extra></extra>'
    ))
    fig_top.update_layout(
        xaxis_title='Saldo',
        margin=dict(t=30, b=20, l=20, r=20),
        height=360,
        showlegend=False
    )
    st.plotly_chart(fig_top, use_container_width=True)

    st.subheader("📚 Distribución de Saldo")
    fig_dist = px.bar(
        saldo_df.sort_values('Saldo', ascending=False).head(15),
        x='Saldo',
        y=saldo_df.sort_values('Saldo', ascending=False).head(15)['Material'].str[:40],
        orientation='h',
        color='Saldo',
        color_continuous_scale='Blues'
    )
    fig_dist.update_layout(
        xaxis_title='Saldo',
        yaxis_title='',
        margin=dict(t=30, b=20, l=20, r=20),
        height=420
    )
    st.plotly_chart(fig_dist, use_container_width=True)

    st.markdown("---")
    st.subheader("📋 Detalle Completo de Saldos")
    with st.expander("Ver detalle completo de materiales con saldo"):
        st.dataframe(
            saldo_df.sort_values('Saldo', ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                'Saldo': st.column_config.NumberColumn(format="%.0f"),
                'Valor_Saldo': st.column_config.NumberColumn(format="%.0f")
            }
        )

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.download_button(
            label="📥 Exportar Saldos",
            data=exportar_analisis(saldo_df).getvalue(),
            file_name="analisis_saldos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )


def exportar_analisis(df_export):
    """Exporta el análisis a Excel"""
    from io import BytesIO

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, sheet_name='Saldos', index=False)
    output.seek(0)
    return output
