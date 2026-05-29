# -*- coding: utf-8 -*-
"""
Created on Wed Apr 15 13:57:21 2026

@author: glori
"""

import pandas as pd
import numpy as np

path = "analisis_metricas_y_flujos(cp1).xlsx"

def quitar_total(df, col="ccaa"):
    if col in df.columns:
        return df[df[col].astype(str).str.strip().str.upper() != "TOTAL"].copy()
    return df.copy()

df_global = pd.read_excel(path, sheet_name="metricas_globales")
df_origen = pd.read_excel(path, sheet_name="resumen_por_origen")
df_flujos = pd.read_excel(path, sheet_name="flujos_i_k_mapa")
df_mov = pd.read_excel(path, sheet_name="movimientos_origen")
df_dest = pd.read_excel(path, sheet_name="capacidad_destinos")
df_obj = pd.read_excel(path, sheet_name="objetivos_resumen")

df_origen = quitar_total(df_origen, col="ccaa_origen")
df_flujos = quitar_total(df_flujos, col="ccaa_origen")
df_mov = quitar_total(df_mov, col="ccaa_origen")
df_dest = quitar_total(df_dest, col="ccaa")

kpis_globales = pd.DataFrame({
    "Indicador": [
        "Total menores",
        "% preferencias cumplidas",
        "% movidos",
        "% no movidos",
        "% movidos y preferencia cumplida",
        "% movidos sin preferencia cumplida",
        "% no movidos y preferencia cumplida",
        "% no movidos y sin preferencia cumplida",
        "f1 (inequidad territorial)",
        "f2 (coste)",
        "f3 (bienestar)"
    ],
    "Valor": [
        df_global.loc[0, "N_total"],
        df_global.loc[0, "pct_preferencia_cumplida"],
        df_global.loc[0, "pct_movidos"],
        df_global.loc[0, "pct_no_movidos"],
        df_global.loc[0, "pct_movidos_y_preferencia_cumplida"],
        df_global.loc[0, "pct_movidos_y_no_preferencia"],
        df_global.loc[0, "pct_no_movidos_y_preferencia_cumplida"],
        df_global.loc[0, "pct_no_movidos_y_no_preferencia"],
        df_obj.loc[0, "f1"],
        df_obj.loc[0, "f2"],
        df_obj.loc[0, "f3"],
    ]
})

print(kpis_globales)

df_dest_kpi = quitar_total(df_dest, col="ccaa")
df_flujos_kpi = quitar_total(df_flujos, col="ccaa_origen")

dashboard_solucion = pd.DataFrame({
    "KPI": [
        "Total menores",
        "% preferencias cumplidas",
        "% movidos",
        "Nº centros abiertos",
        "Menores en emergencia",
        "% umbral emergencia total ocupado",
        "Nº destinos utilizados",
        "f1",
        "f2",
        "f3"
    ],
    "Valor": [
        df_global.loc[0, "N_total"],
        df_global.loc[0, "pct_preferencia_cumplida"],
        df_global.loc[0, "pct_movidos"],
        df_dest_kpi["B_k"].sum(),
        df_dest_kpi["Se_k"].sum(),
        100 * df_dest_kpi["Se_k"].sum() / df_dest_kpi["Umbral_emergencia"].sum()
        if df_dest_kpi["Umbral_emergencia"].sum() > 0 else 0.0,
        df_flujos_kpi["ccaa_dest"].nunique(),
        df_obj.loc[0, "f1"],
        df_obj.loc[0, "f2"],
        df_obj.loc[0, "f3"]
    ]
})

print(dashboard_solucion)

