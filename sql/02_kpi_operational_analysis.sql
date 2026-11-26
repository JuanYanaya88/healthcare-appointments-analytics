-- =============================================================================
-- 02_kpi_operational_analysis.sql
-- KPIs Ejecutivos, Evolución Mensual (LAG) e Impacto Financiero por Especialidad
-- =============================================================================

-- @name: kpi_resumen_clinico
-- 1. KPIs Globales de Operación Ambulatoria (Citas Efectivas: Atendidas vs No-Show)
SELECT
    COUNT(*) AS total_citas_efectivas,
    COUNT(DISTINCT patient_id) AS pacientes_unicos,
    SUM(is_attended) AS citas_atendidas,
    SUM(is_noshow) AS citas_noshow,
    ROUND(100.0 * SUM(is_attended) / COUNT(*), 2) AS tasa_asistencia_pct,
    ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
    ROUND(SUM(realized_revenue_usd), 2) AS ingreso_realizado_usd,
    ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd,
    ROUND(AVG(lead_time_days), 1) AS espera_promedio_dias,
    ROUND(AVG(patient_satisfaction), 2) AS satisfaccion_promedio
FROM vw_appointments_clean;

-- @name: tendencia_mensual_noshow
-- 2. Evolución Mensual de Citas, Tasa de No-Show e Ingreso Perdido + Variación MoM (LAG)
WITH monthly AS (
    SELECT
        appointment_month,
        COUNT(*) AS total_citas,
        SUM(is_attended) AS atendidas,
        SUM(is_noshow) AS noshow,
        ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
        ROUND(SUM(realized_revenue_usd), 2) AS ingreso_realizado_usd,
        ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd,
        ROUND(AVG(lead_time_days), 1) AS espera_prom_dias
    FROM vw_appointments_clean
    GROUP BY appointment_month
)
SELECT
    appointment_month,
    total_citas,
    atendidas,
    noshow,
    tasa_noshow_pct,
    ingreso_realizado_usd,
    ingreso_perdido_usd,
    espera_prom_dias,
    ROUND(
        tasa_noshow_pct - LAG(tasa_noshow_pct) OVER (ORDER BY appointment_month),
        2
    ) AS variacion_noshow_pp
FROM monthly
ORDER BY appointment_month;

-- @name: especialidades_impacto_financiero
-- 3. Ranking de Especialidades por Ingreso Perdido y % Acumulado (Window Functions)
WITH spec_agg AS (
    SELECT
        specialty AS especialidad,
        COUNT(*) AS total_citas,
        SUM(is_noshow) AS citas_noshow,
        ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
        ROUND(AVG(consultation_fee_usd), 2) AS tarifa_prom_usd,
        ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd,
        ROUND(AVG(lead_time_days), 1) AS espera_prom_dias,
        ROUND(AVG(patient_satisfaction), 2) AS satisfaccion_prom
    FROM vw_appointments_clean
    GROUP BY specialty
)
SELECT
    *,
    ROUND(ingreso_perdido_usd * 100.0 / SUM(ingreso_perdido_usd) OVER (), 2) AS pct_perdida_total,
    ROUND(
        SUM(ingreso_perdido_usd) OVER (ORDER BY ingreso_perdido_usd DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        * 100.0 / SUM(ingreso_perdido_usd) OVER (),
        2
    ) AS pareto_perdida_acum_pct
FROM spec_agg
ORDER BY ingreso_perdido_usd DESC;

-- @name: desempeno_por_sede
-- 4. Desempeño Operacional por Sede / Clínica
SELECT
    clinic_name AS sede,
    city AS ciudad,
    complexity_level AS complejidad,
    COUNT(*) AS total_citas,
    SUM(is_noshow) AS citas_noshow,
    ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
    ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd,
    ROUND(AVG(patient_satisfaction), 2) AS satisfaccion_prom
FROM vw_appointments_clean
GROUP BY clinic_name, city, complexity_level
ORDER BY ingreso_perdido_usd DESC;
