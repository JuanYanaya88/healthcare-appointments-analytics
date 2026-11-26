import os
import sys
import pandas as pd
import plotly.express as px  # type: ignore
import streamlit as st  # type: ignore

sys.path.append(os.getcwd())

from src.analytics_etl import load_and_clean_appointments
from src.generate_dataset import generate_healthcare_dataset

st.set_page_config(
    page_title="Healthcare No-Show Analytics",
    page_icon="🏥",
    layout="wide",
)


@st.cache_data
def get_data():
    if not os.path.exists("data/raw/appointments.csv"):
        generate_healthcare_dataset()
    tables = load_and_clean_appointments(verbose=False)
    return tables["merged"]


df = get_data()

# --- Filtros Sidebar ---
st.sidebar.title("Filtros Clínicos")
cities = ["Todas"] + sorted(df["city"].unique().tolist())
sel_city = st.sidebar.selectbox("Ciudad", cities)

specs = ["Todas"] + sorted(df["specialty"].unique().tolist())
sel_spec = st.sidebar.selectbox("Especialidad", specs)

regimes = ["Todos"] + sorted(df["insurance_type"].unique().tolist())
sel_reg = st.sidebar.selectbox("Régimen de Aseguramiento", regimes)

df_f = df.copy()
if sel_city != "Todas":
    df_f = df_f[df_f["city"] == sel_city]
if sel_spec != "Todas":
    df_f = df_f[df_f["specialty"] == sel_spec]
if sel_reg != "Todos":
    df_f = df_f[df_f["insurance_type"] == sel_reg]

# --- Header ---
st.title("🏥 Healthcare Appointments & No-Show Analytics")
st.markdown(
    "Diagnóstico operacional de **inasistencia a citas médicas, impacto financiero y efectividad de recordatorios SMS**."
)

if df_f.empty:
    st.warning("No existen citas para los filtros seleccionados.")
    st.stop()

# --- KPIs ---
total_citas = len(df_f)
noshow_rate = df_f["is_noshow"].mean() * 100
lost_rev = df_f["lost_revenue_usd"].sum()
avg_wait = df_f["lead_time_days"].mean()
avg_sat = df_f["patient_satisfaction"].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Citas Efectivas", f"{total_citas:,}")
c2.metric("Tasa de No-Show", f"{noshow_rate:.1f}%")
c3.metric("Ingreso Perdido", f"${lost_rev:,.0f} USD")
c4.metric("Espera Promedio", f"{avg_wait:.1f} días")
c5.metric("Satisfacción", f"{avg_sat:.2f} / 5.0 ★")

# --- Visualizaciones ---
tab1, tab2, tab3 = st.tabs(
    ["📊 Especialidades y Sedes", "⏱️ Tiempo de Espera y SMS", "🩺 Perfil del Paciente"]
)

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        sp = (
            df_f.groupby("specialty", as_index=False)
            .agg(ingreso_perdido=("lost_revenue_usd", "sum"), tasa_noshow=("is_noshow", lambda s: s.mean() * 100))
            .sort_values("ingreso_perdido", ascending=True)
        )
        fig1 = px.bar(
            sp,
            x="ingreso_perdido",
            y="specialty",
            orientation="h",
            color="tasa_noshow",
            color_continuous_scale="Tealrose",
            title="Ingreso Perdido por Especialidad (USD)",
            labels={"ingreso_perdido": "Ingreso Perdido (USD)", "specialty": "Especialidad", "tasa_noshow": "No-Show %"},
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        monthly = (
            df_f.groupby("appointment_month", as_index=False)
            .agg(tasa_noshow=("is_noshow", lambda s: s.mean() * 100), perdida=("lost_revenue_usd", "sum"))
        )
        fig2 = px.line(
            monthly,
            x="appointment_month",
            y="tasa_noshow",
            markers=True,
            title="Evolución Mensual de la Tasa de No-Show (%)",
            labels={"appointment_month": "Mes", "tasa_noshow": "Tasa No-Show (%)"},
        )
        fig2.update_traces(line_color="#0F4C5C", marker_color="#E76F51")
        st.plotly_chart(fig2, use_container_width=True)

with tab2:
    sms_lt = (
        df_f.groupby(["lead_time_bucket", "sms_reminder_sent"], as_index=False)["is_noshow"]
        .mean()
        .assign(tasa_noshow=lambda d: d["is_noshow"] * 100)
    )
    sms_lt["SMS"] = sms_lt["sms_reminder_sent"].map({0: "Sin SMS", 1: "Con SMS"})
    fig3 = px.bar(
        sms_lt.sort_values("lead_time_bucket"),
        x="lead_time_bucket",
        y="tasa_noshow",
        color="SMS",
        barmode="group",
        color_discrete_map={"Sin SMS": "#E76F51", "Con SMS": "#2A9D8F"},
        title="Tasa de No-Show según Tiempo de Espera y Envío de SMS",
        labels={"lead_time_bucket": "Rango de Espera", "tasa_noshow": "Tasa No-Show (%)"},
    )
    st.plotly_chart(fig3, use_container_width=True)

with tab3:
    col_a, col_b = st.columns(2)
    with col_a:
        age_df = (
            df_f.groupby("age_group", as_index=False)["is_noshow"]
            .mean()
            .assign(tasa_noshow=lambda d: d["is_noshow"] * 100)
            .sort_values("age_group")
        )
        fig4 = px.bar(
            age_df,
            x="age_group",
            y="tasa_noshow",
            color="tasa_noshow",
            color_continuous_scale="Blues",
            title="Tasa de No-Show por Grupo Etario",
            labels={"age_group": "Grupo Etario", "tasa_noshow": "Tasa No-Show (%)"},
        )
        st.plotly_chart(fig4, use_container_width=True)

    with col_b:
        reg_df = (
            df_f.groupby("insurance_type", as_index=False)
            .agg(tasa_noshow=("is_noshow", lambda s: s.mean() * 100), perdida=("lost_revenue_usd", "sum"))
            .sort_values("tasa_noshow", ascending=False)
        )
        fig5 = px.bar(
            reg_df,
            x="insurance_type",
            y="tasa_noshow",
            text=reg_df["tasa_noshow"].round(1).astype(str) + "%",
            color_discrete_sequence=["#1E6091"],
            title="Tasa de No-Show por Régimen de Aseguramiento",
            labels={"insurance_type": "Régimen", "tasa_noshow": "Tasa No-Show (%)"},
        )
        st.plotly_chart(fig5, use_container_width=True)
