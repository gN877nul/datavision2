# datavision2

# Explicación del código de DataVision

Esta guía explica cómo funciona cada archivo, qué hace cada función importante y cómo se conecta la interfaz gráfica con los cálculos.

---

## 1. Visión general

El proyecto está dividido en tres capas. Cada una tiene una sola responsabilidad:

```
ventas_ferreteria.csv
        │
        ▼
 analitica.py      →  lee, valida y calcula (no sabe nada de ventanas)
        │
        ▼
 graficas.py       →  dibuja las gráficas con matplotlib (no sabe nada de ventanas)
        │
        ▼
 datavision.py     →  muestra todo en una ventana Tkinter y responde a los clics
```

Esta separación tiene una ventaja práctica: si mañana los datos vienen de MySQL, solo cambia la parte de lectura en `analitica.py`. La interfaz y las gráficas no se tocan.

---

## 2. `analitica.py`: la lógica de datos

Este archivo no abre ventanas. Recibe datos y devuelve resultados. Todas sus funciones son "puras" en el sentido de que, dada la misma entrada, siempre dan la misma salida.

### Constantes

Al inicio se definen valores fijos del análisis, como `MESES_COMPARACION = 10` (enero a octubre) o `UMBRAL_ATIPICO = 2.0`. Si el documento de requerimientos cambia una regla, basta con modificar esa constante.

### Carga y validación: `cargar_csv(ruta)`

1. Lee el CSV con `pandas.read_csv`.
2. Revisa que existan todas las columnas esperadas. Si falta alguna, lanza `ErrorDatos`.
3. Convierte los números y limpia los textos (quita espacios).
4. Aplica las cuatro reglas de calidad de datos. Cada regla es una **máscara**: una lista de `True` / `False` que indica qué filas la incumplen.
   - Campos obligatorios vacíos.
   - Unidades, precio o costo que no sean mayores que cero.
   - Costo que no sea menor que el precio.
   - Periodo que no coincida con año y mes.
5. Las filas que incumplen alguna regla se descartan. Se cuenta cuántas cayeron por cada motivo.
6. Calcula dos columnas nuevas:
   - `ingresos = unidades × precio_unit`
   - `margen = unidades × (precio_unit − costo_unit)`

Devuelve dos cosas: la tabla limpia y un resumen (`total`, `usados`, `descartados`, `motivos`).

> **Concepto clave:** una máscara es una forma de decir "marca las filas malas" sin usar bucles. Por ejemplo, `df["unidades"] <= 0` produce `True` en cada fila con unidades negativas o cero.

### Filtros: `filtrar(df, categoria, canal)`

Si la categoría elegida es "Todas las categorías", no filtra por categoría. Si es una categoría concreta, conserva solo esas filas. Lo mismo ocurre con el canal. Así, los filtros "Todos" no requieren un caso especial en el resto del código.

### KPI: `kpis(df)` y `comparar_kpis(df, anio_act, anio_ant)`

- `kpis` suma ingresos, unidades y margen de la tabla que recibe. Calcula el margen en porcentaje (`margen ÷ ingresos × 100`) y el precio promedio (`ingresos ÷ unidades`).
- `comparar_kpis` llama a `kpis` dos veces, una con enero–octubre del año actual y otra con enero–octubre del anterior. Luego calcula la variación porcentual de cada indicador con la función `variacion(actual, anterior)`.

`variacion` devuelve `None` cuando no se puede calcular (por ejemplo, si el año anterior no tiene datos). Esto evita divisiones entre cero.

### Serie mensual: `ingresos_mensuales(df, periodos)`

Agrupa las ventas por mes con `groupby`. Luego usa `reindex` con la lista completa de meses. Si un mes no tiene ventas en la selección, aparece con valor cero en lugar de desaparecer. Esto es importante para que la línea de tiempo no tenga huecos.

### Atípicos: `atipicos(serie)`

Calcula el **puntaje z** de cada mes:

```
z = (ingreso del mes − promedio) ÷ desviación estándar
```

Un mes es atípico si `|z| > 2`, es decir, si se aleja más de dos desviaciones estándar del promedio. Devuelve una tabla con el periodo, el ingreso, el z y un indicador `atipico` (`True` o `False`).

### Proyección: `proyeccion(serie)`

Usa `numpy.polyfit`, que ajusta una recta de mínimos cuadrados (`y = pendiente × x + intercepto`) sobre los últimos 12 meses. Después evalúa esa recta en los tres meses siguientes. Los valores negativos se llevan a cero con `np.maximum`. El resultado es una estimación, no un dato real, y así se presenta en la interfaz.

### Barras por categoría: `barras_categoria(df, anio_act, anio_ant)`

Crea una tabla con una fila por categoría y tres columnas: ingresos del año anterior, ingresos del año actual y variación. Usa `unstack` para convertir los años en columnas, que es la forma más directa de comparar dos periodos lado a lado.

### Distribución: `distribucion(df, campo)`

Suma los ingresos de cada valor del campo (canal o categoría) y calcula su participación sobre el total. Como cada participación es su ingreso dividido entre el total, la suma siempre da 100 %.

### Productos: `tabla_productos(df, anio_act, anio_ant)`

Agrupa por producto y categoría, calcula ingresos y margen, y agrega la variación ene–oct. Ordena de mayor a menor ingreso.

### Informe: `generar_informe(df, anio_act, anio_ant)`

Genera los textos del informe a partir de números calculados, no escritos a mano:

- **Hallazgo 1:** la categoría con mayor crecimiento, tomada con `idxmax()` sobre la variación.
- **Hallazgo 2:** la categoría con menor margen, tomada con `idxmin()`.
- **Recomendación:** combina ambos hallazgos y la participación de marzo a julio en los ingresos.

Como usa todos los datos y no los filtros, el informe no cambia cuando el usuario filtra (regla RN-06).

---

## 3. `graficas.py`: el dibujo

Este archivo recibe un eje (`ax`) de matplotlib y lo llena con datos. No crea ventanas ni sabe de Tkinter.

- **`dibujar_lineas`:** dibuja la línea de ingresos mensuales. Los meses atípicos aparecen como puntos rojos. La proyección se dibuja con una línea punteada que empieza en el último dato real, para que se vea su continuidad.
- **`dibujar_barras_categoria`:** dibuja dos barras por categoría (año anterior y actual) y coloca la variación encima de cada grupo. La variación va en verde si sube y en rojo si baja.
- **`dibujar_distribucion_canal`:** dibuja un anillo (gráfica de dona) con la participación de cada canal.

Todas tienen un caso especial: si no hay datos, muestran el mensaje "Sin datos para esta selección" en lugar de fallar.

---

## 4. `datavision.py`: la interfaz gráfica

### Qué es Tkinter

Tkinter es la biblioteca de Python para crear ventanas. Funciona con **widgets** (elementos visuales): botones, etiquetas, tablas, cuadros de texto. Los widgets se organizan en **contenedores** (marcos o *frames*), y se colocan con `pack` o `grid`.

### La clase principal

```python
class DataVisionApp(tk.Tk):
```

La aplicación es una clase que hereda de `tk.Tk`, la ventana principal. Todo lo que la ventana necesita (variables, widgets, datos cargados) vive como atributos de la clase, por ejemplo `self.df_full` o `self.tarjetas`.

El método `__init__` construye la ventana en este orden:

1. Define estilos y tamaño de la ventana.
2. Crea el encabezado con los filtros.
3. Crea las siete pestañas.
4. Crea la barra de estado inferior.
5. Carga el CSV por defecto, si existe.

### Variables que se enlazan a los filtros

```python
self.var_categoria = tk.StringVar(value=an.TODAS_CATEGORIAS)
```

Una `StringVar` es una variable que la interfaz observa. Cuando el usuario elige otra categoría en la lista, la variable cambia. Por eso el código siempre puede preguntar `self.var_categoria.get()` para saber qué está seleccionado.

### Cómo responde la interfaz a los clics

Los widgets reciben un `command` o un `bind` que indica qué función ejecutar:

```python
self.combo_categoria.bind("<<ComboboxSelected>>", lambda e: self.actualizar())
```

Esta línea significa: cuando el usuario elija algo en la lista, ejecuta `actualizar()`. El `lambda` es solo una forma corta de escribir una función sin nombre que recibe el evento y luego llama a `actualizar`.

### El corazón de la aplicación: `actualizar()`

Esta función se ejecuta cada vez que cambia un filtro. Su flujo es:

1. Filtra los datos con `an.filtrar(...)`.
2. Calcula serie mensual, atípicos y proyección.
3. Llama a cada actualizador de pestaña: resumen, gráficas, productos y atípicos.
4. Actualiza la barra de estado.

Por eso la interfaz siempre está sincronizada: todas las pestañas se recalculan desde la misma selección.

### Cómo se llena una tabla

Las tablas son widgets `Treeview`. Para llenarlas, la función primero borra las filas anteriores y luego inserta las nuevas:

```python
self.tv_productos.delete(*self.tv_productos.get_children())
for _, fila in tabla.iterrows():
    self.tv_productos.insert("", "end", values=(...), tags=(...))
```

Los `tags` permiten colorear filas. Por ejemplo, la variación positiva se pinta en verde y la negativa en rojo.

### Cómo se actualizan las tarjetas de KPI

Cada tarjeta es un `Frame` con tres etiquetas: título, valor y variación. Se guardan en un diccionario (`self.tarjetas`) con una clave por indicador. Después, `_actualizar_resumen` cambia el texto y el color de cada etiqueta con `.config(...)`. Esto evita crear widgets nuevos cada vez.

### Cómo se dibujan las gráficas en la ventana

Matplotlib produce figuras, y `FigureCanvasTkAgg` las incrusta en una ventana Tkinter. El método `_dibujar_graficas` borra la figura, crea tres áreas con una cuadrícula (`add_gridspec`) y pide a `graficas.py` que las dibuje. La barra de herramientas de matplotlib permite hacer zoom y guardar la imagen.

### Carga de datos: `cargar_ruta(ruta)`

Esta función es el punto de entrada de los datos. Llama a `analitica.cargar_csv`, y si ocurre un error muestra un cuadro de mensaje en lugar de cerrar el programa. Si todo sale bien, guarda los datos, llena los filtros con los valores reales del archivo, genera el informe una sola vez y actualiza el tablero.

### Textos con formato: `_escribir` y `_texto`

Los informes y las definiciones se muestran en un `Text` de Tkinter, que permite estilos como título o negrita. Se usan **etiquetas de texto** (`tag_configure`) para definir cada estilo, y `_escribir` inserta fragmentos con su etiqueta. El widget se pone en modo de solo lectura para que el usuario no pueda editarlo.

### Funciones de formato

Funciones como `fmt_q`, `fmt_var` y `fmt_pct` convierten números en texto legible: `Q1,651,941`, `▲ +0.8 %`, `32.8 %`. Así el formato está en un solo lugar y no se repite en cada pestaña.

---

## 5. Flujo completo de un clic

Ejemplo: el usuario elige "Pinturas" en la lista de categorías.

1. Tkinter detecta el evento `<<ComboboxSelected>>`.
2. Se ejecuta el `lambda`, que llama a `actualizar()`.
3. `actualizar()` lee `self.var_categoria.get()` → `"Pinturas"`.
4. `analitica.filtrar` devuelve solo las filas de pinturas.
5. Los cálculos generan nuevos KPI, serie, atípicos y proyección.
6. Cada pestaña se redibuja con los nuevos datos.
7. El informe no cambia, porque se generó antes con todos los datos.

---

## 6. Conceptos de programación usados

| Concepto | Dónde aparece | Para qué sirve |
|---|---|---|
| Funciones | Todo el proyecto | Dividir el trabajo en pasos con nombre |
| Clases y herencia | `DataVisionApp(tk.Tk)` | Agrupar la ventana y su estado |
| Máscaras booleanas | `cargar_csv` | Marcar filas que no cumplen reglas |
| `groupby` y `reindex` | `ingresos_mensuales`, `barras_categoria` | Agrupar y completar datos |
| Excepciones | `ErrorDatos`, `try/except` | Manejar archivos inválidos sin cerrar el programa |
| Eventos | `bind`, `command` | Reaccionar a clics y selecciones |
| Diccionarios | `self.tarjetas` | Acceder a widgets por nombre |
| Separación de responsabilidades | Tres archivos | Facilitar cambios y pruebas |

---

## 7. Dónde modificar cada cosa

- **Cambiar una regla de cálculo** (por ejemplo, el umbral de atípicos): `analitica.py`, constantes al inicio.
- **Cambiar colores o tipografía:** `datavision.py`, constantes `COLOR_*` y `FUENTE` al inicio.
- **Cambiar el tipo o estilo de una gráfica:** `graficas.py`.
- **Agregar una pestaña nueva:** crear un método `_construir_...` en `datavision.py`, añadirlo con `self.nb.add(...)` y llamar a una función `_llenar_...` desde `actualizar()`.
- **Cambiar la fuente de datos** (por ejemplo, MySQL): solo `analitica.cargar_csv`, manteniendo las mismas columnas y reglas de calidad.
