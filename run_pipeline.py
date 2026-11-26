"""
Pipeline End-to-End — Healthcare Appointments & No-Show Analytics
(SQL + Python + Excel + Power BI)
"""

from src.analytics_etl import evaluate_sms_impact, export_star_schema, load_and_clean_appointments
from src.generate_dataset import generate_healthcare_dataset
from src.report_generator import generate_excel_report, generate_figures
from src.sql_runner import build_sqlite_database, run_sql_analytics


def main():
    print("=" * 72)
    print("  HEALTHCARE APPOINTMENTS ANALYTICS — PIPELINE END-TO-END")
    print("=" * 72)

    # 1. Generación reproducible del dataset clínico relacional
    print("\n[1/4] Generando dataset clínico reproducible (50,000 citas)...")
    generate_healthcare_dataset(output_dir="data/raw", n_appointments=50_000, n_patients=16_000, seed=42)

    # 2. Base SQLite + Vistas + Consultas SQL Analíticas
    print("\n[2/4] Construyendo SQLite y ejecutando consultas SQL analíticas...")
    db_path = build_sqlite_database(raw_dir="data/raw", db_path="data/processed/healthcare.db")
    sql_outputs = run_sql_analytics(db_path=db_path, sql_dir="sql", output_dir="reports/sql_outputs")
    for name, df_out in sql_outputs.items():
        print(f"      ✓ SQL exportado: reports/sql_outputs/{name}.csv ({len(df_out)} filas)")

    # 3. ETL Python + Modelo Estrella Power BI + Prueba Estadística SMS
    print("\n[3/4] Ejecutando ETL Python, Modelo Estrella y test Chi-Cuadrado SMS...")
    tables = load_and_clean_appointments(raw_dir="data/raw", verbose=True)
    star_paths = export_star_schema(tables, output_dir="data/processed")
    for name, p in star_paths.items():
        print(f"      ✓ Tabla Power BI: {p}")

    sms_stats = evaluate_sms_impact(tables["merged"])
    print(
        f"      ✓ Efectividad SMS: Sin SMS={sms_stats['noshow_sin_sms_pct']}% vs "
        f"Con SMS={sms_stats['noshow_con_sms_pct']}% "
        f"(-{sms_stats['reduccion_relativa_pct']}% relativo | Chi2={sms_stats['chi2_stat']}, p={sms_stats['p_value']:.2e})"
    )
    print(
        f"      ✓ Potencial recuperación (95% SMS): ${sms_stats['ingreso_recuperable_usd']:,.2f} USD "
        f"(~{int(sms_stats['citas_recuperables_est']):,} citas)"
    )

    # 4. Gráficos PNG + Reporte Excel Ejecutivo
    print("\n[4/4] Generando gráficos PNG y Libro Excel Ejecutivo...")
    figs = generate_figures(sql_outputs, figures_dir="reports/figures")
    for f in figs:
        print(f"      ✓ Gráfico generado: {f}")

    excel_file = generate_excel_report(sql_outputs, sms_stats, excel_path="excel/Salud_Reporte_Ejecutivo.xlsx")
    print(f"      ✓ Reporte Excel generado: {excel_file}")

    kpi = sql_outputs["kpi_resumen_clinico"].iloc[0]
    print("\n" + "=" * 72)
    print("  RESUMEN DE KPIs CLÍNICOS VERIFICADOS")
    print("=" * 72)
    print(f"  Citas Efectivas      : {int(kpi['total_citas_efectivas']):,}")
    print(f"  Pacientes Únicos     : {int(kpi['pacientes_unicos']):,}")
    print(f"  Tasa Asistencia      : {float(kpi['tasa_asistencia_pct']):.2f}%")
    print(f"  Tasa No-Show         : {float(kpi['tasa_noshow_pct']):.2f}%")
    print(f"  Ingreso Realizado    : ${float(kpi['ingreso_realizado_usd']):,.2f} USD")
    print(f"  Ingreso Perdido      : ${float(kpi['ingreso_perdido_usd']):,.2f} USD")
    print(f"  Satisfacción Prom.   : {float(kpi['satisfaccion_promedio']):.2f} / 5.00")
    print("=" * 72)


if __name__ == "__main__":
    main()
