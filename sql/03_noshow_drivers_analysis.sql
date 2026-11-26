-- =============================================================================
-- 03_noshow_drivers_analysis.sql
-- Factores Determinantes de Inasistencia: Espera (Lead Time), SMS y Aseguramiento
-- =============================================================================

-- @name: noshow_por_tiempo_espera
-- 1. Relación entre Tiempo de Espera (Lead Time), Tasa de No-Show y Satisfacción
SELECT
    lead_time_bucket AS rango_espera,
    COUNT(*) AS total_citas,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_citas,
    SUM(is_noshow) AS citas_noshow,
    ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
    ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd,
    ROUND(AVG(patient_satisfaction), 2) AS satisfaccion_prom
FROM vw_appointments_clean
GROUP BY lead_time_bucket
ORDER BY lead_time_bucket;

-- @name: efectividad_recordatorio_sms
-- 2. Efectividad del Recordatorio SMS por Rango de Espera
SELECT
    lead_time_bucket AS rango_espera,
    CASE WHEN sms_reminder_sent = 1 THEN 'Con SMS' ELSE 'Sin SMS' END AS recordatorio_sms,
    COUNT(*) AS total_citas,
    ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
    ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd
FROM vw_appointments_clean
GROUP BY lead_time_bucket, sms_reminder_sent
ORDER BY lead_time_bucket, sms_reminder_sent;

-- @name: resumen_sms_global
-- 3. Comparativa Global: Con SMS vs Sin SMS
SELECT
    CASE WHEN sms_reminder_sent = 1 THEN 'Con Recordatorio SMS' ELSE 'Sin Recordatorio SMS' END AS grupo_sms,
    COUNT(*) AS total_citas,
    SUM(is_noshow) AS citas_noshow,
    ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
    ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd
FROM vw_appointments_clean
GROUP BY sms_reminder_sent
ORDER BY sms_reminder_sent DESC;

-- @name: noshow_por_aseguramiento
-- 4. Tasa de No-Show por Régimen de Aseguramiento y Canal de Agendamiento
SELECT
    insurance_type AS regimen,
    COUNT(*) AS total_citas,
    SUM(is_noshow) AS citas_noshow,
    ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
    ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd
FROM vw_appointments_clean
GROUP BY insurance_type
ORDER BY tasa_noshow_pct DESC;

-- @name: noshow_por_dia_semana
-- 5. Tasa de No-Show por Día de la Semana
SELECT
    day_of_week_num,
    CASE day_of_week_num
        WHEN 1 THEN '1. Lunes'
        WHEN 2 THEN '2. Martes'
        WHEN 3 THEN '3. Miércoles'
        WHEN 4 THEN '4. Jueves'
        WHEN 5 THEN '5. Viernes'
        WHEN 6 THEN '6. Sábado'
        ELSE '7. Domingo'
    END AS dia_semana,
    COUNT(*) AS total_citas,
    ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
    ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd
FROM vw_appointments_clean
GROUP BY day_of_week_num
ORDER BY day_of_week_num;
