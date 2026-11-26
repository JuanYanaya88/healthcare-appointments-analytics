-- =============================================================================
-- 04_patient_risk_segmentation.sql
-- Segmentación de Riesgo de Inasistencia por Paciente y Grupo Etario (CTEs)
-- =============================================================================

-- @name: segmentacion_riesgo_pacientes
-- 1. Clasificación de Pacientes por Nivel de Riesgo de No-Show
WITH patient_history AS (
    SELECT
        patient_id,
        COUNT(*) AS total_citas,
        SUM(is_noshow) AS total_noshow,
        ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_paciente_pct,
        ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd
    FROM vw_appointments_clean
    GROUP BY patient_id
),
classified AS (
    SELECT
        *,
        CASE
            WHEN total_noshow = 0 THEN '1. Cumplido (0 faltas)'
            WHEN total_noshow = 1 AND total_citas >= 3 THEN '2. Riesgo Bajo (1 falta ocasional)'
            WHEN total_noshow = 1 THEN '3. Riesgo Moderado (1 falta)'
            ELSE '4. Riesgo Alto (Reincidente >=2 faltas)'
        END AS segmento_riesgo
    FROM patient_history
)
SELECT
    segmento_riesgo,
    COUNT(*) AS pacientes,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_pacientes,
    SUM(total_citas) AS citas_totales,
    SUM(total_noshow) AS citas_noshow,
    ROUND(SUM(total_noshow) * 100.0 / SUM(SUM(total_noshow)) OVER (), 2) AS pct_del_total_noshow,
    ROUND(SUM(ingreso_perdido_usd), 2) AS ingreso_perdido_usd
FROM classified
GROUP BY segmento_riesgo
ORDER BY segmento_riesgo;

-- @name: noshow_por_grupo_etario
-- 2. Inasistencia por Grupo Etario
SELECT
    age_group AS grupo_etario,
    COUNT(*) AS total_citas,
    SUM(is_noshow) AS citas_noshow,
    ROUND(100.0 * SUM(is_noshow) / COUNT(*), 2) AS tasa_noshow_pct,
    ROUND(SUM(lost_revenue_usd), 2) AS ingreso_perdido_usd
FROM vw_appointments_clean
GROUP BY age_group
ORDER BY age_group;
