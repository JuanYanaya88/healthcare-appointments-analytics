-- =============================================================================
-- 01_schema_and_views.sql
-- Capa Analítica (Vistas SQL) — Eficiencia Clínica y No-Show en Citas Médicas
-- Autor: Juan David Yanayaco | Portafolio Data Analyst
-- =============================================================================

-- 1. Vista deduplicada de citas médicas válidas (excluye canceladas anticipadamente)
-- Hallazgo de calidad de datos: se detectan 75 registros duplicados por appointment_id
-- y 180 nulos en booking_channel que se normalizan a 'No Registrado'.
DROP VIEW IF EXISTS vw_appointments_dedup;
CREATE VIEW vw_appointments_dedup AS
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY appointment_id ORDER BY appointment_date) AS rn
    FROM appointments
)
SELECT
    appointment_id,
    patient_id,
    doctor_id,
    clinic_id,
    specialty,
    scheduled_date,
    appointment_date,
    STRFTIME('%Y-%m', appointment_date) AS appointment_month,
    CAST(STRFTIME('%w', appointment_date) AS INTEGER) AS day_of_week_num,
    lead_time_days,
    COALESCE(NULLIF(TRIM(booking_channel), ''), 'No Registrado') AS booking_channel,
    sms_reminder_sent,
    appointment_status,
    CASE WHEN appointment_status = 'No-Show' THEN 1 ELSE 0 END AS is_noshow,
    CASE WHEN appointment_status = 'Atendida' THEN 1 ELSE 0 END AS is_attended,
    consultation_fee_usd,
    CASE WHEN appointment_status = 'No-Show' THEN consultation_fee_usd ELSE 0.0 END AS lost_revenue_usd,
    CASE WHEN appointment_status = 'Atendida' THEN consultation_fee_usd ELSE 0.0 END AS realized_revenue_usd,
    patient_satisfaction
FROM ranked
WHERE rn = 1;

-- 2. Vista maestra enriquecida (Capa Gold) para análisis operacional de No-Show
-- Excluye citas canceladas anticipadamente (cupo liberado) para medir asistencia real vs inasistencia.
DROP VIEW IF EXISTS vw_appointments_clean;
CREATE VIEW vw_appointments_clean AS
SELECT
    a.*,
    p.gender,
    p.age,
    CASE
        WHEN p.age < 18 THEN '1. Menor (<18)'
        WHEN p.age <= 30 THEN '2. Joven (18-30)'
        WHEN p.age <= 45 THEN '3. Adulto (31-45)'
        WHEN p.age <= 60 THEN '4. Adulto Mayor (46-60)'
        ELSE '5. Senior (>60)'
    END AS age_group,
    p.insurance_type,
    p.is_chronic,
    c.clinic_name,
    c.city,
    c.complexity_level,
    d.doctor_name,
    CASE
        WHEN a.lead_time_days = 0 THEN '1. Mismo día (0d)'
        WHEN a.lead_time_days <= 3 THEN '2. Corta (1-3d)'
        WHEN a.lead_time_days <= 7 THEN '3. Media (4-7d)'
        WHEN a.lead_time_days <= 14 THEN '4. Alta (8-14d)'
        WHEN a.lead_time_days <= 30 THEN '5. Muy Alta (15-30d)'
        ELSE '6. Crítica (>30d)'
    END AS lead_time_bucket
FROM vw_appointments_dedup a
INNER JOIN patients p ON a.patient_id = p.patient_id
INNER JOIN clinics c ON a.clinic_id = c.clinic_id
INNER JOIN doctors d ON a.doctor_id = d.doctor_id
WHERE a.appointment_status IN ('Atendida', 'No-Show');
