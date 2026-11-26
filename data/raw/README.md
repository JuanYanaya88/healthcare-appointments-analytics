# Datos Crudos — Red Ambulatoria del Sector Salud (Simulación Reproducible)

Los archivos CSV crudos (`clinics.csv`, `doctors.csv`, `patients.csv`, `appointments.csv`) se generan automáticamente de forma determinista (`seed=42`) al ejecutar:

```bash
python run_pipeline.py
```

El generador crea un modelo relacional realista de **50,000 citas médicas** (con 75 duplicados controlados y 180 valores nulos en canal de agendamiento para demostrar el proceso de limpieza ETL en SQL y Python).
