import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# Paleta clínica profesional (azul médico, verde salud, coral alerta)
DEEP_TEAL = "#0F4C5C"
MED_BLUE = "#1E6091"
HEALTH_GREEN = "#2A9D8F"
CORAL = "#E76F51"
AMBER = "#E9C46A"
DARK_RED = "#C1121F"


def _setup_style():
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#CBD5E0",
            "axes.grid": True,
            "grid.color": "#EDF2F7",
            "grid.linestyle": "-",
            "grid.linewidth": 0.8,
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def generate_figures(
    sql_outputs: dict[str, pd.DataFrame],
    figures_dir: str = "reports/figures",
) -> list[str]:
    """Genera 4 gráficos ejecutivos PNG del sector salud para el README."""
    os.makedirs(figures_dir, exist_ok=True)
    _setup_style()
    generated: list[str] = []

    # -------------------------------------------------------------------------
    # 1. Evolución Mensual: Ingreso Perdido por No-Show y Tasa de Inasistencia %
    # -------------------------------------------------------------------------
    df_m = sql_outputs["tendencia_mensual_noshow"].copy()
    fig, ax1 = plt.subplots(figsize=(11, 5))
    x = np.arange(len(df_m))
    ax1.bar(x, df_m["ingreso_perdido_usd"] / 1_000, color=MED_BLUE, alpha=0.82, width=0.62, label="Ingreso Perdido (k USD)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(df_m["appointment_month"], rotation=45, ha="right", fontsize=8.5)
    ax1.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}k"))
    ax1.set_ylim(0, (df_m["ingreso_perdido_usd"].max() / 1_000) * 1.28)
    ax1.set_ylabel("Ingreso Perdido (Miles de USD)", fontweight="bold", color=DEEP_TEAL)
    ax1.set_xlabel("Mes de Atención", fontweight="bold", color=DEEP_TEAL)

    ax2 = ax1.twinx()
    ax2.spines["top"].set_visible(False)
    ax2.plot(x, df_m["tasa_noshow_pct"], color=CORAL, marker="o", linewidth=2.3, markersize=5.5, label="Tasa No-Show (%)")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.set_ylim(0, max(df_m["tasa_noshow_pct"].max() + 8, 35))
    ax2.set_ylabel("Tasa de Inasistencia (%)", fontweight="bold", color=CORAL)
    ax2.grid(False)

    ax1.set_title(
        "Evolución Mensual: Ingreso Perdido y Tasa de No-Show (2024 – 2025)",
        fontsize=13,
        fontweight="bold",
        color=DEEP_TEAL,
        pad=14,
    )
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", frameon=True, facecolor="white")
    plt.tight_layout()
    p1 = os.path.join(figures_dir, "01_tendencia_noshow_mensual.png")
    plt.savefig(p1, dpi=180)
    plt.close(fig)
    generated.append(p1)

    # -------------------------------------------------------------------------
    # 2. Impacto Financiero y Tasa de No-Show por Especialidad Médica
    # -------------------------------------------------------------------------
    df_sp = sql_outputs["especialidades_impacto_financiero"].sort_values("ingreso_perdido_usd", ascending=True).copy()
    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    colors = [CORAL if ns >= 22 else (MED_BLUE if ns >= 18 else HEALTH_GREEN) for ns in df_sp["tasa_noshow_pct"]]
    bars = ax.barh(df_sp["especialidad"], df_sp["ingreso_perdido_usd"] / 1_000, color=colors, height=0.65)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}k"))
    ax.set_xlim(0, (df_sp["ingreso_perdido_usd"].max() / 1_000) * 1.25)
    ax.set_xlabel("Ingreso Perdido por No-Show (Miles de USD)", fontweight="bold", color=DEEP_TEAL)

    for bar, val, rate in zip(bars, df_sp["ingreso_perdido_usd"], df_sp["tasa_noshow_pct"]):
        ax.text(
            bar.get_width() + 1.2,
            bar.get_y() + bar.get_height() / 2,
            f"${val/1000:,.1f}k  ({rate:.1f}% No-Show)",
            va="center",
            fontsize=8.8,
            fontweight="bold",
            color=DEEP_TEAL,
        )

    ax.set_title(
        "Impacto Financiero y Tasa de Inasistencia por Especialidad Médica",
        fontsize=13,
        fontweight="bold",
        color=DEEP_TEAL,
        pad=14,
    )
    plt.tight_layout()
    p2 = os.path.join(figures_dir, "02_especialidades_impacto_financiero.png")
    plt.savefig(p2, dpi=180)
    plt.close(fig)
    generated.append(p2)

    # -------------------------------------------------------------------------
    # 3. Tiempo de Espera (Lead Time) x Efectividad del Recordatorio SMS
    # -------------------------------------------------------------------------
    df_sms = sql_outputs["efectividad_recordatorio_sms"].copy()
    piv = df_sms.pivot(index="rango_espera", columns="recordatorio_sms", values="tasa_noshow_pct").reset_index()
    labels_clean = [s.split(". ", 1)[-1] for s in piv["rango_espera"]]

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    x = np.arange(len(piv))
    w = 0.36
    b1 = ax.bar(x - w / 2, piv["Sin SMS"], width=w, color=CORAL, label="Sin Recordatorio SMS")
    b2 = ax.bar(x + w / 2, piv["Con SMS"], width=w, color=HEALTH_GREEN, label="Con Recordatorio SMS")

    for group in (b1, b2):
        for bar in group:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 0.8,
                f"{h:.1f}%",
                ha="center",
                va="bottom",
                fontsize=8.3,
                fontweight="bold",
                color=DEEP_TEAL,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels_clean, fontsize=9.2)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, piv[["Sin SMS", "Con SMS"]].max().max() + 10)
    ax.set_ylabel("Tasa de Inasistencia (%)", fontweight="bold", color=DEEP_TEAL)
    ax.set_xlabel("Tiempo de Espera desde Agendamiento", fontweight="bold", color=DEEP_TEAL)
    ax.set_title(
        "Efecto del Tiempo de Espera y Recordatorio SMS en la Tasa de No-Show",
        fontsize=13,
        fontweight="bold",
        color=DEEP_TEAL,
        pad=14,
    )
    ax.legend(frameon=True, facecolor="white")
    plt.tight_layout()
    p3 = os.path.join(figures_dir, "03_espera_y_recordatorio_sms.png")
    plt.savefig(p3, dpi=180)
    plt.close(fig)
    generated.append(p3)

    # -------------------------------------------------------------------------
    # 4. Segmentación de Riesgo de Pacientes: % Pacientes vs % del Total No-Show
    # -------------------------------------------------------------------------
    df_risk = sql_outputs["segmentacion_riesgo_pacientes"].copy()
    labels_r = [s.split(". ", 1)[-1] for s in df_risk["segmento_riesgo"]]

    fig, ax = plt.subplots(figsize=(10.5, 5))
    x = np.arange(len(df_risk))
    w = 0.36
    b1 = ax.bar(x - w / 2, df_risk["pct_pacientes"], width=w, color=MED_BLUE, label="% de Pacientes")
    b2 = ax.bar(x + w / 2, df_risk["pct_del_total_noshow"], width=w, color=CORAL, label="% del Total de Inasistencias")

    for group in (b1, b2):
        for bar in group:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 1.0,
                f"{h:.1f}%",
                ha="center",
                va="bottom",
                fontsize=8.5,
                fontweight="bold",
                color=DEEP_TEAL,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels_r, fontsize=9.0, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, max(df_risk["pct_pacientes"].max(), df_risk["pct_del_total_noshow"].max()) + 12)
    ax.set_ylabel("Participación (%)", fontweight="bold", color=DEEP_TEAL)
    ax.set_title(
        "Segmentación de Riesgo de Pacientes: Concentración de Inasistencias",
        fontsize=13,
        fontweight="bold",
        color=DEEP_TEAL,
        pad=14,
    )
    ax.legend(frameon=True, facecolor="white")
    plt.tight_layout()
    p4 = os.path.join(figures_dir, "04_segmentacion_riesgo_pacientes.png")
    plt.savefig(p4, dpi=180)
    plt.close(fig)
    generated.append(p4)

    return generated


def _style_header(ws, row_idx: int, num_cols: int, fill_hex: str = "0F4C5C"):
    fill = PatternFill("solid", fgColor=fill_hex)
    font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(border_style="thin", color="CBD5E0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws.row_dimensions[row_idx].height = 24
    for col in range(1, num_cols + 1):
        c = ws.cell(row=row_idx, column=col)
        c.fill = fill
        c.font = font
        c.alignment = align
        c.border = border


def _style_rows(ws, start_r: int, end_r: int, num_cols: int):
    alt_fill = PatternFill("solid", fgColor="F0F7F9")
    white_fill = PatternFill("solid", fgColor="FFFFFF")
    font = Font(name="Calibri", size=10, color="1A202C")
    thin = Side(border_style="thin", color="E2E8F0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for r in range(start_r, end_r + 1):
        fill = alt_fill if (r - start_r) % 2 == 1 else white_fill
        for c in range(1, num_cols + 1):
            cell = ws.cell(row=r, column=c)
            cell.fill = fill
            cell.font = font
            cell.border = border


def _autofit(ws, min_w: int = 12, max_w: int = 34):
    for col_cells in ws.columns:
        letter = get_column_letter(col_cells[0].column)
        max_len = 0
        for cell in col_cells:
            v = str(cell.value or "")
            if v.startswith("="):
                v = "1234567890"
            max_len = max(max_len, len(v))
        ws.column_dimensions[letter].width = max(min_w, min(max_len + 4, max_w))


def generate_excel_report(
    sql_outputs: dict[str, pd.DataFrame],
    sms_stats: dict[str, float],
    excel_path: str = "excel/Salud_Reporte_Ejecutivo.xlsx",
) -> str:
    """Genera libro Excel clínico de 5 hojas con fórmulas dinámicas y gráficos nativos."""
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
    wb = Workbook()

    # =========================================================================
    # HOJA 1: Resumen Ejecutivo
    # =========================================================================
    ws = wb.active
    ws.title = "Resumen Ejecutivo"
    ws.views.sheetView[0].showGridLines = False

    ws["B2"] = "REPORTE EJECUTIVO — ANÁLISIS DE CITAS MÉDICAS Y NO-SHOW (SECTOR SALUD)"
    ws["B2"].font = Font(name="Calibri", size=15, bold=True, color="0F4C5C")
    ws["B3"] = "Proyecto de Análisis de Datos | SQL + Python + Excel + Power BI | Autor: Juan David Yanayaco"
    ws["B3"].font = Font(name="Calibri", size=10, italic=True, color="4A5568")

    kpi = sql_outputs["kpi_resumen_clinico"].iloc[0]
    kpis = [
        ("Citas Efectivas Analizadas", int(kpi["total_citas_efectivas"]), "#,##0", "Total de citas Atendidas + No-Show (2024–2025 tras deduplicación)."),
        ("Pacientes Únicos", int(kpi["pacientes_unicos"]), "#,##0", "Población atendida a través de las 6 sedes y 10 especialidades."),
        ("Citas Atendidas", int(kpi["citas_atendidas"]), "#,##0", "Consultas efectivamente realizadas."),
        ("Citas con Inasistencia (No-Show)", int(kpi["citas_noshow"]), "#,##0", "Cupos médicos perdidos sin cancelación previa."),
        ("Tasa Global de No-Show (Fórmula)", "=C9/C6", "0.0%", "Calculada dinámicamente (=No-Show / Citas Efectivas)."),
        ("Ingreso Realizado (USD)", float(kpi["ingreso_realizado_usd"]), "$#,##0.00", "Facturación efectivamente ejecutada por consultas atendidas."),
        ("Ingreso Perdido por No-Show (USD)", float(kpi["ingreso_perdido_usd"]), "$#,##0.00", "Pérdida financiera directa por inasistencias médicas."),
        ("Reducción Relativa con SMS", sms_stats["reduccion_relativa_pct"] / 100.0, "0.0%", f"Estadísticamente significativa (Chi²={sms_stats['chi2_stat']}, p<0.001)."),
        ("Recuperación Potencial (95% SMS)", sms_stats["ingreso_recuperable_usd"], "$#,##0.00", f"Estimado al cubrir el 95% de citas futuras (~{int(sms_stats['citas_recuperables_est']):,} citas)."),
    ]

    ws["B5"] = "Indicador Clínico / Financiero"
    ws["C5"] = "Valor"
    ws["D5"] = "Interpretación de Negocio"
    _style_header(ws, 5, 4)
    ws["A5"].fill = PatternFill(fill_type=None)
    ws["A5"].border = Border()

    thin = Side(border_style="thin", color="E2E8F0")
    for idx, (label, val, fmt, note) in enumerate(kpis, start=6):
        ws.cell(row=idx, column=2, value=label).font = Font(name="Calibri", size=10, bold=True, color="0F4C5C")
        cv = ws.cell(row=idx, column=3, value=val)
        cv.number_format = fmt
        cv.font = Font(name="Calibri", size=11, bold=True, color="1E6091")
        cv.alignment = Alignment(horizontal="right")
        ws.cell(row=idx, column=4, value=note).font = Font(name="Calibri", size=10, color="2D3748")
        for c in (2, 3, 4):
            ws.cell(row=idx, column=c).border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if idx % 2 == 1:
                ws.cell(row=idx, column=c).fill = PatternFill("solid", fgColor="F0F7F9")

    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 66

    # =========================================================================
    # HOJA 2: Tendencia Mensual
    # =========================================================================
    ws_m = wb.create_sheet("Tendencia Mensual")
    df_m = sql_outputs["tendencia_mensual_noshow"].copy()
    ws_m["A1"] = "EVOLUCIÓN MENSUAL DE CITAS, NO-SHOW E IMPACTO FINANCIERO"
    ws_m["A1"].font = Font(name="Calibri", size=13, bold=True, color="0F4C5C")

    headers_m = [
        "Mes", "Total Citas", "Atendidas", "No-Show",
        "Tasa No-Show % (Fórmula)", "Ingreso Realizado (USD)", "Ingreso Perdido (USD)", "Espera Prom. (días)"
    ]
    for c, h in enumerate(headers_m, start=1):
        ws_m.cell(row=3, column=c, value=h)
    _style_header(ws_m, 3, len(headers_m))

    end_m = 3 + len(df_m)
    for i, row in df_m.iterrows():
        r = 4 + i
        ws_m.cell(row=r, column=1, value=row["appointment_month"])
        ws_m.cell(row=r, column=2, value=int(row["total_citas"])).number_format = "#,##0"
        ws_m.cell(row=r, column=3, value=int(row["atendidas"])).number_format = "#,##0"
        ws_m.cell(row=r, column=4, value=int(row["noshow"])).number_format = "#,##0"
        ws_m.cell(row=r, column=5, value=f"=IF(B{r}>0,D{r}/B{r},0)").number_format = "0.0%"
        ws_m.cell(row=r, column=6, value=float(row["ingreso_realizado_usd"])).number_format = "$#,##0.00"
        ws_m.cell(row=r, column=7, value=float(row["ingreso_perdido_usd"])).number_format = "$#,##0.00"
        ws_m.cell(row=r, column=8, value=float(row["espera_prom_dias"])).number_format = "0.0"

    _style_rows(ws_m, 4, end_m, len(headers_m))
    tot_m = end_m + 1
    ws_m.cell(row=tot_m, column=1, value="TOTAL / PROMEDIO")
    ws_m.cell(row=tot_m, column=2, value=f"=SUM(B4:B{end_m})").number_format = "#,##0"
    ws_m.cell(row=tot_m, column=3, value=f"=SUM(C4:C{end_m})").number_format = "#,##0"
    ws_m.cell(row=tot_m, column=4, value=f"=SUM(D4:D{end_m})").number_format = "#,##0"
    ws_m.cell(row=tot_m, column=5, value=f"=D{tot_m}/B{tot_m}").number_format = "0.0%"
    ws_m.cell(row=tot_m, column=6, value=f"=SUM(F4:F{end_m})").number_format = "$#,##0.00"
    ws_m.cell(row=tot_m, column=7, value=f"=SUM(G4:G{end_m})").number_format = "$#,##0.00"
    ws_m.cell(row=tot_m, column=8, value=f"=AVERAGE(H4:H{end_m})").number_format = "0.0"
    _style_header(ws_m, tot_m, len(headers_m), fill_hex="1E6091")
    ws_m.freeze_panes = "A4"
    _autofit(ws_m)

    ch_m = LineChart()
    ch_m.title = "Ingreso Perdido Mensual por No-Show (USD)"
    ch_m.add_data(Reference(ws_m, min_col=7, min_row=3, max_row=end_m), titles_from_data=True)
    ch_m.set_categories(Reference(ws_m, min_col=1, min_row=4, max_row=end_m))
    ch_m.legend = None
    ch_m.width = 17
    ch_m.height = 10
    ws_m.add_chart(ch_m, "J3")

    # =========================================================================
    # HOJA 3: Especialidades y Costo
    # =========================================================================
    ws_s = wb.create_sheet("Especialidades")
    df_sp = sql_outputs["especialidades_impacto_financiero"].copy()
    ws_s["A1"] = "IMPACTO FINANCIERO Y PARETO DE PÉRDIDAS POR ESPECIALIDAD MÉDICA"
    ws_s["A1"].font = Font(name="Calibri", size=13, bold=True, color="0F4C5C")

    headers_s = [
        "Especialidad", "Total Citas", "No-Show", "Tasa No-Show % (Fórmula)",
        "Tarifa Prom. (USD)", "Ingreso Perdido (USD)", "% Pérdida (Fórmula)", "% Acumulado Pareto", "Satisfacción"
    ]
    for c, h in enumerate(headers_s, start=1):
        ws_s.cell(row=3, column=c, value=h)
    _style_header(ws_s, 3, len(headers_s))

    end_s = 3 + len(df_sp)
    for i, row in df_sp.iterrows():
        r = 4 + i
        ws_s.cell(row=r, column=1, value=row["especialidad"])
        ws_s.cell(row=r, column=2, value=int(row["total_citas"])).number_format = "#,##0"
        ws_s.cell(row=r, column=3, value=int(row["citas_noshow"])).number_format = "#,##0"
        ws_s.cell(row=r, column=4, value=f"=C{r}/B{r}").number_format = "0.0%"
        ws_s.cell(row=r, column=5, value=float(row["tarifa_prom_usd"])).number_format = "$#,##0.00"
        ws_s.cell(row=r, column=6, value=float(row["ingreso_perdido_usd"])).number_format = "$#,##0.00"
        ws_s.cell(row=r, column=7, value=f"=F{r}/$F${end_s+1}").number_format = "0.0%"
        ws_s.cell(row=r, column=8, value=f"=SUM($F$4:F{r})/$F${end_s+1}").number_format = "0.0%"
        ws_s.cell(row=r, column=9, value=float(row["satisfaccion_prom"])).number_format = "0.00"

    _style_rows(ws_s, 4, end_s, len(headers_s))
    tot_s = end_s + 1
    ws_s.cell(row=tot_s, column=1, value="TOTAL / PROMEDIO")
    ws_s.cell(row=tot_s, column=2, value=f"=SUM(B4:B{end_s})").number_format = "#,##0"
    ws_s.cell(row=tot_s, column=3, value=f"=SUM(C4:C{end_s})").number_format = "#,##0"
    ws_s.cell(row=tot_s, column=4, value=f"=C{tot_s}/B{tot_s}").number_format = "0.0%"
    ws_s.cell(row=tot_s, column=5, value=f"=AVERAGE(E4:E{end_s})").number_format = "$#,##0.00"
    ws_s.cell(row=tot_s, column=6, value=f"=SUM(F4:F{end_s})").number_format = "$#,##0.00"
    ws_s.cell(row=tot_s, column=7, value=f"=SUM(G4:G{end_s})").number_format = "0.0%"
    ws_s.cell(row=tot_s, column=8, value=1.0).number_format = "0.0%"
    ws_s.cell(row=tot_s, column=9, value=f"=AVERAGE(I4:I{end_s})").number_format = "0.00"
    _style_header(ws_s, tot_s, len(headers_s), fill_hex="1E6091")
    ws_s.freeze_panes = "A4"
    _autofit(ws_s)

    ch_s = BarChart()
    ch_s.type = "bar"
    ch_s.title = "Ingreso Perdido por Especialidad (USD)"
    ch_s.add_data(Reference(ws_s, min_col=6, min_row=3, max_row=end_s), titles_from_data=True)
    ch_s.set_categories(Reference(ws_s, min_col=1, min_row=4, max_row=end_s))
    ch_s.legend = None
    ch_s.width = 16
    ch_s.height = 11
    ws_s.add_chart(ch_s, "K3")

    # =========================================================================
    # HOJA 4: Factores No-Show (Espera + SMS + Régimen)
    # =========================================================================
    ws_f = wb.create_sheet("Factores No-Show")
    df_lt = sql_outputs["noshow_por_tiempo_espera"].copy()
    ws_f["A1"] = "FACTORES DETERMINANTES DE INASISTENCIA (ESPERA Y RECORDATORIOS SMS)"
    ws_f["A1"].font = Font(name="Calibri", size=13, bold=True, color="0F4C5C")

    headers_lt = [
        "Rango de Espera", "Total Citas", "% Citas (Fórmula)", "Citas No-Show",
        "Tasa No-Show % (Fórmula)", "Ingreso Perdido (USD)", "Satisfacción Prom."
    ]
    for c, h in enumerate(headers_lt, start=1):
        ws_f.cell(row=3, column=c, value=h)
    _style_header(ws_f, 3, len(headers_lt))

    end_lt = 3 + len(df_lt)
    for i, row in df_lt.iterrows():
        r = 4 + i
        ws_f.cell(row=r, column=1, value=row["rango_espera"])
        ws_f.cell(row=r, column=2, value=int(row["total_citas"])).number_format = "#,##0"
        ws_f.cell(row=r, column=3, value=f"=B{r}/$B${end_lt+1}").number_format = "0.0%"
        ws_f.cell(row=r, column=4, value=int(row["citas_noshow"])).number_format = "#,##0"
        ws_f.cell(row=r, column=5, value=f"=D{r}/B{r}").number_format = "0.0%"
        ws_f.cell(row=r, column=6, value=float(row["ingreso_perdido_usd"])).number_format = "$#,##0.00"
        ws_f.cell(row=r, column=7, value=float(row["satisfaccion_prom"])).number_format = "0.00"

    _style_rows(ws_f, 4, end_lt, len(headers_lt))
    tot_lt = end_lt + 1
    ws_f.cell(row=tot_lt, column=1, value="TOTAL / PROMEDIO")
    ws_f.cell(row=tot_lt, column=2, value=f"=SUM(B4:B{end_lt})").number_format = "#,##0"
    ws_f.cell(row=tot_lt, column=3, value=f"=SUM(C4:C{end_lt})").number_format = "0.0%"
    ws_f.cell(row=tot_lt, column=4, value=f"=SUM(D4:D{end_lt})").number_format = "#,##0"
    ws_f.cell(row=tot_lt, column=5, value=f"=D{tot_lt}/B{tot_lt}").number_format = "0.0%"
    ws_f.cell(row=tot_lt, column=6, value=f"=SUM(F4:F{end_lt})").number_format = "$#,##0.00"
    ws_f.cell(row=tot_lt, column=7, value=f"=AVERAGE(G4:G{end_lt})").number_format = "0.00"
    _style_header(ws_f, tot_lt, len(headers_lt), fill_hex="1E6091")

    # Segunda tabla: Comparativa SMS Global
    df_sg = sql_outputs["resumen_sms_global"].copy()
    sr = tot_lt + 3
    ws_f.cell(row=sr, column=1, value="IMPACTO DEL RECORDATORIO SMS").font = Font(
        name="Calibri", size=12, bold=True, color="0F4C5C"
    )
    sh = sr + 1
    for c, h in enumerate(["Grupo SMS", "Total Citas", "Citas No-Show", "Tasa No-Show % (Fórmula)", "Ingreso Perdido (USD)"], start=1):
        ws_f.cell(row=sh, column=c, value=h)
    _style_header(ws_f, sh, 5, fill_hex="2A9D8F")
    for i, row in df_sg.iterrows():
        r = sh + 1 + i
        ws_f.cell(row=r, column=1, value=row["grupo_sms"])
        ws_f.cell(row=r, column=2, value=int(row["total_citas"])).number_format = "#,##0"
        ws_f.cell(row=r, column=3, value=int(row["citas_noshow"])).number_format = "#,##0"
        ws_f.cell(row=r, column=4, value=f"=C{r}/B{r}").number_format = "0.0%"
        ws_f.cell(row=r, column=5, value=float(row["ingreso_perdido_usd"])).number_format = "$#,##0.00"
    _style_rows(ws_f, sh + 1, sh + len(df_sg), 5)
    ws_f.freeze_panes = "A4"
    _autofit(ws_f)

    ch_f = BarChart()
    ch_f.title = "Tasa de No-Show por Rango de Espera"
    ch_f.add_data(Reference(ws_f, min_col=5, min_row=3, max_row=end_lt), titles_from_data=True)
    ch_f.set_categories(Reference(ws_f, min_col=1, min_row=4, max_row=end_lt))
    ch_f.legend = None
    ch_f.width = 16
    ch_f.height = 10
    ws_f.add_chart(ch_f, "I3")

    # =========================================================================
    # HOJA 5: Segmentación de Pacientes
    # =========================================================================
    ws_p = wb.create_sheet("Riesgo Pacientes")
    df_p = sql_outputs["segmentacion_riesgo_pacientes"].copy()
    ws_p["A1"] = "SEGMENTACIÓN DE PACIENTES POR RIESGO DE INASISTENCIA"
    ws_p["A1"].font = Font(name="Calibri", size=13, bold=True, color="0F4C5C")

    headers_p = [
        "Segmento de Riesgo", "Pacientes", "% Pacientes (Fórmula)", "Citas Totales",
        "Citas No-Show", "% del Total No-Show (Fórmula)", "Ingreso Perdido (USD)"
    ]
    for c, h in enumerate(headers_p, start=1):
        ws_p.cell(row=3, column=c, value=h)
    _style_header(ws_p, 3, len(headers_p))

    end_p = 3 + len(df_p)
    for i, row in df_p.iterrows():
        r = 4 + i
        ws_p.cell(row=r, column=1, value=row["segmento_riesgo"])
        ws_p.cell(row=r, column=2, value=int(row["pacientes"])).number_format = "#,##0"
        ws_p.cell(row=r, column=3, value=f"=B{r}/$B${end_p+1}").number_format = "0.0%"
        ws_p.cell(row=r, column=4, value=int(row["citas_totales"])).number_format = "#,##0"
        ws_p.cell(row=r, column=5, value=int(row["citas_noshow"])).number_format = "#,##0"
        ws_p.cell(row=r, column=6, value=f"=E{r}/$E${end_p+1}").number_format = "0.0%"
        ws_p.cell(row=r, column=7, value=float(row["ingreso_perdido_usd"])).number_format = "$#,##0.00"

    _style_rows(ws_p, 4, end_p, len(headers_p))
    tot_p = end_p + 1
    ws_p.cell(row=tot_p, column=1, value="TOTAL")
    ws_p.cell(row=tot_p, column=2, value=f"=SUM(B4:B{end_p})").number_format = "#,##0"
    ws_p.cell(row=tot_p, column=3, value=f"=SUM(C4:C{end_p})").number_format = "0.0%"
    ws_p.cell(row=tot_p, column=4, value=f"=SUM(D4:D{end_p})").number_format = "#,##0"
    ws_p.cell(row=tot_p, column=5, value=f"=SUM(E4:E{end_p})").number_format = "#,##0"
    ws_p.cell(row=tot_p, column=6, value=f"=SUM(F4:F{end_p})").number_format = "0.0%"
    ws_p.cell(row=tot_p, column=7, value=f"=SUM(G4:G{end_p})").number_format = "$#,##0.00"
    _style_header(ws_p, tot_p, len(headers_p), fill_hex="1E6091")
    ws_p.freeze_panes = "A4"
    _autofit(ws_p)

    ch_p = BarChart()
    ch_p.title = "Ingreso Perdido por Segmento de Riesgo (USD)"
    ch_p.add_data(Reference(ws_p, min_col=7, min_row=3, max_row=end_p), titles_from_data=True)
    ch_p.set_categories(Reference(ws_p, min_col=1, min_row=4, max_row=end_p))
    ch_p.legend = None
    ch_p.width = 16
    ch_p.height = 10
    ws_p.add_chart(ch_p, "I3")

    wb.save(excel_path)
    return excel_path
