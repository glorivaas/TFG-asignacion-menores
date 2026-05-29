# TFG-asignacion-menores
Código de Python del Trabajo de Fin de Grado de Gloria Rivas: **Modelo de asignación de menores no acompañados a centros de acogida en España**.


## Contenido

- `codigo/`: scripts utilizados para construir y resolver el modelo.
- `datos/`: ficheros de entrada utilizados.
- `resultados/`: tablas y figuras generadas.

## Ejecución

Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Requisitos adicionales

El proyecto utiliza Gurobi Optimizer.

Es necesario disponer de una licencia válida de Gurobi para ejecutar los modelos de optimización.

# TFG-asignacion-menores

Código fuente desarrollado para el Trabajo de Fin de Grado de **Gloria Rivas** (Ingeniería Matemática), titulado:

**Modelo de asignación de menores migrantes no acompañados a centros de acogida en España mediante optimización multiobjetivo.**

## Descripción

Este proyecto desarrolla un modelo matemático de optimización multiobjetivo para la asignación territorial de menores migrantes no acompañados (MMNA) a centros de acogida en España.

El modelo busca equilibrar simultáneamente tres objetivos:

1. **Equidad territorial**, distribuyendo la responsabilidad de acogida entre comunidades autónomas.
2. **Eficiencia económica**, minimizando los costes asociados a traslados, apertura de plazas y situaciones de emergencia.
3. **Bienestar e integración de los menores**, incorporando preferencias territoriales e indicadores sociales de las comunidades receptoras.

La formulación se implementa mediante programación lineal entera mixta utilizando **Gurobi Optimizer**.

---

## Estructura del repositorio

```text
TFG-asignacion-menores/
│
├── README.md
├── requirements.txt
├── .gitignore
│
├── src/
│   ├── version2.py
│   ├── generacion_probabilidades.py
│   ├── lex_wgp.py
│   ├── seleccionsoluciones.py
│   ├── generador_metricasresultados.py
│   └── generador_kpi.py
│
├── data/
│   ├── plazasCCAA.xlsx
│   ├── llegadas.xlsx
│   ├── Costestraslado.xlsx
│   ├── CostesCCAA2.xlsx
│   ├── poblacion.xlsx
│   ├── renta_hogares.xlsx
│   ├── tasa_paro.xlsx
│   ├── dispersion.xlsx
│   ├── esfuerzo_mena.xlsx
│   ├── plazas_dimensionamiento.xlsx
│   ├── indice_bienestar_v2.xlsx
│   ├── R_ij.xlsx
│   └── L_ij.xlsx
│
└── docs/
    └── TFG_Gloria_Rivas.pdf
```

---

## Archivos principales

### `version2.py`

Implementa el modelo matemático final desarrollado en el TFG.

Incluye:

* Definición de conjuntos y parámetros.
* Construcción de la cuota de equidad territorial basada en el Real Decreto-ley 2/2025.
* Índice compuesto de bienestar.
* Restricciones de capacidad y emergencia.
* Funciones objetivo multiobjetivo.

---

### `generacion_probabilidades.py`

Genera las matrices de preferencias utilizadas por el modelo:

* `R_ij.xlsx`
* `L_ij.xlsx`

Las preferencias se construyen a partir de hipótesis de permanencia territorial y proximidad geográfica entre comunidades autónomas.

---

### `lex_wgp.py`

Implementa los métodos de optimización multiobjetivo empleados en el trabajo:

* Optimización lexicográfica.
* Weighted Goal Programming (WGP).

---

### `seleccionsoluciones.py`

Selecciona soluciones representativas del conjunto eficiente utilizando:

* Soluciones extremas.
* Compromise Programming.
* Diversificación mediante farthest-point sampling.

---

### `generador_metricasresultados.py`

Calcula métricas de desempeño de las soluciones obtenidas:

* Cumplimiento de preferencias.
* Movilidad territorial.
* Uso de capacidad.
* Indicadores globales.

---

### `generador_kpi.py`

Genera indicadores resumen y tablas empleadas en el análisis de resultados.

---

## Datos utilizados

Los datos empleados proceden de fuentes públicas oficiales y de indicadores construidos específicamente para el proyecto.

Entre ellos:

* Capacidad y ocupación de los sistemas de acogida.
* Población de las comunidades autónomas.
* Renta disponible por hogar.
* Tasa de paro.
* Dispersión poblacional.
* Indicadores de esfuerzo previo de acogida.
* Índices compuestos de bienestar.

Los ficheros incluidos permiten reproducir íntegramente los experimentos realizados en el TFG.

---

## Instalación

Instalar las dependencias del proyecto:

```bash
pip install -r requirements.txt
```

---

## Requisitos adicionales

El proyecto utiliza **Gurobi Optimizer** para resolver los modelos de programación lineal entera mixta.

Es necesario disponer de una licencia válida de Gurobi:

https://www.gurobi.com

---

## Reproducción de resultados

Flujo recomendado:

### 1. Generar preferencias

```bash
python src/generacion_probabilidades.py
```

### 2. Ejecutar el modelo

```bash
python src/version2.py
```

### 3. Resolver los escenarios multiobjetivo

```bash
python src/lex_wgp.py
```

### 4. Seleccionar soluciones representativas

```bash
python src/seleccionsoluciones.py
```

### 5. Generar métricas e indicadores

```bash
python src/generador_metricasresultados.py

python src/generador_kpi.py
```

---

## Trabajo académico asociado

Gloria Rivas.

**Modelo de asignación de menores migrantes no acompañados a centros de acogida en España mediante optimización multiobjetivo.**

Trabajo de Fin de Grado en Ingeniería Matemática.

Universidad Pontificia Comillas (ICAI), 2026.

---

## Licencia

Este repositorio se publica con fines académicos y de investigación.
