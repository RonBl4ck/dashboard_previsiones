"""
Página del Simulador de Presupuesto
Permite simular cambios en el presupuesto y ver su impacto
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import sys
import io

sys.path.append('..')
from components.charts import COLORS, PALETTE

@st.cache_data
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def show(df, apply_filters):
    """Función principal de la página del Simulador"""
    
    st.title("🎚️ Simulador de Presupuesto")
    
    # Aplicar filtros
    df_filtered = apply_filters(df)
    
    if df_filtered.empty:
        st.warning("No hay datos con los filtros seleccionados")
        return
    
    # Presupuesto actual
    presupuesto_actual = df_filtered['Valor materiales (MS/.)'].sum()
    
    st.markdown("""
    <div style="background-color: white; 
                border: 1px solid #E0E0E0;
                border-radius: 15px; padding: 25px; color: #1E3A8A; margin-bottom: 20px;">
        <h3 style="margin: 0; color: #555555; font-weight: normal;">Presupuesto Actual</h3>
        <h1 style="margin: 5px 0 5px 0; font-size: 2.5rem; color: #1E3A8A;">S/ {:,.0f}</h1>
        <p style="margin: 0; color: #555555;">Materiales: {} | Proyectos: {}</p>
    </div>
    """.format(presupuesto_actual, df_filtered['DESCRIPCION'].nunique(), df_filtered['Nombre del proyecto'].nunique()), 
    unsafe_allow_html=True)
    
    # Tabs para diferentes modos de simulación
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Ajuste Global", 
        "🎯 Ajuste por Proyecto", 
        "🔄 Redistribución",
        "💲 Simulación por Precio"
    ])
    
    # ============================================
    # TAB 1: Ajuste Global del Presupuesto
    # ============================================
    with tab1:
        st.subheader("Ajuste Global del Presupuesto")
        
        ajuste_tipo = st.radio(
            "Tipo de Ajuste:",
            ["Porcentual (%)", "Monto Fijo (S/.)"],
            horizontal=True
        )

        col1, col2 = st.columns([2, 1])
        
        ajuste_pct = 0
        nuevo_presupuesto = presupuesto_actual

        if ajuste_tipo == "Porcentual (%)":
            with col1:
                # Slider de ajuste
                ajuste_pct = st.slider(
                    "Variación del presupuesto (%):",
                    min_value=-50,
                    max_value=50,
                    value=0,
                    step=1,
                    help="Desliza para aumentar o reducir el presupuesto total"
                )
            nuevo_presupuesto = presupuesto_actual * (1 + ajuste_pct / 100)
        
        else: # Monto Fijo
            with col1:
                ajuste_monto = st.number_input(
                    "Aumento o Reducción del Presupuesto (S/.)",
                    value=0,
                    step=10000,
                    help="Ingresa un monto para aumentar (positivo) o reducir (negativo) el presupuesto."
                )
            nuevo_presupuesto = presupuesto_actual + ajuste_monto
            if presupuesto_actual > 0:
                ajuste_pct = (ajuste_monto / presupuesto_actual) * 100

        with col2:
            # Mostrar valores
            diferencia = nuevo_presupuesto - presupuesto_actual
            
            st.metric(
                "Nuevo Presupuesto", 
                f"S/ {nuevo_presupuesto:,.0f}",
                delta=f"S/ {diferencia:,.0f} ({ajuste_pct:+.1f}%)"
            )
        
        # Mostrar impacto por proyecto
        st.markdown("---")
        st.subheader("📋 Impacto por Proyecto (Distribución Proporcional)")
        
        # Calcular distribución proporcional
        proyectos_agg = df_filtered.groupby('Nombre del proyecto')['Valor materiales (MS/.)'].sum().reset_index()
        proyectos_agg['Participación %'] = proyectos_agg['Valor materiales (MS/.)'] / presupuesto_actual * 100
        proyectos_agg['Valor Original'] = proyectos_agg['Valor materiales (MS/.)']
        proyectos_agg['Valor Nuevo'] = proyectos_agg['Valor materiales (MS/.)'] * (1 + ajuste_pct / 100)
        proyectos_agg['Diferencia'] = proyectos_agg['Valor Nuevo'] - proyectos_agg['Valor Original']
        
        # Ordenar por valor
        proyectos_agg = proyectos_agg.sort_values('Valor Original', ascending=False)
        
        # Gráfico comparativo
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Original',
            y=proyectos_agg['Nombre del proyecto'].str[:40],
            x=proyectos_agg['Valor Original'],
            orientation='h',
            marker_color=COLORS['primary'],
            text=proyectos_agg['Valor Original'].apply(lambda x: f'{x:,.0f}'),
            textposition='auto'
        ))
        
        fig.add_trace(go.Bar(
            name='Simulado',
            y=proyectos_agg['Nombre del proyecto'].str[:40],
            x=proyectos_agg['Valor Nuevo'],
            orientation='h',
            marker_color=COLORS['secondary'],
            text=proyectos_agg['Valor Nuevo'].apply(lambda x: f'{x:,.0f}'),
            textposition='auto'
        ))
        
        fig.update_layout(
            barmode='group',
            xaxis_title='Valor (MS/.)',
            margin=dict(t=30, b=30, l=250, r=20),
            height=max(500, len(proyectos_agg) * 30),
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabla de impacto
        tabla_impacto = proyectos_agg[['Nombre del proyecto', 'Participación %', 'Valor Original', 'Valor Nuevo', 'Diferencia']].copy()
        tabla_impacto['Participación %'] = tabla_impacto['Participación %'].apply(lambda x: f"{x:.1f}%")
        tabla_impacto['Valor Original'] = tabla_impacto['Valor Original'].apply(lambda x: f"S/ {x:,.0f}")
        tabla_impacto['Valor Nuevo'] = tabla_impacto['Valor Nuevo'].apply(lambda x: f"S/ {x:,.0f}")
        tabla_impacto['Diferencia'] = tabla_impacto['Diferencia'].apply(lambda x: f"S/ {x:,.0f}")
        
        st.dataframe(tabla_impacto, use_container_width=True, hide_index=True)

        # Botón de descarga
        st.download_button(
            label="📥 Exportar Escenario",
            data=to_excel(proyectos_agg[['Nombre del proyecto', 'Participación %', 'Valor Original', 'Valor Nuevo', 'Diferencia']]),
            file_name="simulacion_ajuste_global.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )
    
    # ============================================
    # TAB 2: Ajuste por Proyecto Específico
    # ============================================
    with tab2:
        st.subheader("Ajuste Individual por Proyecto")

        proyectos = df_filtered.groupby('Nombre del proyecto')['Valor materiales (MS/.)'].sum().sort_values(ascending=False)
        
        st.markdown("""
        Selecciona los proyectos que deseas ajustar. Los cambios se reflejarán 
        en el presupuesto total.
        """)

        proyectos_seleccionados = st.multiselect(
            "Selecciona Proyectos para ajustar:",
            options=proyectos.index.tolist(),
            default=proyectos.head(3).index.tolist() # Sugerir los 3 primeros
        )

        ajustes = {}
        total_ajustes = 0

        if proyectos_seleccionados:
            st.markdown("### Ajuste de Presupuestos")
            cols = st.columns(2)
            
            for i, proyecto in enumerate(proyectos_seleccionados):
                col = cols[i % 2]
                valor = proyectos[proyecto]
                
                with col:
                    # Slider para cada proyecto
                    nuevo_valor = st.number_input(
                        f"{proyecto[:35]}...",
                        min_value=0,
                        max_value=int(valor * 3), # Aumentar rango de ajuste
                        value=int(valor),
                        step=10000,
                        key=f"proyecto_{proyecto}"
                    )
                    
                    ajustes[proyecto] = nuevo_valor
                    
                    # Mostrar diferencia
                    diff = nuevo_valor - valor
                    color = "green" if diff >= 0 else "red"
                    st.markdown(f"<span style='color: {color};'>Diferencia: S/ {diff:,.0f}</span>", unsafe_allow_html=True)

        # Calcular el nuevo total
        proyectos_no_seleccionados_valor = proyectos[~proyectos.index.isin(proyectos_seleccionados)].sum()
        total_nuevo = sum(ajustes.values()) + proyectos_no_seleccionados_valor

        st.markdown("---")
        
        # Resumen del ajuste
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Presupuesto Original", f"S/ {presupuesto_actual:,.0f}")
        with col2:
            st.metric("Presupuesto Simulado", f"S/ {total_nuevo:,.0f}")
        with col3:
            diff_total = total_nuevo - presupuesto_actual
            st.metric("Diferencia Total", f"S/ {diff_total:,.0f}", delta=f"{diff_total/presupuesto_actual*100:+.1f}%" if presupuesto_actual > 0 else "N/A")

        # Gráfico de donut comparativo
        if proyectos_seleccionados:
            col1, col2 = st.columns(2)
            
            # Datos para los gráficos
            labels_original = list(ajustes.keys())
            values_original = [proyectos[p] for p in labels_original]

            if proyectos_no_seleccionados_valor > 0:
                labels_original.append("Otros Proyectos")
                values_original.append(proyectos_no_seleccionados_valor)

            values_simulado = list(ajustes.values())
            if proyectos_no_seleccionados_valor > 0:
                values_simulado.append(proyectos_no_seleccionados_valor)


            with col1:
                fig1 = go.Figure(go.Pie(
                    labels=[l[:30] for l in labels_original],
                    values=values_original,
                    hole=0.5,
                    marker_colors=PALETTE
                ))
                fig1.update_layout(title="Distribución Original", height=400)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                fig2 = go.Figure(go.Pie(
                    labels=[l[:30] for l in labels_original],
                    values=values_simulado,
                    hole=0.5,
                    marker_colors=PALETTE
                ))
                fig2.update_layout(title="Distribución Simulada", height=400)
                st.plotly_chart(fig2, use_container_width=True)

            # Preparar datos para descarga
            df_export = pd.DataFrame({
                'Proyecto': proyectos.index,
                'Valor Original': proyectos.values,
                'Valor Simulado': [ajustes.get(p, proyectos[p]) for p in proyectos.index]
            })
            df_export['Diferencia'] = df_export['Valor Simulado'] - df_export['Valor Original']

            st.download_button(
                label="📥 Exportar Escenario",
                data=to_excel(df_export),
                file_name="simulacion_ajuste_por_proyecto.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
    
    # ============================================
    # TAB 3: Redistribución de Presupuesto
    # ============================================
    with tab3:
        st.subheader("Redistribución de Presupuesto entre Proyectos")
        
        st.markdown("""
        Simula el impacto de mover presupuesto de un proyecto a otro.
        Útil para análisis de escenarios "What-If".
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📉 Reducir de:")
            
            proyectos_lista = list(df_filtered.groupby('Nombre del proyecto')['Valor materiales (MS/.)'].sum().sort_values(ascending=False).index)
            
            proyecto_reducir = st.selectbox(
                "Proyecto a reducir:",
                proyectos_lista,
                key="proyecto_reducir"
            )
            
            valor_proyecto_reducir = df_filtered[df_filtered['Nombre del proyecto'] == proyecto_reducir]['Valor materiales (MS/.)'].sum()
            
            monto_reducir = st.number_input(
                f"Monto a reducir (Max: S/ {valor_proyecto_reducir:,.0f}):",
                min_value=0,
                max_value=int(valor_proyecto_reducir),
                value=0,
                step=10000,
                key="monto_reducir"
            )
        
        with col2:
            st.markdown("### 📈 Aumentar a:")
            
            proyectos_destino = [p for p in proyectos_lista if p != proyecto_reducir]
            
            proyecto_aumentar = st.selectbox(
                "Proyecto a aumentar:",
                proyectos_destino,
                key="proyecto_aumentar"
            )
            
            valor_proyecto_aumentar = df_filtered[df_filtered['Nombre del proyecto'] == proyecto_aumentar]['Valor materiales (MS/.)'].sum()
            
            # Mostrar valor actual
            st.info(f"Valor actual: S/ {valor_proyecto_aumentar:,.0f}")
        
        st.markdown("---")
        
        # Calcular impacto
        if monto_reducir > 0:
            st.subheader("📊 Resultado de la Redistribución")
            
            # Datos antes y después
            antes = {
                proyecto_reducir: valor_proyecto_reducir,
                proyecto_aumentar: valor_proyecto_aumentar
            }
            
            despues = {
                proyecto_reducir: valor_proyecto_reducir - monto_reducir,
                proyecto_aumentar: valor_proyecto_aumentar + monto_reducir
            }
            
            # Gráfico comparativo
            proyectos_comp = [proyecto_reducir[:30], proyecto_aumentar[:30]]
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                name='Antes',
                x=proyectos_comp,
                y=[antes[proyecto_reducir], antes[proyecto_aumentar]],
                marker_color=COLORS['primary'],
                text=[f'S/ {v:,.0f}' for v in [antes[proyecto_reducir], antes[proyecto_aumentar]]],
                textposition='outside'
            ))
            
            fig.add_trace(go.Bar(
                name='Después',
                x=proyectos_comp,
                y=[despues[proyecto_reducir], despues[proyecto_aumentar]],
                marker_color=COLORS['success'],
                text=[f'S/ {v:,.0f}' for v in [despues[proyecto_reducir], despues[proyecto_aumentar]]],
                textposition='outside'
            ))
            
            fig.update_layout(
                barmode='group',
                yaxis_title='Valor (MS/.)',
                margin=dict(t=50, b=50, l=60, r=20),
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Métricas
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    proyecto_reducir[:35],
                    f"S/ {despues[proyecto_reducir]:,.0f}",
                    delta=f"S/ {-monto_reducir:,.0f}"
                )
            
            with col2:
                st.metric(
                    proyecto_aumentar[:35],
                    f"S/ {despues[proyecto_aumentar]:,.0f}",
                    delta=f"S/ {monto_reducir:,.0f}"
                )
            
            # Sugerencia de uso
            st.markdown("---")
            st.subheader("💡 Sugerencias de Inversión")
            
            # Calcular qué se podría comprar con el monto redistribuido
            materiales_comunes = df_filtered.groupby('DESCRIPCION').agg({
                'P.U. s/.': 'first',
                'Valor materiales (MS/.)': 'sum'
            }).reset_index()
            
            materiales_comunes = materiales_comunes.sort_values('Valor materiales (MS/.)', ascending=False)
            
            st.markdown(f"Con **S/ {monto_reducir:,.0f}** adicionales en '{proyecto_aumentar[:35]}', podrías:")
            
            # Sugerir materiales que se podrían adquirir más
            sugerencias = []
            for _, row in materiales_comunes.head(5).iterrows():
                if row['P.U. s/.'] > 0:
                    cantidad_adicional = monto_reducir / row['P.U. s/.']
                    if cantidad_adicional > 1:
                        sugerencias.append({
                            'Material': row['DESCRIPCION'][:50],
                            'Cantidad Adicional': f"{cantidad_adicional:,.0f} und",
                            'Precio Unit.': f"S/ {row['P.U. s/.']:,.2f}"
                        })
            
            if sugerencias:
                df_sugerencias = pd.DataFrame(sugerencias)
                st.dataframe(df_sugerencias, use_container_width=True, hide_index=True)

            # Preparar datos para descarga
            df_export = pd.DataFrame({
                'Operación': [f'Reducir de {proyecto_reducir}', f'Aumentar a {proyecto_aumentar}'],
                'Valor Original': [antes[proyecto_reducir], antes[proyecto_aumentar]],
                'Valor Simulado': [despues[proyecto_reducir], despues[proyecto_aumentar]],
                'Diferencia': [-monto_reducir, monto_reducir]
            })

            st.download_button(
                label="📥 Exportar Escenario",
                data=to_excel(df_export),
                file_name="simulacion_redistribucion.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
    
    # ============================================
    # TAB 4: Simulación por Precio de Material
    # ============================================
    with tab4:
        st.subheader("Simulación por Cambio de Precio de Material")

        st.markdown("""
        Selecciona un material y simula un cambio en su precio unitario.
        Puedes definir explícitamente desde qué mes aplicar el cambio.
        """)

        # Selección de material
        materiales = df_filtered.sort_values('DESCRIPCION')['DESCRIPCION'].unique()
        material_seleccionado = st.selectbox(
            "Selecciona un Material:",
            materiales,
            key="material_precio_sim"
        )

        if material_seleccionado:
            df_material = df_filtered[df_filtered['DESCRIPCION'] == material_seleccionado]
            precio_actual = df_material['P.U. s/.'].iloc[0]
            meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Precio Unitario Actual", f"S/ {precio_actual:,.2f}")

            with col2:
                nuevo_precio = st.number_input(
                    "Nuevo Precio Unitario (S/.)",
                    value=float(precio_actual),
                    min_value=0.0,
                    step=0.1,
                    format="%.2f"
                )

            with col3:
                mes_inicio = st.selectbox(
                    "Aplicar cambio desde",
                    meses,
                    index=0,
                    key="mes_inicio_precio_sim"
                )

            # Simulación
            if nuevo_precio != precio_actual:
                mes_inicio_idx = meses.index(mes_inicio)
                meses_a_recalcular = meses[mes_inicio_idx:]

                cant_cols = [f'Cant_{m}' for m in meses_a_recalcular]
                valor_cols = [f'Valor_{m}' for m in meses_a_recalcular]

                # Cantidad total a futuro
                cantidad_futura = df_material[cant_cols].sum().sum()
                
                # Valores originales y nuevos
                valor_original_futuro = df_material[valor_cols].sum().sum()
                valor_nuevo_futuro = cantidad_futura * nuevo_precio

                diferencia_total = valor_nuevo_futuro - valor_original_futuro
                nuevo_presupuesto_total = presupuesto_actual + diferencia_total
                
                st.markdown("---")
                st.subheader("Impacto de la Simulación")

                col1, col2, col3 = st.columns(3)
                col1.metric("Presupuesto Original", f"S/ {presupuesto_actual:,.0f}")
                col2.metric("Nuevo Presupuesto Simulado", f"S/ {nuevo_presupuesto_total:,.0f}", delta=f"S/ {diferencia_total:,.0f}")
                col3.metric("Cantidad Afectada (und.)", f"{cantidad_futura:,.0f}")

                # Detalle por proyecto
                st.markdown(f"#### Impacto por Proyecto (desde {mes_inicio})")

                impacto_proyectos = df_material.groupby('Nombre del proyecto').agg(
                    {f'Cant_{m}': 'sum' for m in meses_a_recalcular}
                ).reset_index()

                impacto_proyectos['Cantidad Afectada'] = impacto_proyectos[[f'Cant_{m}' for m in meses_a_recalcular]].sum(axis=1)
                impacto_proyectos = impacto_proyectos[impacto_proyectos['Cantidad Afectada'] > 0]
                
                impacto_proyectos['Impacto en Valor (S/.)'] = (impacto_proyectos['Cantidad Afectada'] * nuevo_precio) - (impacto_proyectos['Cantidad Afectada'] * precio_actual)
                
                st.dataframe(
                    impacto_proyectos[['Nombre del proyecto', 'Cantidad Afectada', 'Impacto en Valor (S/.)']],
                    use_container_width=True,
                    hide_index=True,
                     column_config={
                        "Impacto en Valor (S/.)": st.column_config.NumberColumn(format="S/ %.2f")
                    }
                )
                
                # Preparar datos para descarga
                df_export = impacto_proyectos[['Nombre del proyecto', 'Cantidad Afectada', 'Impacto en Valor (S/.)']]
                
                st.download_button(
                    label="📥 Exportar Escenario",
                    data=to_excel(df_export),
                    file_name=f"simulacion_precio_{material_seleccionado[:20]}.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )
    

