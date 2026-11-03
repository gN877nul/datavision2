"""Dibujo de las gráficas de DataVision con matplotlib (sin Tkinter)."""

import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

COLOR_PRIMARIO = "#1d4ed8"
COLOR_ATIPICO = "#b3261e"
COLOR_PROYECCION = "#6b7280"
COLOR_ANTERIOR = "#9ca3af"
COLORES_CANAL = ["#1d4ed8", "#16a34a", "#f59e0b"]
COLOR_SUBE = "#1e7b34"
COLOR_BAJA = "#b3261e"

_formato_miles = FuncFormatter(lambda v, _: f"Q{v / 1000:,.0f} mil")


def _sin_datos(ax, mensaje="Sin datos para esta selección"):
    ax.text(0.5, 0.5, mensaje, ha="center", va="center",
            transform=ax.transAxes, color="#6b7280")
    ax.set_axis_off()


def dibujar_lineas(ax, serie, atip, proy):
    """RF-03 + RF-10 + RF-11: ingresos mensuales, atípicos y proyección punteada."""
    if serie.sum() == 0:
        return _sin_datos(ax)

    y = serie.to_numpy(dtype=float)
    x = np.arange(len(y))
    ax.plot(x, y, marker="o", ms=4, color=COLOR_PRIMARIO, label="Ingresos reales")

    mascara = atip["atipico"].to_numpy()
    if mascara.any():
        ax.scatter(x[mascara], y[mascara], color=COLOR_ATIPICO, s=70,
                   zorder=5, label="Mes atípico (|z| > 2)")

    etiquetas = list(serie.index)
    if proy:
        xp = np.arange(len(y), len(y) + len(proy))
        yp = [v for _, v in proy]
        ax.plot([x[-1], *xp], [y[-1], *yp], linestyle="--", marker="o", ms=4,
                color=COLOR_PROYECCION, label="Proyección (estimación)")
        etiquetas += [p for p, _ in proy]

    ax.set_xticks(np.arange(len(etiquetas)))
    ax.set_xticklabels(etiquetas, rotation=45, ha="right", fontsize=7)
    ax.yaxis.set_major_formatter(_formato_miles)
    ax.set_ylim(bottom=0)
    ax.set_title("Evolución mensual de ingresos", fontsize=11)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")


def dibujar_barras_categoria(ax, tabla, anio_ant, anio_act):
    """RF-04: ingresos por categoría en ene–oct de cada año, con variación."""
    if tabla.empty or tabla[["anterior", "actual"]].to_numpy().sum() == 0:
        return _sin_datos(ax)

    categorias = list(tabla.index)
    x = np.arange(len(categorias))
    ancho = 0.38
    ax.bar(x - ancho / 2, tabla["anterior"], ancho, color=COLOR_ANTERIOR,
           label=f"ene–oct {anio_ant}")
    ax.bar(x + ancho / 2, tabla["actual"], ancho, color=COLOR_PRIMARIO,
           label=f"ene–oct {anio_act}")

    for i, (_, fila) in enumerate(tabla.iterrows()):
        var = fila["variacion"]
        if var is None or pd.isna(var):
            continue
        color = COLOR_SUBE if var >= 0 else COLOR_BAJA
        ax.text(x[i] + ancho / 2, max(fila["anterior"], fila["actual"]),
                f"{var:+.1f}%", ha="center", va="bottom", fontsize=8,
                color=color, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(categorias, rotation=15, ha="right", fontsize=8)
    ax.yaxis.set_major_formatter(_formato_miles)
    ax.margins(y=0.25)
    ax.set_title("Ingresos por categoría: comparación ene–oct", fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8, loc="upper center", ncol=2)


def dibujar_distribucion_canal(ax, distribucion):
    """RF-05: participación de cada canal en el total (suma 100 %)."""
    if distribucion.empty:
        return _sin_datos(ax)

    ax.pie(distribucion["ingresos"], labels=distribucion["canal"],
           autopct="%1.1f%%", startangle=90,
           colors=COLORES_CANAL[: len(distribucion)],
           wedgeprops={"width": 0.45}, textprops={"fontsize": 8})
    ax.set_title("Participación por canal de venta", fontsize=11)
    ax.axis("equal")
