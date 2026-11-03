"""Cálculos de DataVision, sin interfaz gráfica.

Cada función se relaciona con un requerimiento del documento de análisis
(RF = requerimiento funcional, RN = regla de negocio).
"""

from collections import Counter

import numpy as np
import pandas as pd

COLUMNAS = [
    "id", "periodo", "anio", "mes", "producto", "categoria",
    "canal", "unidades", "precio_unit", "costo_unit",
]
TODAS_CATEGORIAS = "Todas las categorías"  # RN-04
TODOS_CANALES = "Todos los canales"        # RN-04
MESES_COMPARACION = 10                     # RN-01: ene–oct
UMBRAL_ATIPICO = 2.0                       # RN-02: |z| > 2
MESES_PROYECCION = 3                       # RN-03
MESES_HISTORIA_PROYECCION = 12             # RN-03
MINIMO_REGISTROS = 20                      # RF-01


class ErrorDatos(Exception):
    """Se lanza cuando el archivo no puede usarse."""


# ---------------------------------------------------------------- RF-01 carga
def cargar_csv(ruta):
    """Lee el CSV, aplica las reglas de calidad y calcula ingresos y margen.

    Devuelve (df_valido, resumen). Los registros que no cumplen las reglas
    se descartan y se reportan en resumen["motivos"].
    """
    try:
        df = pd.read_csv(ruta)
    except Exception as e:  # noqa: BLE001
        raise ErrorDatos(f"No se pudo leer el archivo: {e}") from e

    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ErrorDatos("Faltan columnas en el archivo: " + ", ".join(faltan))

    df = df[COLUMNAS].copy()
    total = len(df)

    for c in ["anio", "mes", "unidades", "precio_unit", "costo_unit"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["periodo", "producto", "categoria", "canal"]:
        df[c] = df[c].where(df[c].notna(), "").astype(str).str.strip()

    anio_i = df["anio"].fillna(0).astype(int)
    mes_i = df["mes"].fillna(0).astype(int)
    periodo_esperado = anio_i.astype(str).str.zfill(4) + "-" + mes_i.astype(str).str.zfill(2)

    # Reglas de calidad de datos (sección "Reglas de Calidad de Datos")
    reglas = [
        (
            df[["periodo", "anio", "mes", "producto", "categoria", "canal",
                "unidades", "precio_unit", "costo_unit"]].isna().any(axis=1)
            | (df[["periodo", "producto", "categoria", "canal"]] == "").any(axis=1),
            "Campo obligatorio vacío",
        ),
        (
            ~(df["unidades"] > 0) | ~(df["precio_unit"] > 0) | ~(df["costo_unit"] > 0),
            "Unidades, precio o costo no mayores que cero",
        ),
        (
            ~(df["costo_unit"] < df["precio_unit"]),
            "Costo no menor que el precio (margen no positivo)",
        ),
        (
            (df["periodo"] != periodo_esperado) | (~mes_i.between(1, 12)),
            "El periodo no coincide con el año y el mes",
        ),
    ]

    invalido = pd.Series(False, index=df.index)
    motivos = Counter()
    for mascara, motivo in reglas:
        nuevos = mascara & ~invalido
        if nuevos.any():
            motivos[motivo] = int(nuevos.sum())
        invalido = invalido | mascara

    valido = df[~invalido].copy()
    valido["anio"] = valido["anio"].astype(int)
    valido["mes"] = valido["mes"].astype(int)
    valido["unidades"] = valido["unidades"].astype(int)
    valido["ingresos"] = valido["unidades"] * valido["precio_unit"]
    valido["margen"] = valido["unidades"] * (valido["precio_unit"] - valido["costo_unit"])
    valido = valido.sort_values(["periodo", "producto", "canal"]).reset_index(drop=True)

    resumen = {
        "total": total,
        "usados": len(valido),
        "descartados": total - len(valido),
        "motivos": dict(motivos),
    }
    return valido, resumen


def anios_de(df):
    """Devuelve (año actual, año anterior) a partir de los datos cargados."""
    actual = int(df["anio"].max())
    return actual, actual - 1


def periodos_de(df):
    """Lista de todos los meses entre el primero y el último periodo (AAAA-MM)."""
    inicio = pd.Period(df["periodo"].min(), freq="M")
    fin = pd.Period(df["periodo"].max(), freq="M")
    return [str(p) for p in pd.period_range(inicio, fin, freq="M")]


def valores_categorias(df):
    return sorted(df["categoria"].unique())


def valores_canales(df):
    return sorted(df["canal"].unique())


# ------------------------------------------------------------ RF-06 filtros
def filtrar(df, categoria=TODAS_CATEGORIAS, canal=TODOS_CANALES):
    if categoria and categoria != TODAS_CATEGORIAS:
        df = df[df["categoria"] == categoria]
    if canal and canal != TODOS_CANALES:
        df = df[df["canal"] == canal]
    return df


# -------------------------------------------------------------- RF-02 KPI
def variacion(actual, anterior):
    """Variación porcentual; None si no se puede calcular."""
    if actual is None or anterior is None or pd.isna(actual) or pd.isna(anterior):
        return None
    if anterior == 0:
        return None
    return (actual / anterior - 1) * 100


def kpis(df):
    ingresos = float(df["ingresos"].sum())
    unidades = int(df["unidades"].sum())
    margen = float(df["margen"].sum())
    return {
        "ingresos": ingresos,
        "unidades": unidades,
        "margen": margen,
        "margen_pct": margen / ingresos * 100 if ingresos else None,
        "precio_prom": ingresos / unidades if unidades else None,
    }


def _ene_oct(df, anio):
    """RN-01: solo enero a octubre de cada año."""
    return df[(df["anio"] == anio) & (df["mes"] <= MESES_COMPARACION)]


def comparar_kpis(df, anio_act, anio_ant):
    """KPI totales y su variación ene–oct del año actual contra el anterior (RF-09)."""
    total = kpis(df)
    act = kpis(_ene_oct(df, anio_act))
    ant = kpis(_ene_oct(df, anio_ant))

    margen_pp = None
    if act["margen_pct"] is not None and ant["margen_pct"] is not None:
        margen_pp = act["margen_pct"] - ant["margen_pct"]

    return {
        "total": total,
        "actual": act,
        "anterior": ant,
        "crecimiento_interanual": variacion(act["ingresos"], ant["ingresos"]),
        "ingresos_var": variacion(act["ingresos"], ant["ingresos"]),
        "unidades_var": variacion(act["unidades"], ant["unidades"]),
        "precio_var": variacion(act["precio_prom"], ant["precio_prom"]),
        "margen_pp": margen_pp,
    }


# ---------------------------------------------------- RF-03 serie mensual
def ingresos_mensuales(df, periodos):
    """Serie de ingresos por mes; los meses sin ventas valen 0."""
    serie = df.groupby("periodo")["ingresos"].sum()
    return serie.reindex(periodos, fill_value=0.0).astype(float)


# ---------------------------------------------------- RF-10 atípicos
def atipicos(serie):
    """RN-02: z = (ingreso del mes − promedio) ÷ desviación estándar de la selección."""
    valores = serie.to_numpy(dtype=float)
    z = np.zeros_like(valores)
    if len(valores) >= 3:
        sd = valores.std(ddof=1)
        if sd > 0:
            z = (valores - valores.mean()) / sd
    return pd.DataFrame({
        "periodo": serie.index,
        "ingresos": valores,
        "z": z,
        "atipico": np.abs(z) > UMBRAL_ATIPICO,
    })


# ---------------------------------------------------- RF-11 proyección
def siguientes_periodos(ultimo, n):
    base = pd.Period(ultimo, freq="M")
    return [str(base + i) for i in range(1, n + 1)]


def proyeccion(serie):
    """RN-03: recta de mínimos cuadrados sobre los últimos 12 meses, extendida 3 meses.

    Devuelve una lista de (periodo, valor estimado). Es una estimación, no un dato real.
    """
    if len(serie) < 2:
        return []
    y = serie.to_numpy(dtype=float)[-MESES_HISTORIA_PROYECCION:]
    x = np.arange(len(y))
    pendiente, intercepto = np.polyfit(x, y, 1)
    x_futuro = np.arange(len(y), len(y) + MESES_PROYECCION)
    valores = np.maximum(pendiente * x_futuro + intercepto, 0.0)
    periodos = siguientes_periodos(serie.index[-1], MESES_PROYECCION)
    return list(zip(periodos, valores.tolist()))


# ---------------------------------------- RF-04 y RF-09: categorías
def barras_categoria(df, anio_act, anio_ant):
    """Ingresos ene–oct por categoría en ambos años y su variación."""
    columnas = ["anterior", "actual", "variacion"]
    ej = df[(df["mes"] <= MESES_COMPARACION) & df["anio"].isin([anio_ant, anio_act])]
    if ej.empty:
        return pd.DataFrame(columns=columnas)

    tabla = ej.groupby(["categoria", "anio"])["ingresos"].sum().unstack("anio")
    tabla = tabla.reindex(columns=[anio_ant, anio_act], fill_value=0.0).fillna(0.0)
    tabla.columns = columnas[:2]
    tabla["variacion"] = [variacion(a, b) for a, b in zip(tabla["actual"], tabla["anterior"])]
    return tabla


# ---------------------------------------- RF-05: distribución
def distribucion(df, campo):
    """Participación de cada valor de `campo` en los ingresos totales (suma 100 %)."""
    total = df["ingresos"].sum()
    if total == 0:
        return pd.DataFrame(columns=[campo, "ingresos", "participacion"])
    grupos = df.groupby(campo)["ingresos"].sum().sort_values(ascending=False)
    return pd.DataFrame({
        campo: grupos.index,
        "ingresos": grupos.values,
        "participacion": grupos.values / total * 100,
    })


# ---------------------------------------- RF-08: tabla de productos
def tabla_productos(df, anio_act, anio_ant):
    columnas = ["producto", "categoria", "ingresos", "variacion", "margen_pct"]
    if df.empty:
        return pd.DataFrame(columns=columnas)

    g = df.groupby(["producto", "categoria"]).agg(
        ingresos=("ingresos", "sum"), margen=("margen", "sum")
    ).reset_index()
    g["margen_pct"] = g["margen"] / g["ingresos"] * 100

    ej = _ene_oct(df, anio_act)
    ea = _ene_oct(df, anio_ant)
    act = ej.groupby("producto")["ingresos"].sum()
    ant = ea.groupby("producto")["ingresos"].sum()
    g["variacion"] = [
        variacion(act.get(p, 0.0), ant.get(p, 0.0)) for p in g["producto"]
    ]
    return g.sort_values("ingresos", ascending=False)[columnas].reset_index(drop=True)


# ---------------------------------------- RF-12: informe (usa todos los datos, RN-06)
def generar_informe(df, anio_act, anio_ant):
    """Devuelve dos hallazgos y una recomendación con cifras calculadas."""
    comp = comparar_kpis(df, anio_act, anio_ant)
    cat = barras_categoria(df, anio_act, anio_ant).dropna(subset=["variacion"])
    if cat.empty:
        return {
            "hallazgos": ["No hay datos de ambos años para comparar categorías."],
            "recomendacion": "Carga datos de ambos años para generar la recomendación.",
        }

    cat_crece = cat["variacion"].idxmax()
    cat_margen = (
        df.groupby("categoria")[["ingresos", "margen"]].sum()
        .assign(margen_pct=lambda t: t["margen"] / t["ingresos"] * 100)
    )
    cat_margen_bajo = cat_margen["margen_pct"].idxmin()
    margen_bajo = cat_margen.loc[cat_margen_bajo]
    participacion_bajo = margen_bajo["ingresos"] / df["ingresos"].sum() * 100

    total_var = comp["crecimiento_interanual"]
    temporada = df[df["mes"].between(3, 7)]["ingresos"].sum() / df["ingresos"].sum() * 100

    hallazgo_1 = (
        f"Los ingresos de ene–oct {anio_act} {'crecieron' if total_var and total_var >= 0 else 'bajaron'} "
        f"{abs(total_var):.1f} % frente a ene–oct {anio_ant}. La categoría que más creció fue "
        f"{cat_crece}, con {cat.loc[cat_crece, 'variacion']:+.1f} % "
        f"(de Q{cat.loc[cat_crece, 'anterior']:,.0f} a Q{cat.loc[cat_crece, 'actual']:,.0f})."
    )
    hallazgo_2 = (
        f"{cat_margen_bajo} tiene el margen bruto más bajo del negocio: {margen_bajo['margen_pct']:.1f} %, "
        f"frente a {comp['total']['margen_pct']:.1f} % del total. Aun así representa "
        f"{participacion_bajo:.1f} % de los ingresos, por lo que cada venta deja menos ganancia."
    )
    recomendacion = (
        f"Revisar costos y precios de {cat_margen_bajo} antes de la temporada alta de marzo a julio, "
        f"que concentra {temporada:.1f} % de los ingresos. Mantener inventario suficiente de "
        f"{cat_crece}, la categoría con mayor crecimiento."
    )
    return {"hallazgos": [hallazgo_1, hallazgo_2], "recomendacion": recomendacion}
