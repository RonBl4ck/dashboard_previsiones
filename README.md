# 📊 Dashboard de Previsiones 2026

Dashboard interactivo para el análisis y gestión de previsiones de materiales desarrollado con **Python** y **Streamlit**.

## 🚀 Características

- **Resumen Ejecutivo**: KPIs principales y distribución del presupuesto
- **Previsión Mensual**: Evolución temporal y análisis por proyecto
- **Previsión vs Real**: Comparación con datos de consumo real
- **Simulador de Presupuesto**: Análisis de escenarios "What-If"
- **Saldos y Ajustes**: Integración de inventarios y cálculo de necesidades netas

## 📋 Requisitos

- Python 3.9+
- Las librerías listadas en `requirements.txt`

## 🛠️ Instalación

### 1. Crear entorno virtual (recomendado)

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Colocar datos

Coloca tu archivo de previsión en la carpeta `data/` con el nombre `prevision_2026.xlsx`.

## 🚀 Ejecución

```bash
cd dashboard_previsiones
streamlit run app.py
```

El dashboard se abrirá automáticamente en tu navegador en `http://localhost:8501`

## 📁 Estructura del Proyecto

```
dashboard_previsiones/
├── app.py                    # Aplicación principal
├── pages/
│   ├── __init__.py
│   ├── resumen_ejecutivo.py  # Pestaña 1: Resumen
│   ├── prevision_mensual.py  # Pestaña 2: Mensual
│   ├── prevision_vs_real.py  # Pestaña 3: Vs Real
│   ├── simulador.py          # Pestaña 4: Simulador
│   └── saldos.py             # Pestaña 5: Saldos
├── components/
│   ├── __init__.py
│   ├── charts.py             # Gráficos reutilizables
│   └── kpis.py               # Componentes de KPIs
├── utils/
│   ├── __init__.py
│   └── data_utils.py         # Utilidades de datos
├── data/
│   └── prevision_2026.xlsx   # Archivo de datos
├── requirements.txt          # Dependencias
└── README.md                 # Este archivo
```

## 📊 Páginas del Dashboard

### 1. Resumen Ejecutivo
- KPIs principales (presupuesto, cantidad, proyectos)
- Distribución por Sección (Colonial/Panamericana)
- Distribución por Área (MT/BT/AP)
- Treemap de proyectos
- Top materiales por valor

### 2. Previsión Mensual
- Evolución mensual de valores/cantidades
- Distribución mensual por proyecto
- Heatmap de proyecto vs mes
- Tabla detallada mensual

### 3. Previsión vs Consumo Real
- Carga de archivo de consumo real
- Gráfico comparativo mensual
- Gauge de % de ejecución
- Desviación acumulada
- Heatmap de cumplimiento

### 4. Simulador de Presupuesto
- Ajuste porcentual global
- Ajuste individual por proyecto
- Redistribución entre proyectos
- Sugerencias de inversión

### 5. Saldos y Ajustes
- Carga de archivo de saldos
- Cálculo de necesidades netas
- Materiales con excedentes
- Materiales con déficit

## 🎨 Personalización

### Colores Corporativos
Los colores se pueden modificar en `components/charts.py`:

```python
COLORS = {
    'primary': '#1B3F66',
    'secondary': '#2E86AB', 
    'accent': '#E94F37',
    'success': '#2ECC71',
    'warning': '#F39C12',
}
```

### Filtros Globales
Los filtros del sidebar se pueden extender en `app.py` agregando nuevos selectboxes.

## 📝 Formato de Archivos de Entrada

### Archivo de Previsión (requerido)
- Hoja: `PREVISION 01.26-(PI%)`
- Columnas: Seccion, AREA, Nombre del proyecto, DESCRIPCION, meses, etc.

### Archivo de Consumo Real (opcional)
- Columnas: Matricula/DESCRIPCION, Ene, Feb, Mar, ... Dic

### Archivo de Saldos (opcional)
- Columnas: DESCRIPCION/Matricula, Saldo/Stock/Cantidad

## 🔧 Edición desde VSCode

1. Abre la carpeta `dashboard_previsiones` en VSCode
2. Instala la extensión de Python
3. Edita los archivos según necesites
4. Los cambios se reflejarán automáticamente (hot reload)

### Archivos más comunes a editar:
- `components/charts.py`: Modificar tipos de gráficos
- `components/kpis.py`: Agregar nuevos KPIs
- `pages/*.py`: Modificar cada pestaña
- `app.py`: Cambiar navegación o filtros

## 📈 Exportación

El dashboard incluye botones para exportar:
- Escenarios simulados a Excel
- Análisis de saldos a Excel
- Datos filtrados a CSV

## 🐛 Solución de Problemas

### Error: "Module not found"
```bash
pip install -r requirements.txt
```

### Error: "File not found"
Verifica que el archivo de datos esté en `data/prevision_2026.xlsx`

### Gráficos no se muestran
Verifica que plotly esté instalado correctamente:
```bash
pip install plotly --upgrade
```

## 📞 Soporte

Para consultas sobre el dashboard, contactar al equipo de desarrollo.

---

**Desarrollado con ❤️ usando Streamlit**
