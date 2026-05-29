# TFG-asignacion-menores
Código de Python del Trabajo de Fin de Grado de Gloria Rivas: **Modelo de asignación de menores no acompañados a centros de acogida en España**.


## Contenido

- `codigo/`: scripts utilizados para construir y resolver el modelo.
- `datos/`: ficheros de entrada utilizados.
- `resultados/`: tablas y figuras generadas.

---

## Archivos principales

### `version1.py`

Implementa el modelo matemático final desarrollado en el TFG (solucionado con el método lexicográfico como ejemplo).

Incluye:

* Definición de conjuntos y parámetros.
* Índice compuesto de bienestar.
* Restricciones de capacidad y emergencia.
* Funciones objetivo multiobjetivo.

---

### `version2.py`

Implementa el modelo 2 (solucionado con el método lexicográfico como ejemplo).

Incluye:

* Definición de conjuntos y parámetros.
* Construcción de la cuota de equidad territorial basada en el Real Decreto-ley 2/2025.
* Índice compuesto de bienestar (con las modificaciones correspondientes).
* Restricciones de capacidad y emergencia.
* Funciones objetivo multiobjetivo (con las modificaciones correspondientes).

---

### `generacion_probabilidades.py`

Genera las matrices de preferencias utilizadas por el modelo:

* `R_ij.xlsx`
* `L_ij.xlsx`

Las preferencias se construyen a partir de hipótesis de permanencia territorial y proximidad geográfica entre comunidades autónomas.

---

### `conjuntoeficiente_completo.py`

Construcción aproximada del conjunto eficiente con las correspondientes variables asociadas a cada una de las soluciones. Utiliza para ello:

* Método de ponderaciones.
* Método de las epsilon-restricciones.

---

### `lex_wgp.py`

Implementa los métodos de optimización multicriterio:

* Método lexicográfico.
* Weighted Goal Programming (WGP).

---

### `compromiseprogramming_direct.py`

Calcula las soluciones de compromiso para cada versión directamente, sin utilizar el conjunto eficiente aproximado como base.

---

### `seleccionsoluciones.py`

Selecciona soluciones representativas del conjunto eficiente utilizando:

* Soluciones extremas.
* Compromise Programming aproximado.
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
python src/version1.py
python src/version2.py
```

### 3. Resolver los escenarios multiobjetivo

```bash
python src/conjuntoeficiente_completo.py
python src/lex_wgp.py
```

### 4. Seleccionar soluciones representativas

```bash
python src/seleccionsoluciones.py
python src/compromiseprogramming_direct.py
python src/compromiseprogramming_direct2.py
```

### 5. Generar métricas e indicadores

```bash
python src/generador_metricasresultados.py
python src/generador_kpi.py
```

---

## Trabajo académico asociado

Gloria Rivas.

**Modelo de asignación de menores no acompañados a centros de acogida en España.**

Trabajo de Fin de Grado en Ingeniería Matemática.

Universidad Complutense de Madrid (UCM), 2026.

---

## Licencia

Este repositorio se publica con fines académicos y de investigación.
