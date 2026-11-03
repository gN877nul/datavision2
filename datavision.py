"""DataVision (beta): tablero de inteligencia de negocios para una ferretería.

Uso:
    python datavision.py                 (carga ventas_ferreteria.csv si está en la misma carpeta)
    python datavision.py ruta/archivo.csv

Requiere: pandas, numpy, matplotlib (Tkinter viene con Python en Windows y macOS).
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

import analitica as an
import graficas as g

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_DEFECTO = os.path.join(CARPETA, "ventas_ferreteria.csv")

FUENTE = "Arial"
COLOR_FONDO = "#f3f4f6"
COLOR_TARJETA = "#ffffff"
COLOR_BORDE = "#d1d5db"
COLOR_TEXTO = "#1f2937"
COLOR_NOTA = "#6b7280"
COLOR_SUBE = "#1e7b34"
COLOR_BAJA = "#b3261e"
COLOR_ATIPICO_FONDO = "#fde2e1"

MESES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
         7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}

# RF-13: definiciones visibles en la aplicación (tabla 6 y reglas de negocio)
DEFINICIONES_KPI = [
    ("Ingresos por ventas", "Σ (unidades × precio_unit)", "Mide el tamaño del negocio en quetzales."),
    ("Crecimiento interanual", "Ingresos ene–oct año actual ÷ ingresos ene–oct año anterior − 1",
     "Indica si el negocio crece, comparando los mismos meses."),
    ("Margen bruto %", "Σ unidades × (precio − costo) ÷ ingresos",
     "Muestra cuánto de cada quetzal vendido queda como ganancia bruta."),
    ("Unidades vendidas", "Σ unidades", "Mide el volumen físico vendido."),
    ("Precio promedio por unidad", "Ingresos ÷ unidades", "Refleja cambios de precio y de mezcla de productos."),
]
REGLAS_NEGOCIO = [
    ("RN-01", "La comparación entre periodos usa los mismos meses de cada año (enero a octubre)."),
    ("RN-02", "Un mes es atípico si |z| > 2, donde z = (ingresos del mes − promedio) ÷ desviación estándar de la selección."),
    ("RN-03", "La proyección es una recta de mínimos cuadrados ajustada a los últimos 12 meses y extendida 3 meses. Es una estimación, no un dato real."),
    ("RN-04", "Los filtros “Todas las categorías” y “Todos los canales” suman todos los registros."),
    ("RN-05", "Una variación positiva se muestra en verde con signo +; una negativa, en rojo con signo −."),
    ("RN-06", "El informe de hallazgos se calcula con todos los datos y no cambia con los filtros."),
]


# ------------------------------------------------------------ formato
def vacio(valor):
    return valor is None or (not isinstance(valor, str) and pd.isna(valor))


def fmt_q(valor):
    return "—" if vacio(valor) else f"Q{valor:,.0f}"


def fmt_var(valor):
    """Variación con signo y flecha (RNF-07: no depende solo del color)."""
    if vacio(valor):
        return "—"
    flecha = "▲" if valor > 0 else "▼" if valor < 0 else "■"
    return f"{flecha} {valor:+.1f} %"


def fmt_pp(valor):
    if vacio(valor):
        return "—"
    flecha = "▲" if valor > 0 else "▼" if valor < 0 else "■"
    return f"{flecha} {valor:+.1f} pp"


def fmt_pct(valor):
    return "—" if vacio(valor) else f"{valor:.1f} %"


def color_var(valor):
    if vacio(valor) or valor == 0:
        return COLOR_NOTA
    return COLOR_SUBE if valor > 0 else COLOR_BAJA


def nombre_mes(periodo):
    anio, mes = periodo.split("-")
    return f"{MESES[int(mes)]} {anio}"


# ------------------------------------------------------------ aplicación
class DataVisionApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DataVision · Beta")
        self.geometry("1220x820")
        self.minsize(1000, 680)
        self.configure(bg=COLOR_FONDO)

        self.df_full = None
        self.resumen_carga = None
        self.anio_act = None
        self.anio_ant = None
        self.periodos = []
        self.df_sel = None
        self.serie = None
        self.atip = None
        self.proy = []
        self.informe = None

        self.var_categoria = tk.StringVar(value=an.TODAS_CATEGORIAS)
        self.var_canal = tk.StringVar(value=an.TODOS_CANALES)

        self._estilos()
        self._construir_encabezado()
        self._construir_pestanas()
        self._construir_barra_estado()

        if os.path.exists(ARCHIVO_DEFECTO):
            self.cargar_ruta(ARCHIVO_DEFECTO)
        elif len(sys.argv) > 1:
            self.cargar_ruta(sys.argv[1])
        else:
            self.estado.config(text="Carga un archivo CSV de ventas para comenzar (botón “Cargar CSV”).")

    # ----- estilos y estructura
    def _estilos(self):
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("Treeview", font=(FUENTE, 10), rowheight=24)
        estilo.configure("Treeview.Heading", font=(FUENTE, 10, "bold"))
        estilo.configure("TNotebook.Tab", font=(FUENTE, 10, "bold"), padding=(12, 6))

    def _construir_encabezado(self):
        marco = tk.Frame(self, bg=COLOR_FONDO)
        marco.pack(fill="x", padx=16, pady=(12, 6))

        titulo = tk.Frame(marco, bg=COLOR_FONDO)
        titulo.pack(side="left")
        tk.Label(titulo, text="DataVision", font=(FUENTE, 18, "bold"),
                 bg=COLOR_FONDO, fg=COLOR_TEXTO).pack(anchor="w")
        tk.Label(titulo, text="Inteligencia de negocios · Ferretería",
                 font=(FUENTE, 9), bg=COLOR_FONDO, fg=COLOR_NOTA).pack(anchor="w")

        controles = tk.Frame(marco, bg=COLOR_FONDO)
        controles.pack(side="right")

        ttk.Button(controles, text="Cargar CSV…", command=self.abrir_archivo).grid(row=0, column=0, padx=4)
        tk.Label(controles, text="Categoría", bg=COLOR_FONDO, fg=COLOR_TEXTO,
                 font=(FUENTE, 9)).grid(row=0, column=1, padx=(14, 4))
        self.combo_categoria = ttk.Combobox(controles, textvariable=self.var_categoria,
                                            state="readonly", width=20)
        self.combo_categoria.grid(row=0, column=2)
        self.combo_categoria.bind("<<ComboboxSelected>>", lambda e: self.actualizar())

        tk.Label(controles, text="Canal", bg=COLOR_FONDO, fg=COLOR_TEXTO,
                 font=(FUENTE, 9)).grid(row=0, column=3, padx=(14, 4))
        self.combo_canal = ttk.Combobox(controles, textvariable=self.var_canal,
                                        state="readonly", width=16)
        self.combo_canal.grid(row=0, column=4)
        self.combo_canal.bind("<<ComboboxSelected>>", lambda e: self.actualizar())

        ttk.Button(controles, text="Restablecer filtros", command=self.restablecer).grid(
            row=0, column=5, padx=(14, 0))

    def _construir_pestanas(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=6)

        self.tab_resumen = ttk.Frame(self.nb, padding=12)
        self.tab_graficas = ttk.Frame(self.nb, padding=8)
        self.tab_productos = ttk.Frame(self.nb, padding=12)
        self.tab_atipicos = ttk.Frame(self.nb, padding=12)
        self.tab_informe = ttk.Frame(self.nb, padding=12)
        self.tab_definiciones = ttk.Frame(self.nb, padding=12)
        self.tab_datos = ttk.Frame(self.nb, padding=12)

        self.nb.add(self.tab_resumen, text="Resumen")
        self.nb.add(self.tab_graficas, text="Gráficas")
        self.nb.add(self.tab_productos, text="Productos")
        self.nb.add(self.tab_atipicos, text="Atípicos y proyección")
        self.nb.add(self.tab_informe, text="Informe")
        self.nb.add(self.tab_definiciones, text="Definiciones")
        self.nb.add(self.tab_datos, text="Datos")

        self._construir_resumen()
        self._construir_graficas()
        self._construir_productos()
        self._construir_atipicos()
        self._construir_informe()
        self._construir_definiciones()
        self._construir_datos()

    def _construir_barra_estado(self):
        self.estado = tk.Label(self, text="", anchor="w", bg="#e5e7eb", fg=COLOR_TEXTO,
                               font=(FUENTE, 9), padx=10, pady=4)
        self.estado.pack(fill="x", side="bottom")

    # ----- utilidades de tablas y tarjetas
    def _tabla(self, padre, columnas, titulos, anchos, alinear_derecha=()):
        cont = ttk.Frame(padre)
        tv = ttk.Treeview(cont, columns=columnas, show="headings", selectmode="browse")
        for col, titulo, ancho in zip(columnas, titulos, anchos):
            tv.heading(col, text=titulo)
            tv.column(col, width=ancho, minwidth=60,
                      anchor="e" if col in alinear_derecha else "w", stretch=True)
        sb = ttk.Scrollbar(cont, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tv.tag_configure("sube", foreground=COLOR_SUBE)
        tv.tag_configure("baja", foreground=COLOR_BAJA)
        tv.tag_configure("atipico", background=COLOR_ATIPICO_FONDO)
        return cont, tv

    def _tarjeta(self, padre, titulo, nota):
        marco = tk.Frame(padre, bg=COLOR_TARJETA, highlightbackground=COLOR_BORDE,
                         highlightthickness=1, padx=14, pady=12)
        tk.Label(marco, text=titulo, bg=COLOR_TARJETA, fg="#374151",
                 font=(FUENTE, 10, "bold")).pack(anchor="w")
        valor = tk.Label(marco, text="—", bg=COLOR_TARJETA, fg=COLOR_TEXTO,
                         font=(FUENTE, 20, "bold"))
        valor.pack(anchor="w", pady=(4, 0))
        variacion = tk.Label(marco, text="", bg=COLOR_TARJETA, fg=COLOR_NOTA,
                             font=(FUENTE, 10, "bold"), wraplength=210, justify="left")
        variacion.pack(anchor="w")
        tk.Label(marco, text=nota, bg=COLOR_TARJETA, fg=COLOR_NOTA, font=(FUENTE, 8),
                 wraplength=210, justify="left").pack(anchor="w", pady=(8, 0))
        return marco, valor, variacion

    # ----- pestaña Resumen (RF-02, RF-09, RNF-05)
    def _construir_resumen(self):
        fila = tk.Frame(self.tab_resumen, bg=COLOR_FONDO)
        fila.pack(fill="x")
        self.tarjetas = {}
        definiciones = [
            ("ingresos", "Ingresos totales", "Σ unidades × precio. Todos los meses del filtro."),
            ("crecimiento", "Crecimiento interanual", "Ingresos ene–oct del año actual ÷ año anterior − 1."),
            ("margen", "Margen bruto %", "Σ unidades × (precio − costo) ÷ ingresos."),
            ("unidades", "Unidades vendidas", "Σ unidades. Variación ene–oct vs. año anterior."),
            ("precio", "Precio promedio", "Ingresos ÷ unidades. Variación ene–oct vs. año anterior."),
        ]
        for i, (clave, titulo, nota) in enumerate(definiciones):
            marco, valor, variacion = self._tarjeta(fila, titulo, nota)
            marco.grid(row=0, column=i, sticky="nsew", padx=5)
            fila.columnconfigure(i, weight=1, uniform="tarjetas")
            self.tarjetas[clave] = (valor, variacion)

        self.lbl_comparacion = tk.Label(self.tab_resumen, text="", bg=COLOR_FONDO,
                                        fg=COLOR_TEXTO, font=(FUENTE, 10), justify="left")
        self.lbl_comparacion.pack(anchor="w", pady=(16, 4))
        tk.Label(self.tab_resumen,
                 text="Las variaciones comparan enero a octubre de cada año (RN-01). "
                      "pp = puntos porcentuales. Verde sube, rojo baja (RN-05).",
                 bg=COLOR_FONDO, fg=COLOR_NOTA, font=(FUENTE, 9)).pack(anchor="w")

    # ----- pestaña Gráficas (RF-03, RF-04, RF-05, RF-10, RF-11)
    def _construir_graficas(self):
        self.fig = Figure(figsize=(10, 7), dpi=100)
        self.canvas_fig = FigureCanvasTkAgg(self.fig, master=self.tab_graficas)
        barra = NavigationToolbar2Tk(self.canvas_fig, self.tab_graficas, pack_toolbar=False)
        barra.update()
        barra.pack(side="top", fill="x")
        self.canvas_fig.get_tk_widget().pack(fill="both", expand=True)
        tk.Label(self.tab_graficas,
                 text="Línea punteada = proyección lineal (estimación, no dato real). "
                      "Puntos rojos = meses atípicos con |z| > 2.",
                 bg=COLOR_FONDO, fg=COLOR_NOTA, font=(FUENTE, 9)).pack(anchor="w", pady=(4, 0))

    # ----- pestaña Productos (RF-08)
    def _construir_productos(self):
        self.lbl_productos = tk.Label(self.tab_productos, text="", bg=COLOR_FONDO,
                                      fg=COLOR_TEXTO, font=(FUENTE, 10))
        self.lbl_productos.pack(anchor="w", pady=(0, 8))
        cont, self.tv_productos = self._tabla(
            self.tab_productos,
            columnas=("producto", "categoria", "ingresos", "variacion", "margen"),
            titulos=("Producto", "Categoría", "Ingresos", "Var. ene–oct", "Margen %"),
            anchos=(280, 150, 130, 140, 110),
            alinear_derecha=("ingresos", "variacion", "margen"),
        )
        cont.pack(fill="both", expand=True)

    # ----- pestaña Atípicos y proyección (RF-10, RF-11)
    def _construir_atipicos(self):
        self.lbl_atipicos = tk.Label(self.tab_atipicos, text="", bg=COLOR_FONDO,
                                     fg=COLOR_TEXTO, font=(FUENTE, 11, "bold"))
        self.lbl_atipicos.pack(anchor="w", pady=(0, 6))

        cont, self.tv_atipicos = self._tabla(
            self.tab_atipicos,
            columnas=("periodo", "ingresos", "z", "estado"),
            titulos=("Mes", "Ingresos", "Puntaje z", "Estado"),
            anchos=(160, 160, 120, 200),
            alinear_derecha=("ingresos", "z"),
        )
        cont.pack(fill="both", expand=True)

        tk.Label(self.tab_atipicos, text="Proyección de ingresos de los próximos 3 meses (estimación)",
                 bg=COLOR_FONDO, fg=COLOR_TEXTO, font=(FUENTE, 11, "bold")).pack(anchor="w", pady=(14, 6))
        cont2, self.tv_proy = self._tabla(
            self.tab_atipicos,
            columnas=("periodo", "estimado", "nota"),
            titulos=("Mes", "Ingreso estimado", "Tipo"),
            anchos=(160, 160, 320),
            alinear_derecha=("estimado",),
        )
        cont2.pack(fill="x")
        self.tv_proy.configure(height=3)

    # ----- pestaña Informe (RF-12, RN-06)
    def _construir_informe(self):
        self.txt_informe = self._texto(self.tab_informe)

    # ----- pestaña Definiciones (RF-13)
    def _construir_definiciones(self):
        self.txt_definiciones = self._texto(self.tab_definiciones)

    def _texto(self, padre):
        marco = ttk.Frame(padre)
        marco.pack(fill="both", expand=True)
        txt = tk.Text(marco, wrap="word", font=(FUENTE, 11), bg=COLOR_TARJETA,
                      relief="flat", padx=18, pady=14, state="disabled")
        sb = ttk.Scrollbar(marco, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.tag_configure("titulo", font=(FUENTE, 13, "bold"), spacing1=10, spacing3=4)
        txt.tag_configure("negrita", font=(FUENTE, 11, "bold"))
        txt.tag_configure("nota", foreground=COLOR_NOTA, font=(FUENTE, 9))
        return txt

    def _escribir(self, txt, fragmentos):
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        for texto, etiqueta in fragmentos:
            txt.insert("end", texto, etiqueta)
        txt.configure(state="disabled")

    # ----- pestaña Datos (RF-01, reglas de calidad)
    def _construir_datos(self):
        self.lbl_datos = tk.Label(self.tab_datos, text="", bg=COLOR_FONDO, fg=COLOR_TEXTO,
                                  font=(FUENTE, 10), justify="left")
        self.lbl_datos.pack(anchor="w", pady=(0, 10))
        cont, self.tv_datos = self._tabla(
            self.tab_datos,
            columnas=("id", "periodo", "producto", "categoria", "canal", "unidades", "precio", "costo"),
            titulos=("ID", "Periodo", "Producto", "Categoría", "Canal", "Unidades", "Precio (Q)", "Costo (Q)"),
            anchos=(60, 90, 230, 130, 120, 90, 100, 100),
            alinear_derecha=("id", "unidades", "precio", "costo"),
        )
        cont.pack(fill="both", expand=True)

    # ----- carga de datos (RF-01)
    def abrir_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona el archivo de ventas",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if ruta:
            self.cargar_ruta(ruta)

    def cargar_ruta(self, ruta):
        try:
            df, resumen = an.cargar_csv(ruta)
        except an.ErrorDatos as e:
            messagebox.showerror("No se pudo cargar el archivo", str(e))
            return

        if resumen["usados"] < an.MINIMO_REGISTROS:
            messagebox.showwarning(
                "Pocos registros",
                f"Se usaron {resumen['usados']} registros. El prototipo requiere al menos "
                f"{an.MINIMO_REGISTROS} (RF-01).",
            )
        if resumen["usados"] == 0:
            return

        self.df_full = df
        self.resumen_carga = resumen
        self.ruta = ruta
        self.anio_act, self.anio_ant = an.anios_de(df)
        self.periodos = an.periodos_de(df)

        self.combo_categoria["values"] = [an.TODAS_CATEGORIAS] + an.valores_categorias(df)
        self.combo_canal["values"] = [an.TODOS_CANALES] + an.valores_canales(df)
        self.var_categoria.set(an.TODAS_CATEGORIAS)
        self.var_canal.set(an.TODOS_CANALES)

        # RN-06: el informe se calcula una vez con todos los datos
        self.informe = an.generar_informe(df, self.anio_act, self.anio_ant)
        self._llenar_informe()
        self._llenar_definiciones()
        self._llenar_datos()
        self.actualizar()

    def restablecer(self):
        """RF-07: vuelve a la vista general."""
        self.var_categoria.set(an.TODAS_CATEGORIAS)
        self.var_canal.set(an.TODOS_CANALES)
        self.actualizar()

    # ----- actualización del tablero (RF-06)
    def actualizar(self):
        if self.df_full is None:
            return

        df = an.filtrar(self.df_full, self.var_categoria.get(), self.var_canal.get())
        self.df_sel = df
        self.serie = an.ingresos_mensuales(df, self.periodos)
        self.atip = an.atipicos(self.serie)
        self.proy = an.proyeccion(self.serie)

        self._actualizar_resumen(df)
        self._dibujar_graficas(df)
        self._llenar_productos(df)
        self._llenar_atipicos()

        filtros = f"Categoría: {self.var_categoria.get()} · Canal: {self.var_canal.get()}"
        usados = self.resumen_carga["usados"]
        self.estado.config(
            text=f"Registros usados: {usados} de {self.resumen_carga['total']}  ·  "
                 f"Filtros → {filtros}  ·  Fuente: {os.path.basename(self.ruta)}"
        )

    def _actualizar_resumen(self, df):
        c = an.comparar_kpis(df, self.anio_act, self.anio_ant)
        t = c["total"]

        valor, var = self.tarjetas["ingresos"]
        valor.config(text=fmt_q(t["ingresos"]))
        var.config(text=f"{len(df)} registros en la selección", fg=COLOR_NOTA)

        valor, var = self.tarjetas["crecimiento"]
        valor.config(text=fmt_var(c["crecimiento_interanual"]),
                     fg=color_var(c["crecimiento_interanual"]))
        var.config(text=f"ene–oct {self.anio_act} vs {self.anio_ant}", fg=COLOR_NOTA)

        valor, var = self.tarjetas["margen"]
        valor.config(text=fmt_pct(t["margen_pct"]))
        var.config(text=fmt_pp(c["margen_pp"]), fg=color_var(c["margen_pp"]))

        valor, var = self.tarjetas["unidades"]
        valor.config(text=f"{t['unidades']:,}")
        var.config(text=fmt_var(c["unidades_var"]), fg=color_var(c["unidades_var"]))

        valor, var = self.tarjetas["precio"]
        valor.config(text=f"Q{t['precio_prom']:,.2f}" if t["precio_prom"] else "—")
        var.config(text=fmt_var(c["precio_var"]), fg=color_var(c["precio_var"]))

        a, b = c["actual"], c["anterior"]
        self.lbl_comparacion.config(
            text=f"Comparación ene–oct:  {self.anio_act}: {fmt_q(a['ingresos'])} en ingresos, "
                 f"{a['unidades']:,} unidades  ·  {self.anio_ant}: {fmt_q(b['ingresos'])} en ingresos, "
                 f"{b['unidades']:,} unidades"
        )

    def _dibujar_graficas(self, df):
        self.fig.clear()
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1.15, 1], hspace=0.8, wspace=0.3,
                                   left=0.07, right=0.98, top=0.95, bottom=0.12)
        ax_lineas = self.fig.add_subplot(gs[0, :])
        ax_barras = self.fig.add_subplot(gs[1, 0])
        ax_pie = self.fig.add_subplot(gs[1, 1])

        g.dibujar_lineas(ax_lineas, self.serie, self.atip, self.proy)
        tabla = an.barras_categoria(df, self.anio_act, self.anio_ant)
        g.dibujar_barras_categoria(ax_barras, tabla, self.anio_ant, self.anio_act)
        g.dibujar_distribucion_canal(ax_pie, an.distribucion(df, "canal"))
        self.canvas_fig.draw_idle()

    def _llenar_productos(self, df):
        tabla = an.tabla_productos(df, self.anio_act, self.anio_ant)
        self.tv_productos.delete(*self.tv_productos.get_children())
        for _, fila in tabla.iterrows():
            var = fila["variacion"]
            etiqueta = "" if vacio(var) else ("sube" if var > 0 else "baja" if var < 0 else "")
            self.tv_productos.insert("", "end", tags=(etiqueta,) if etiqueta else (), values=(
                fila["producto"], fila["categoria"], fmt_q(fila["ingresos"]),
                fmt_var(var), fmt_pct(fila["margen_pct"]),
            ))
        self.lbl_productos.config(
            text=f"{len(tabla)} productos · ordenados de mayor a menor ingreso · "
                 f"variación ene–oct {self.anio_act} vs {self.anio_ant}"
        )

    def _llenar_atipicos(self):
        n = int(self.atip["atipico"].sum())
        if n == 0:
            self.lbl_atipicos.config(text="No hay meses atípicos en esta selección.", fg=COLOR_SUBE)
        else:
            self.lbl_atipicos.config(text=f"{n} mes(es) atípico(s) en esta selección (|z| > 2).",
                                     fg=COLOR_BAJA)

        self.tv_atipicos.delete(*self.tv_atipicos.get_children())
        for _, fila in self.atip.iterrows():
            if fila["atipico"]:
                estado, etiqueta = "Atípico", "atipico"
            else:
                estado, etiqueta = "Normal", ""
            self.tv_atipicos.insert("", "end", tags=(etiqueta,) if etiqueta else (), values=(
                nombre_mes(fila["periodo"]), fmt_q(fila["ingresos"]), f"{fila['z']:+.2f}", estado,
            ))

        self.tv_proy.delete(*self.tv_proy.get_children())
        if not self.proy:
            self.tv_proy.insert("", "end", values=("—", "—", "Se necesitan al menos 2 meses"))
        for periodo, valor in self.proy:
            self.tv_proy.insert("", "end", values=(
                nombre_mes(periodo), fmt_q(valor), "Estimación (no dato real)",
            ))

    # ----- informe y definiciones (RF-12, RF-13)
    def _llenar_informe(self):
        frag = [
            ("Informe de hallazgos\n", "titulo"),
            ("Cifras calculadas con todos los datos. Este informe no cambia con los filtros (RN-06).\n\n", "nota"),
        ]
        for i, texto in enumerate(self.informe["hallazgos"], start=1):
            frag += [(f"Hallazgo {i}\n", "negrita"), (texto + "\n\n", None)]
        frag += [("Recomendación\n", "negrita"), (self.informe["recomendacion"] + "\n\n", None)]
        frag += [("Cada cifra puede rastrearse en las pestañas Resumen, Productos y Gráficas (RNF-05).", "nota")]
        self._escribir(self.txt_informe, frag)

    def _llenar_definiciones(self):
        frag = [("Definición de los indicadores clave (KPI)\n", "titulo")]
        for nombre, formula, proposito in DEFINICIONES_KPI:
            frag += [(f"{nombre}\n", "negrita"), (f"Fórmula: {formula}\n", None),
                     (f"Para qué sirve: {proposito}\n\n", None)]
        frag += [("Reglas de negocio\n", "titulo")]
        for codigo, texto in REGLAS_NEGOCIO:
            frag += [(f"{codigo}  ", "negrita"), (texto + "\n", None)]
        self._escribir(self.txt_definiciones, frag)

    def _llenar_datos(self):
        r = self.resumen_carga
        motivos = "\n".join(f"  · {m}: {n} registro(s)" for m, n in r["motivos"].items()) or "  · Ninguno"
        self.lbl_datos.config(text=(
            f"Archivo: {os.path.basename(self.ruta)}\n"
            f"Registros en el archivo: {r['total']}   ·   Usados: {r['usados']}   ·   Descartados: {r['descartados']}\n"
            f"Reglas de calidad que causaron descartes:\n{motivos}"
        ))
        self.tv_datos.delete(*self.tv_datos.get_children())
        for _, fila in self.df_full.head(200).iterrows():
            self.tv_datos.insert("", "end", values=(
                int(fila["id"]), fila["periodo"], fila["producto"], fila["categoria"], fila["canal"],
                int(fila["unidades"]), f"{fila['precio_unit']:,.2f}", f"{fila['costo_unit']:,.2f}",
            ))


if __name__ == "__main__":
    DataVisionApp().mainloop()
