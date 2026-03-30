import re

filepath = r'd:\PROGRAMACION\dashboard_previsiones\pages\resumen_ejecutivo.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Already replaced Promedio_Historico with Maximo_Historico, but just in case:
content = content.replace("Consumo Promedio Histórico", "Consumo Máximo Histórico")
content = content.replace("Prom. Histórico", "Máx. Histórico")

# Reemplazar bloque de UI de 2 columnas por uno dinamico
target_block_regex = re.compile(r'# Top Variaciones Absolutas.*st\.info\("No hay reducciones registradas\."\)', re.DOTALL)

new_ui = """# Controles de Visualización
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
                st.info("No hay registros que coincidan con esta selección.")"""

content = target_block_regex.sub(new_ui, content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Edición de UI completada exitosamente.")
