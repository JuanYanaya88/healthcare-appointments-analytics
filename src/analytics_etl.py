import os
import pandas as pd
from scipy.stats import chi2_contingency


def load_and_clean_appointments(raw_dir: str = "data/raw", verbose: bool = True) -> dict[str, pd.DataFrame]:
    """
    Carga, deduplica y limpia las tablas clínicas.
    Retorna diccionario con tablas limpias + tabla consolidada de citas efectivas.
    """
    clinics = pd.read_csv(os.path.join(raw_dir, "clinics.csv"))
    doctors = pd.read_csv(os.path.join(raw_dir, "doctors.csv"))
    patients = pd.read_csv(os.path.join(raw_dir, "patients.csv"))
    appts = pd.read_csv(os.path.join(raw_dir, "appointments.csv"))

    raw_rows = len(appts)
    appts = appts.drop_duplicates(subset=["appointment_id"], keep="first").copy()
    dups_removed = raw_rows - len(appts)

    null_channels = int(appts["booking_channel"].isna().sum())
    appts["booking_channel"] = appts["booking_channel"].fillna("No Registrado")

    appts["scheduled_date"] = pd.to_datetime(appts["scheduled_date"])
    appts["appointment_date"] = pd.to_datetime(appts["appointment_date"])
    appts["appointment_month"] = appts["appointment_date"].dt.to_period("M").astype(str)

    # Citas efectivas (Atendida vs No-Show)
    cancelled_count = int((appts["appointment_status"] == "Cancelada").sum())
    appts_eff = appts[appts["appointment_status"].isin(["Atendida", "No-Show"])].copy()
    appts_eff["is_noshow"] = (appts_eff["appointment_status"] == "No-Show").astype(int)
    appts_eff["lost_revenue_usd"] = appts_eff["consultation_fee_usd"].where(
        appts_eff["is_noshow"] == 1, 0.0
    )
    appts_eff["realized_revenue_usd"] = appts_eff["consultation_fee_usd"].where(
        appts_eff["is_noshow"] == 0, 0.0
    )

    # Grupos etarios
    patients["age_group"] = pd.cut(
        patients["age"],
        bins=[-1, 17, 30, 45, 60, 120],
        labels=[
            "1. Menor (<18)",
            "2. Joven (18-30)",
            "3. Adulto (31-45)",
            "4. Adulto Mayor (46-60)",
            "5. Senior (>60)",
        ],
    ).astype(str)

    # Rango de espera (lead_time_days)
    appts_eff["lead_time_bucket"] = pd.cut(
        appts_eff["lead_time_days"],
        bins=[-1, 0, 3, 7, 14, 30, 999],
        labels=[
            "1. Mismo día (0d)",
            "2. Corta (1-3d)",
            "3. Media (4-7d)",
            "4. Alta (8-14d)",
            "5. Muy Alta (15-30d)",
            "6. Crítica (>30d)",
        ],
    ).astype(str)

    # Consolidado analítico
    df_merged = (
        appts_eff.merge(patients, on="patient_id", how="inner")
        .merge(clinics, on="clinic_id", how="inner")
        .merge(doctors[["doctor_id", "doctor_name"]], on="doctor_id", how="inner")
    )

    if verbose:
        print(
            f"[ETL] Citas crudas: {raw_rows:,} | Duplicados eliminados: {dups_removed} "
            f"| Canales nulos imputados: {null_channels} | Canceladas excluidas: {cancelled_count:,} "
            f"| Citas efectivas: {len(df_merged):,}"
        )

    return {
        "clinics": clinics,
        "doctors": doctors,
        "patients": patients,
        "appointments": appts_eff,
        "merged": df_merged,
    }


def evaluate_sms_impact(df_merged: pd.DataFrame) -> dict[str, float]:
    """
    Evalúa mediante prueba estadística Chi-Cuadrado la efectividad del recordatorio SMS
    y estima el potencial de recuperación financiera al ampliar la cobertura de SMS al 95%.
    """
    ct = pd.crosstab(df_merged["sms_reminder_sent"], df_merged["is_noshow"])
    chi2, p_val, _, _ = chi2_contingency(ct)

    ns_no_sms = df_merged.loc[df_merged["sms_reminder_sent"] == 0, "is_noshow"].mean()
    ns_with_sms = df_merged.loc[df_merged["sms_reminder_sent"] == 1, "is_noshow"].mean()
    abs_reduction_pp = (ns_no_sms - ns_with_sms) * 100
    rel_reduction_pct = (ns_no_sms - ns_with_sms) / ns_no_sms * 100

    # Simulación de impacto financiero: cubrir 95% de citas con lead_time >= 1 día que hoy no tienen SMS
    target_pool = df_merged[(df_merged["sms_reminder_sent"] == 0) & (df_merged["lead_time_days"] >= 1)]
    avg_fee = target_pool["consultation_fee_usd"].mean()
    citas_recuperables = len(target_pool) * 0.95 * (ns_no_sms - ns_with_sms)
    ahorro_estimado_usd = citas_recuperables * avg_fee

    return {
        "noshow_sin_sms_pct": round(ns_no_sms * 100, 2),
        "noshow_con_sms_pct": round(ns_with_sms * 100, 2),
        "reduccion_absoluta_pp": round(abs_reduction_pp, 2),
        "reduccion_relativa_pct": round(rel_reduction_pct, 1),
        "chi2_stat": round(float(chi2), 2),
        "p_value": float(p_val),
        "citas_recuperables_est": round(float(citas_recuperables), 0),
        "ingreso_recuperable_usd": round(float(ahorro_estimado_usd), 2),
    }


def export_star_schema(tables: dict[str, pd.DataFrame], output_dir: str = "data/processed") -> dict[str, str]:
    """Exporta tablas limpias en Modelo Estrella listas para importar en Power BI Desktop."""
    os.makedirs(output_dir, exist_ok=True)
    appts = tables["appointments"]
    patients = tables["patients"]
    doctors = tables["doctors"]
    clinics = tables["clinics"]

    # Segmentación de riesgo por paciente para dim_patients
    pat_hist = (
        appts.groupby("patient_id", as_index=False)
        .agg(total_citas=("appointment_id", "count"), total_noshow=("is_noshow", "sum"))
    )

    def _risk_label(row):
        if row["total_noshow"] == 0:
            return "1. Cumplido (0 faltas)"
        if row["total_noshow"] == 1 and row["total_citas"] >= 3:
            return "2. Riesgo Bajo (1 falta ocasional)"
        if row["total_noshow"] == 1:
            return "3. Riesgo Moderado (1 falta)"
        return "4. Riesgo Alto (Reincidente >=2 faltas)"

    pat_hist["risk_segment"] = pat_hist.apply(_risk_label, axis=1)
    dim_patients = patients.merge(
        pat_hist[["patient_id", "total_citas", "total_noshow", "risk_segment"]],
        on="patient_id",
        how="left",
    )

    fact_cols = [
        "appointment_id",
        "patient_id",
        "doctor_id",
        "clinic_id",
        "specialty",
        "scheduled_date",
        "appointment_date",
        "appointment_month",
        "lead_time_days",
        "lead_time_bucket",
        "booking_channel",
        "sms_reminder_sent",
        "appointment_status",
        "is_noshow",
        "consultation_fee_usd",
        "realized_revenue_usd",
        "lost_revenue_usd",
        "patient_satisfaction",
    ]
    fact_appointments = appts[fact_cols].copy()
    fact_appointments["scheduled_date"] = fact_appointments["scheduled_date"].dt.date
    fact_appointments["appointment_date"] = fact_appointments["appointment_date"].dt.date

    # Dimensión Calendario
    dates = pd.date_range(appts["appointment_date"].min(), appts["appointment_date"].max(), freq="D")
    dim_date = pd.DataFrame(
        {
            "date": dates.date,
            "year": dates.year,
            "quarter": "Q" + dates.quarter.astype(str),
            "month": dates.month,
            "month_name": dates.strftime("%b"),
            "year_month": dates.strftime("%Y-%m"),
            "day_of_week": dates.day_name(),
        }
    )

    exports = {
        "fact_appointments": fact_appointments,
        "dim_patients": dim_patients,
        "dim_doctors": doctors,
        "dim_clinics": clinics,
        "dim_date": dim_date,
    }
    saved = {}
    for name, df in exports.items():
        path = os.path.join(output_dir, f"{name}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        saved[name] = path

    return saved
