"""
Generador reproducible de datos clínicos relacionales — Sector Salud (Citas Médicas)

Modela la operación ambulatoria de una red de 6 clínicas / IPS durante 2024–2025
(~50,000 citas médicas, 16,000 pacientes, 72 médicos, 10 especialidades) con patrones
estadísticos realistas de inasistencia (No-Show):
- Mayor tiempo de espera entre agendamiento y cita incrementa significativamente el No-Show.
- Los recordatorios por SMS reducen la inasistencia en ~35–40%.
- Diferencias por grupo etario, especialidad, canal de agendamiento y día de la semana.
"""

import os
import numpy as np
import pandas as pd


def generate_healthcare_dataset(
    output_dir: str = "data/raw",
    n_appointments: int = 50_000,
    n_patients: int = 16_000,
    seed: int = 42,
) -> dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    rng = np.random.default_rng(seed)

    # -------------------------------------------------------------------------
    # 1. Dimensión Sedes / Clínicas (6 sedes en Colombia)
    # -------------------------------------------------------------------------
    clinics = pd.DataFrame(
        [
            ("CL-01", "Sede Norte", "Cali", "Alta Complejidad", 18),
            ("CL-02", "Sede Sur", "Cali", "Mediana Complejidad", 14),
            ("CL-03", "Sede Centro", "Cali", "Consulta Externa", 12),
            ("CL-04", "Sede Chapinero", "Bogotá", "Alta Complejidad", 20),
            ("CL-05", "Sede Poblado", "Medellín", "Alta Complejidad", 16),
            ("CL-06", "Sede Prado", "Barranquilla", "Mediana Complejidad", 12),
        ],
        columns=["clinic_id", "clinic_name", "city", "complexity_level", "consultorios"],
    )

    # -------------------------------------------------------------------------
    # 2. Dimensión Especialidades y Médicos
    # -------------------------------------------------------------------------
    specialties = [
        # (nombre, peso_demanda, tarifa_usd, prob_base_noshow)
        ("Medicina General", 0.24, 38.0, 0.22),
        ("Pediatría", 0.12, 52.0, 0.16),
        ("Ginecología", 0.10, 68.0, 0.18),
        ("Cardiología", 0.08, 95.0, 0.13),
        ("Dermatología", 0.08, 72.0, 0.24),
        ("Ortopedia", 0.09, 82.0, 0.19),
        ("Odontología", 0.09, 55.0, 0.27),
        ("Psicología", 0.08, 60.0, 0.29),
        ("Oftalmología", 0.07, 78.0, 0.17),
        ("Neurología", 0.05, 110.0, 0.14),
    ]
    spec_names = [s[0] for s in specialties]
    spec_weights = np.array([s[1] for s in specialties])
    spec_weights = spec_weights / spec_weights.sum()
    spec_fee = {s[0]: s[2] for s in specialties}
    spec_base_ns = {s[0]: s[3] for s in specialties}

    doctors_rows = []
    doc_idx = 1
    for spec, _, fee, _ in specialties:
        n_docs = max(4, int(round(72 * spec_weights[spec_names.index(spec)])))
        for _ in range(n_docs):
            clinic_id = rng.choice(clinics["clinic_id"].values)
            doctors_rows.append(
                (f"DR-{doc_idx:03d}", f"Dr(a). Especialista {doc_idx:03d}", spec, clinic_id, fee)
            )
            doc_idx += 1
    doctors = pd.DataFrame(
        doctors_rows,
        columns=["doctor_id", "doctor_name", "specialty", "primary_clinic_id", "base_fee_usd"],
    )

    # -------------------------------------------------------------------------
    # 3. Dimensión Pacientes
    # -------------------------------------------------------------------------
    patient_ids = [f"PAT-{i:05d}" for i in range(1, n_patients + 1)]
    genders = rng.choice(["Femenino", "Masculino"], size=n_patients, p=[0.56, 0.44])
    ages = np.clip(rng.normal(loc=41, scale=18, size=n_patients).astype(int), 1, 90)
    insurances = rng.choice(
        ["Contributivo", "Subsidiado", "Medicina Prepagada", "Particular"],
        size=n_patients,
        p=[0.52, 0.24, 0.16, 0.08],
    )
    chronic_flag = (rng.random(n_patients) < np.where(ages >= 50, 0.42, 0.12)).astype(int)
    # Propensión intrínseca individual del paciente (para simular reincidentes realistas)
    patient_propensity = rng.normal(loc=0.0, scale=0.45, size=n_patients)

    patients = pd.DataFrame(
        {
            "patient_id": patient_ids,
            "gender": genders,
            "age": ages,
            "insurance_type": insurances,
            "is_chronic": chronic_flag,
        }
    )

    # -------------------------------------------------------------------------
    # 4. Tabla de Hechos: Citas Médicas (2024-01-01 a 2025-06-30 — 18 meses)
    # -------------------------------------------------------------------------
    # Selección de pacientes con distribución heterogénea (crónicos visitan más)
    p_weights = np.where(chronic_flag == 1, 2.4, 1.0)
    p_weights = p_weights / p_weights.sum()
    p_indices = rng.choice(n_patients, size=n_appointments, p=p_weights)

    # Fechas de cita (lunes a sábado, con ligera estacionalidad)
    all_dates = pd.date_range("2024-01-02", "2025-06-30", freq="D")
    valid_dates = all_dates[all_dates.dayofweek < 6]  # Lunes(0) a Sábado(5)
    day_weights = np.where(valid_dates.dayofweek == 5, 0.55, 1.0)
    day_weights = day_weights / day_weights.sum()
    appt_dates = pd.to_datetime(rng.choice(valid_dates, size=n_appointments, p=day_weights))

    # Tiempo de espera (lead_time_days) entre agendamiento y cita
    lead_days = np.clip(rng.gamma(shape=1.6, scale=7.0, size=n_appointments).astype(int), 0, 60)
    sched_dates = appt_dates - pd.to_timedelta(lead_days, unit="D")

    # Especialidad y médico coherente
    chosen_specs = rng.choice(spec_names, size=n_appointments, p=spec_weights)
    spec_to_docs = doctors.groupby("specialty")["doctor_id"].apply(list).to_dict()
    doc_to_clinic = doctors.set_index("doctor_id")["primary_clinic_id"].to_dict()

    chosen_doctors = [rng.choice(spec_to_docs[sp]) for sp in chosen_specs]
    chosen_clinics = [doc_to_clinic[d] for d in chosen_doctors]

    channels = rng.choice(
        ["App Móvil", "Portal Web", "Teléfono", "Presencial"],
        size=n_appointments,
        p=[0.34, 0.26, 0.28, 0.12],
    )

    # Recordatorio SMS enviado (62% de citas, menor en citas mismo día)
    sms_prob = np.where(lead_days == 0, 0.15, 0.65)
    sms_sent = (rng.random(n_appointments) < sms_prob).astype(int)

    # Tarifa consulta (ligera variación por aseguradora)
    ins_arr = insurances[p_indices]
    ins_mult = np.where(
        ins_arr == "Medicina Prepagada",
        1.25,
        np.where(ins_arr == "Particular", 1.35, np.where(ins_arr == "Subsidiado", 0.80, 1.0)),
    )
    fees = np.round(np.array([spec_fee[sp] for sp in chosen_specs]) * ins_mult, 2)

    # -------------------------------------------------------------------------
    # Modelo logístico realista para probabilidad de No-Show
    # -------------------------------------------------------------------------
    base_ns = np.array([spec_base_ns[sp] for sp in chosen_specs])
    base_logit = np.log(base_ns / (1.0 - base_ns))

    age_arr = ages[p_indices]
    chronic_arr = chronic_flag[p_indices]
    dow = appt_dates.dayofweek.values  # 0=Lun .. 5=Sáb

    logit = (
        base_logit
        + patient_propensity[p_indices]
        # Lead time: mayor espera -> mayor inasistencia
        + np.where(lead_days == 0, -1.15, 0.0)
        + np.where((lead_days >= 1) & (lead_days <= 3), -0.35, 0.0)
        + np.where((lead_days >= 8) & (lead_days <= 14), 0.35, 0.0)
        + np.where((lead_days >= 15) & (lead_days <= 30), 0.72, 0.0)
        + np.where(lead_days > 30, 1.05, 0.0)
        # Efecto protector fuerte del SMS
        + np.where(sms_sent == 1, -0.58, 0.0)
        # Edad: jóvenes 18-30 faltan más; adultos mayores <65+ menos
        + np.where((age_arr >= 18) & (age_arr <= 30), 0.36, 0.0)
        + np.where(age_arr >= 60, -0.28, 0.0)
        # Crónicos suelen ser más cumplidos en controles
        + np.where(chronic_arr == 1, -0.22, 0.0)
        # Régimen aseguramiento
        + np.where(ins_arr == "Subsidiado", 0.28, 0.0)
        + np.where(ins_arr == "Particular", -0.45, 0.0)
        + np.where(ins_arr == "Medicina Prepagada", -0.20, 0.0)
        # Día de semana: lunes y viernes/sábado mayor riesgo
        + np.where(dow == 0, 0.16, 0.0)
        + np.where(dow >= 4, 0.22, 0.0)
        # Canal agendamiento
        + np.where(channels == "Teléfono", 0.18, 0.0)
        + np.where(channels == "App Móvil", -0.15, 0.0)
    )

    prob_noshow = 1.0 / (1.0 + np.exp(-logit))
    is_noshow = (rng.random(n_appointments) < prob_noshow).astype(int)

    # Cancelaciones previas (6% de las que no fueron no-show) para realismo operacional
    is_cancelled = ((is_noshow == 0) & (rng.random(n_appointments) < 0.06)).astype(int)
    status = np.where(is_noshow == 1, "No-Show", np.where(is_cancelled == 1, "Cancelada", "Atendida"))

    # Satisfacción del paciente (solo para citas atendidas, 1-5)
    sat_mean = np.where(lead_days <= 7, 4.45, np.where(lead_days <= 14, 4.10, 3.65))
    sat_raw = np.clip(np.round(rng.normal(sat_mean, 0.75)), 1, 5)
    satisfaction = np.where(status == "Atendida", sat_raw, np.nan)

    # Introducir ~0.4% de nulos realistas en canal y 80 duplicados controlados para demostrar limpieza ETL
    channels_dirty = channels.astype(object)
    null_idx = rng.choice(n_appointments, size=180, replace=False)
    channels_dirty[null_idx] = None

    appointments = pd.DataFrame(
        {
            "appointment_id": [f"APT-{i:06d}" for i in range(1, n_appointments + 1)],
            "patient_id": [patient_ids[idx] for idx in p_indices],
            "doctor_id": chosen_doctors,
            "clinic_id": chosen_clinics,
            "specialty": chosen_specs,
            "scheduled_date": sched_dates.strftime("%Y-%m-%d"),
            "appointment_date": appt_dates.strftime("%Y-%m-%d"),
            "lead_time_days": lead_days,
            "booking_channel": channels_dirty,
            "sms_reminder_sent": sms_sent,
            "appointment_status": status,
            "consultation_fee_usd": fees,
            "patient_satisfaction": satisfaction,
        }
    )

    # Añadir 75 registros duplicados para demostrar detección y limpieza en SQL/Python
    dup_sample = appointments.sample(75, random_state=seed)
    appointments = pd.concat([appointments, dup_sample], ignore_index=True)

    # Guardar archivos
    files = {
        "clinics": clinics,
        "doctors": doctors,
        "patients": patients,
        "appointments": appointments,
    }
    saved = {}
    for name, df in files.items():
        path = os.path.join(output_dir, f"{name}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        saved[name] = path

    return saved


if __name__ == "__main__":
    paths = generate_healthcare_dataset()
    for name, p in paths.items():
        print(f"Generado: {name} -> {p}")
