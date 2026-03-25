"""
Pagina del Simulador de Presupuesto
Permite simular cambios en el presupuesto y ver su impacto.
"""

import io
import re
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.append('..')
from components.charts import PALETTE


@st.cache_data
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()


def format_project_label(project_name):
    """Convierte 'Descripcion (Codigo)' a 'Codigo - Descripcion'."""
    if not isinstance(project_name, str):
        return project_name

    match = re.match(r"^(.*)\s+\((.*)\)$", project_name.strip())
    if not match:
        return project_name

    descripcion, codigo = match.groups()
    return f"{codigo.strip()} - {descripcion.strip()}"


def build_project_budget_table(df_filtered, overrides):
    """Construye la tabla de presupuestos por proyecto aplicando overrides activos."""
    proyectos = df_filtered.groupby('Nombre del proyecto')['Valor materiales (MS/.)'].sum().reset_index()
    proyectos.columns = ['Proyecto', 'Presupuesto Original']
    proyectos = proyectos.sort_values('Presupuesto Original', ascending=False).reset_index(drop=True)
    proyectos['Presupuesto Simulado'] = proyectos['Proyecto'].map(overrides).fillna(proyectos['Presupuesto Original'])
    return proyectos


def show(df, apply_filters):
    """Funcion principal de la pagina del Simulador."""

    st.title("Simulador de Presupuesto")

    df_filtered = apply_filters(df)

    if df_filtered.empty:
        st.warning("No hay datos con los filtros seleccionados")
        return

    df_filtered = df_filtered.copy()
    df_filtered['Nombre del proyecto'] = df_filtered['Nombre del proyecto'].apply(format_project_label)

    presupuesto_actual = df_filtered['Valor materiales (MS/.)'].sum()

    st.markdown(
        """
        <div style="background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 15px; padding: 25px; color: #1E3A8A; margin-bottom: 20px;">
            <h3 style="margin: 0; color: #555555; font-weight: normal;">Presupuesto Actual</h3>
            <h1 style="margin: 5px 0 5px 0; font-size: 2.5rem; color: #1E3A8A;">S/ {:,.0f}</h1>
            <p style="margin: 0; color: #555555;">Materiales: {} | Proyectos: {}</p>
        </div>
        """.format(
            presupuesto_actual,
            df_filtered['DESCRIPCION'].nunique(),
            df_filtered['Nombre del proyecto'].nunique(),
        ),
        unsafe_allow_html=True,
    )

    st.subheader("Ajuste por Proyecto")

    state_key = "simulador_project_overrides"
    if state_key not in st.session_state:
        st.session_state[state_key] = {}

    proyectos = build_project_budget_table(df_filtered, st.session_state[state_key])

    st.markdown(
        """
        Busca un proyecto para simularlo de forma puntual.
        Si necesitas una edicion masiva, abre la tabla completa.
        """
    )

    proyecto_seleccionado = st.selectbox(
        "Buscar y seleccionar proyecto:",
        proyectos['Proyecto'].tolist(),
        key="proyecto_objetivo_simulador",
    )

    proyecto_actual = proyectos[proyectos['Proyecto'] == proyecto_seleccionado].iloc[0]

    col1, col2 = st.columns([2, 1])
    with col1:
        st.dataframe(
            pd.DataFrame([proyecto_actual]),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Proyecto": st.column_config.TextColumn("Proyecto"),
                "Presupuesto Original": st.column_config.NumberColumn(
                    "Presupuesto Original (S/.)",
                    format="S/ %.2f",
                ),
                "Presupuesto Simulado": st.column_config.NumberColumn(
                    "Presupuesto Simulado (S/.)",
                    format="S/ %.2f",
                ),
            },
        )
    with col2:
        nuevo_presupuesto = st.number_input(
            "Nuevo presupuesto simulado",
            min_value=0.0,
            value=float(proyecto_actual['Presupuesto Simulado']),
            step=1000.0,
            format="%.2f",
            key=f"presupuesto_simulado_{proyecto_seleccionado}",
        )
        if st.button("Aplicar ajuste", use_container_width=True, key="aplicar_ajuste_proyecto"):
            st.session_state[state_key][proyecto_seleccionado] = nuevo_presupuesto
            st.rerun()
        if st.button("Restablecer proyecto", use_container_width=True, key="reset_ajuste_proyecto"):
            st.session_state[state_key].pop(proyecto_seleccionado, None)
            st.rerun()

    edited_proyectos = build_project_budget_table(df_filtered, st.session_state[state_key])

    with st.expander("Ver tabla completa de proyectos", expanded=False):
        filtro_tabla = st.text_input(
            "Filtrar proyectos en la tabla completa:",
            key="filtro_tabla_proyectos_simulador",
        ).strip().lower()

        tabla_completa = edited_proyectos.copy()
        if filtro_tabla:
            tabla_completa = tabla_completa[
                tabla_completa['Proyecto'].str.lower().str.contains(filtro_tabla, na=False)
            ]

        tabla_editada_completa = st.data_editor(
            tabla_completa,
            column_config={
                "Proyecto": st.column_config.TextColumn("Proyecto", disabled=True),
                "Presupuesto Original": st.column_config.NumberColumn(
                    "Presupuesto Original (S/.)",
                    format="S/ %.2f",
                    disabled=True,
                ),
                "Presupuesto Simulado": st.column_config.NumberColumn(
                    "Presupuesto Simulado (S/.)",
                    format="S/ %.0f",
                    step=1000.0,
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="editor_proyectos_completo",
        )

        cambios_tabla = dict(
            zip(
                tabla_editada_completa['Proyecto'],
                tabla_editada_completa['Presupuesto Simulado'],
            )
        )
        for proyecto, presupuesto in cambios_tabla.items():
            st.session_state[state_key][proyecto] = presupuesto

        edited_proyectos = build_project_budget_table(df_filtered, st.session_state[state_key])

    edited_proyectos['Diferencia'] = (
        edited_proyectos['Presupuesto Simulado'] - edited_proyectos['Presupuesto Original']
    )
    proyectos_modificados = edited_proyectos[edited_proyectos['Diferencia'] != 0].copy()
    total_nuevo = edited_proyectos['Presupuesto Simulado'].sum()

    if not proyectos_modificados.empty:
        st.markdown("#### Proyectos modificados")
        st.dataframe(
            proyectos_modificados[['Proyecto', 'Presupuesto Original', 'Presupuesto Simulado', 'Diferencia']],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Presupuesto Original": st.column_config.NumberColumn(format="S/ %.2f"),
                "Presupuesto Simulado": st.column_config.NumberColumn(format="S/ %.2f"),
                "Diferencia": st.column_config.NumberColumn(format="S/ %+.2f"),
            },
        )

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Presupuesto Original", f"S/ {presupuesto_actual:,.0f}")
    with col2:
        st.metric("Presupuesto Simulado", f"S/ {total_nuevo:,.0f}")
    with col3:
        diff_total = total_nuevo - presupuesto_actual
        delta_pct = f"{diff_total / presupuesto_actual * 100:+.1f}%" if presupuesto_actual > 0 else "N/A"
        st.metric("Diferencia Total", f"S/ {diff_total:,.0f}", delta=delta_pct)

    if proyectos_modificados.empty:
        st.info("Modifica algun presupuesto simulado en la tabla superior para ver el impacto.")
        return

    col1, col2 = st.columns(2)

    mod_names = proyectos_modificados['Proyecto'].tolist()
    otros_original = edited_proyectos[~edited_proyectos['Proyecto'].isin(mod_names)]['Presupuesto Original'].sum()
    otros_simulado = edited_proyectos[~edited_proyectos['Proyecto'].isin(mod_names)]['Presupuesto Simulado'].sum()

    labels_pie = mod_names + (["Otros Proyectos"] if otros_original > 0 else [])
    values_orig_pie = proyectos_modificados['Presupuesto Original'].tolist() + ([otros_original] if otros_original > 0 else [])
    values_sim_pie = proyectos_modificados['Presupuesto Simulado'].tolist() + ([otros_simulado] if otros_simulado > 0 else [])

    with col1:
        fig1 = go.Figure(
            go.Pie(
                labels=[label[:30] for label in labels_pie],
                values=values_orig_pie,
                hole=0.5,
                marker_colors=PALETTE,
            )
        )
        fig1.update_layout(title="Distribucion Original", height=400)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = go.Figure(
            go.Pie(
                labels=[label[:30] for label in labels_pie],
                values=values_sim_pie,
                hole=0.5,
                marker_colors=PALETTE,
            )
        )
        fig2.update_layout(title="Distribucion Simulada", height=400)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.subheader("Impacto en Cantidad de Materiales")

    df_afectados = df_filtered[df_filtered['Nombre del proyecto'].isin(mod_names)].copy()
    proyectos_modificados['Ratio Ajuste'] = (
        proyectos_modificados['Presupuesto Simulado']
        / proyectos_modificados['Presupuesto Original'].replace(0, 1)
    )
    ratio_dict = dict(zip(proyectos_modificados['Proyecto'], proyectos_modificados['Ratio Ajuste']))
    df_afectados['Ratio'] = df_afectados['Nombre del proyecto'].map(ratio_dict)
    df_afectados['Total/Cantidad'] = df_afectados['Total/Cantidad'].fillna(0)

    materiales_agg = df_afectados.groupby(['Nombre del proyecto', 'DESCRIPCION']).agg({
        'Total/Cantidad': 'sum',
        'Cant_Ene': 'sum',
        'Cant_Feb': 'sum',
        'Cant_Mar': 'sum',
        'Cant_Abr': 'sum',
        'Cant_May': 'sum',
        'Cant_Jun': 'sum',
        'Cant_Jul': 'sum',
        'Cant_Ago': 'sum',
        'Cant_Sep': 'sum',
        'Cant_Oct': 'sum',
        'Cant_Nov': 'sum',
        'Cant_Dic': 'sum',
        'Ratio': 'first',
    }).reset_index()

    materiales_agg['Cantidad Original'] = materiales_agg['Total/Cantidad']
    materiales_agg['Cantidad Simulada'] = materiales_agg['Total/Cantidad'] * materiales_agg['Ratio']
    materiales_agg['Diferencia Cantidad'] = (
        materiales_agg['Cantidad Simulada'] - materiales_agg['Cantidad Original']
    )

    meses_cant = [
        'Cant_Ene', 'Cant_Feb', 'Cant_Mar', 'Cant_Abr', 'Cant_May', 'Cant_Jun',
        'Cant_Jul', 'Cant_Ago', 'Cant_Sep', 'Cant_Oct', 'Cant_Nov', 'Cant_Dic',
    ]
    meses_labels = {
        'Cant_Ene': 'Ene',
        'Cant_Feb': 'Feb',
        'Cant_Mar': 'Mar',
        'Cant_Abr': 'Abr',
        'Cant_May': 'May',
        'Cant_Jun': 'Jun',
        'Cant_Jul': 'Jul',
        'Cant_Ago': 'Ago',
        'Cant_Sep': 'Sep',
        'Cant_Oct': 'Oct',
        'Cant_Nov': 'Nov',
        'Cant_Dic': 'Dic',
    }

    for mes in meses_cant:
        materiales_agg[f'Sim_{mes}'] = materiales_agg[mes] * materiales_agg['Ratio']

    tabla_mostrar = materiales_agg[
        ['Nombre del proyecto', 'DESCRIPCION', 'Cantidad Original', 'Cantidad Simulada', 'Diferencia Cantidad']
    ].copy()
    st.dataframe(
        tabla_mostrar,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cantidad Original": st.column_config.NumberColumn(format="%.2f"),
            "Cantidad Simulada": st.column_config.NumberColumn(format="%.2f"),
            "Diferencia Cantidad": st.column_config.NumberColumn(format="%+.2f"),
        },
    )

    st.markdown("#### Detalle mensual por material")
    proyecto_detalle = st.selectbox(
        "Proyecto para ver el detalle mensual:",
        mod_names,
        key="proyecto_detalle_ajuste",
    )

    detalle_proyecto = materiales_agg[materiales_agg['Nombre del proyecto'] == proyecto_detalle].copy()
    detalle_mensual = detalle_proyecto[['Nombre del proyecto', 'DESCRIPCION']].copy()

    for mes in meses_cant:
        mes_label = meses_labels[mes]
        detalle_mensual[f'{mes_label} Original'] = detalle_proyecto[mes]
        detalle_mensual[f'{mes_label} Simulado'] = detalle_proyecto[f'Sim_{mes}']
        detalle_mensual[f'{mes_label} Dif.'] = detalle_proyecto[f'Sim_{mes}'] - detalle_proyecto[mes]

    st.dataframe(
        detalle_mensual,
        use_container_width=True,
        hide_index=True,
        column_config={
            col: st.column_config.NumberColumn(format="%.2f")
            for col in detalle_mensual.columns
            if col not in ['Nombre del proyecto', 'DESCRIPCION']
        },
    )

    cols_export = [
        'Nombre del proyecto', 'DESCRIPCION', 'Cantidad Original', 'Cantidad Simulada', 'Diferencia Cantidad'
    ]
    for mes in meses_cant:
        cols_export.extend([mes, f'Sim_{mes}'])

    df_export_materiales = materiales_agg[cols_export]

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Exportar Ajustes por Proyecto",
            data=to_excel(edited_proyectos),
            file_name="simulacion_ajuste_proyectos.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            label="Exportar Evolucion Materiales (Mes a Mes)",
            data=to_excel(df_export_materiales),
            file_name="simulacion_materiales_evolucion.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True,
        )
