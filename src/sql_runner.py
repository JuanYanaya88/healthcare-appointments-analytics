import os
import re
import sqlite3
import pandas as pd


RAW_TABLES = ("clinics", "doctors", "patients", "appointments")


def build_sqlite_database(
    raw_dir: str = "data/raw",
    db_path: str = "data/processed/healthcare.db",
) -> str:
    """Carga las 4 tablas clínicas normalizadas en SQLite e indexa las llaves."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    try:
        for table in RAW_TABLES:
            csv_path = os.path.join(raw_dir, f"{table}.csv")
            df = pd.read_csv(csv_path)
            df.to_sql(table, conn, if_exists="replace", index=False)

        indexes = [
            "CREATE INDEX idx_appt_id ON appointments(appointment_id);",
            "CREATE INDEX idx_appt_patient ON appointments(patient_id);",
            "CREATE INDEX idx_appt_clinic ON appointments(clinic_id);",
            "CREATE INDEX idx_appt_doctor ON appointments(doctor_id);",
            "CREATE INDEX idx_appt_status ON appointments(appointment_status);",
            "CREATE INDEX idx_patients_id ON patients(patient_id);",
            "CREATE INDEX idx_doctors_id ON doctors(doctor_id);",
            "CREATE INDEX idx_clinics_id ON clinics(clinic_id);",
        ]
        for idx in indexes:
            conn.execute(idx)
        conn.commit()
    finally:
        conn.close()

    return db_path


def _parse_named_queries(sql_text: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"--\s*@name:\s*([a-zA-Z0-9_]+)\s*\n(.*?)(?=(?:--\s*@name:|\Z))", re.DOTALL
    )
    return [(m.group(1).strip(), m.group(2).strip()) for m in pattern.finditer(sql_text) if m.group(2).strip()]


def run_sql_analytics(
    db_path: str = "data/processed/healthcare.db",
    sql_dir: str = "sql",
    output_dir: str = "reports/sql_outputs",
) -> dict[str, pd.DataFrame]:
    """Ejecuta las vistas y consultas SQL clínicas y exporta los resultados a CSV."""
    os.makedirs(output_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    results: dict[str, pd.DataFrame] = {}

    try:
        with open(os.path.join(sql_dir, "01_schema_and_views.sql"), "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()

        query_files = [
            "02_kpi_operational_analysis.sql",
            "03_noshow_drivers_analysis.sql",
            "04_patient_risk_segmentation.sql",
        ]
        for qfile in query_files:
            with open(os.path.join(sql_dir, qfile), "r", encoding="utf-8") as f:
                content = f.read()
            for name, sql in _parse_named_queries(content):
                df_res = pd.read_sql_query(sql, conn)
                results[name] = df_res
                df_res.to_csv(os.path.join(output_dir, f"{name}.csv"), index=False, encoding="utf-8-sig")
    finally:
        conn.close()

    return results
