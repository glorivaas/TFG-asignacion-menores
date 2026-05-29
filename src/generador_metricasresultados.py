# -*- coding: utf-8 -*-
"""
Created on Tue Mar 10 20:56:04 2026

@author: glori
"""

import pandas as pd
import numpy as np
import math

PATH_X = "resultados_cp/cp_direct_L2_Xpos2.csv"
PATH_XRES = "resultados_cp/cp_direct_L2_Xres_pos2.csv"
PATH_XNEW = "resultados_cp/cp_direct_L2_Xnew_pos2.csv"
PATH_B = "resultados_cp/cp_direct_L2_B2.csv"
PATH_SUMMARY = "resultados_cp/cp_direct_L2_summary2.csv"

df_res = pd.read_excel("plazasCCAA.xlsx")
df_res = df_res.rename(columns={
    "Plazas totales": "plazas_totales",
    "Comunidad Autónoma": "ccaa"
})

# solución concreta
SOL_ID = "cp_direct_L2"

# comunidad concreta para tabla de movimientos origen -> destino
COMUNIDAD_ORIGEN = "Canarias"
OUTPUT_EXCEL = "analisis_metricas_y_flujos(cpL2version2).xlsx"

def safe_pct(num, den):
    return 100.0 * num / den if den != 0 else 0.0


def normalizar_xpos(df_x):
    df = df_x.copy()
    df["X_total"] = pd.to_numeric(df["X"], errors="coerce").fillna(0.0)
    df["X_res"] = 0.0
    df["X_new"] = 0.0
    return df[
        ["sol_id", "i", "j", "k", "ccaa_origen", "ccaa_pref", "ccaa_dest", "X_total", "X_res", "X_new"]
    ]


def combinar_xres_xnew(df_res, df_new):
    claves = ["sol_id", "i", "j", "k", "ccaa_origen", "ccaa_pref", "ccaa_dest"]

    df_res2 = df_res.copy()
    df_new2 = df_new.copy()

    df_res2["X_res"] = pd.to_numeric(df_res2["X_res"], errors="coerce").fillna(0.0)
    df_new2["X_new"] = pd.to_numeric(df_new2["X_new"], errors="coerce").fillna(0.0)

    df_merge = pd.merge(
        df_res2,
        df_new2,
        on=claves,
        how="outer"
    )

    df_merge["X_res"] = df_merge["X_res"].fillna(0.0)
    df_merge["X_new"] = df_merge["X_new"].fillna(0.0)
    df_merge["X_total"] = df_merge["X_res"] + df_merge["X_new"]

    return df_merge[
        ["sol_id", "i", "j", "k", "ccaa_origen", "ccaa_pref", "ccaa_dest", "X_total", "X_res", "X_new"]
    ]


def construir_asignaciones_totales(path_x, path_xres, path_xnew):
    """
    Construye la tabla total de asignaciones:
    - comunidades normales desde Xpos
    - comunidades receptoras desde Xres + Xnew
    """
    df_x = pd.read_csv(path_x)
    df_xres = pd.read_csv(path_xres)
    df_xnew = pd.read_csv(path_xnew)

    df_normales = normalizar_xpos(df_x)
    df_especiales = combinar_xres_xnew(df_xres, df_xnew)

    df_total = pd.concat([df_normales, df_especiales], ignore_index=True)

    claves = ["sol_id", "i", "j", "k", "ccaa_origen", "ccaa_pref", "ccaa_dest"]
    df_total = (
        df_total
        .groupby(claves, as_index=False)[["X_total", "X_res", "X_new"]]
        .sum()
    )

    df_total = df_total[df_total["X_total"] > 1e-9].copy()

    return df_total


def filtrar_solucion(df, sol_id=None):
    if sol_id is None:
        return df.copy()
    return df[df["sol_id"] == sol_id].copy()


def metricas_globales_por_solucion(df_sol):
    total = df_sol["X_total"].sum()

    pref_cumplida = df_sol.loc[df_sol["j"] == df_sol["k"], "X_total"].sum()
    movidos = df_sol.loc[df_sol["i"] != df_sol["k"], "X_total"].sum()
    no_movidos = df_sol.loc[df_sol["i"] == df_sol["k"], "X_total"].sum()

    movidos_y_pref = df_sol.loc[(df_sol["i"] != df_sol["k"]) & (df_sol["j"] == df_sol["k"]), "X_total"].sum()
    movidos_y_no_pref = df_sol.loc[(df_sol["i"] != df_sol["k"]) & (df_sol["j"] != df_sol["k"]), "X_total"].sum()
    no_movidos_y_pref = df_sol.loc[(df_sol["i"] == df_sol["k"]) & (df_sol["j"] == df_sol["k"]), "X_total"].sum()
    no_movidos_y_no_pref = df_sol.loc[(df_sol["i"] == df_sol["k"]) & (df_sol["j"] != df_sol["k"]), "X_total"].sum()

    return {
        "sol_id": df_sol["sol_id"].iloc[0],
        "N_total": total,
        "menores_preferencia_cumplida": pref_cumplida,
        "pct_preferencia_cumplida": safe_pct(pref_cumplida, total),
        "menores_movidos": movidos,
        "pct_movidos": safe_pct(movidos, total),
        "menores_no_movidos": no_movidos,
        "pct_no_movidos": safe_pct(no_movidos, total),
        "movidos_y_preferencia_cumplida": movidos_y_pref,
        "pct_movidos_y_preferencia_cumplida": safe_pct(movidos_y_pref, total),
        "movidos_y_no_preferencia": movidos_y_no_pref,
        "pct_movidos_y_no_preferencia": safe_pct(movidos_y_no_pref, total),
        "no_movidos_y_preferencia_cumplida": no_movidos_y_pref,
        "pct_no_movidos_y_preferencia_cumplida": safe_pct(no_movidos_y_pref, total),
        "no_movidos_y_no_preferencia": no_movidos_y_no_pref,
        "pct_no_movidos_y_no_preferencia": safe_pct(no_movidos_y_no_pref, total),
    }


def metricas_todas_las_soluciones(df):
    filas = []
    for sol_id, grp in df.groupby("sol_id", sort=False):
        filas.append(metricas_globales_por_solucion(grp))
    return pd.DataFrame(filas)


def resumen_por_origen(df_sol):
    filas = []

    for origen, grp in df_sol.groupby("ccaa_origen", sort=False):
        total = grp["X_total"].sum()
        pref = grp.loc[grp["j"] == grp["k"], "X_total"].sum()
        mov = grp.loc[grp["i"] != grp["k"], "X_total"].sum()

        filas.append({
            "sol_id": grp["sol_id"].iloc[0],
            "ccaa_origen": origen,
            "N_origen": total,
            "menores_preferencia_cumplida": pref,
            "pct_preferencia_cumplida": safe_pct(pref, total),
            "menores_movidos": mov,
            "pct_movidos": safe_pct(mov, total),
            "menores_no_movidos": total - mov,
            "pct_no_movidos": safe_pct(total - mov, total),
        })

    return pd.DataFrame(filas).sort_values(["sol_id", "N_origen"], ascending=[True, False])


def flujos_i_k(df_sol):
    df = (
        df_sol.groupby(["sol_id", "i", "k", "ccaa_origen", "ccaa_dest"], as_index=False)["X_total"]
        .sum()
        .rename(columns={"X_total": "flujo"})
    )

    total_origen = (
        df.groupby(["sol_id", "i"], as_index=False)["flujo"]
        .sum()
        .rename(columns={"flujo": "total_desde_origen"})
    )

    df = df.merge(total_origen, on=["sol_id", "i"], how="left")
    df["pct_sobre_origen"] = np.where(
        df["total_desde_origen"] > 0,
        100 * df["flujo"] / df["total_desde_origen"],
        0.0
    )

    return df.sort_values(["sol_id", "ccaa_origen", "flujo"], ascending=[True, True, False])


def movimientos_desde_comunidad(df_sol, comunidad_origen):
    df_f = flujos_i_k(df_sol)
    return df_f[df_f["ccaa_origen"] == comunidad_origen].copy()


def capacidad_destinos(path_b, sol_id=None, ncap=50):
    df_b = pd.read_csv(path_b)
    df_b = filtrar_solucion(df_b, sol_id).copy()
    df_b = df_b.merge(df_res[["ccaa", "plazas_totales"]], on="ccaa", how="left")

    cols = ["sol_id", "k", "ccaa", "B_k", "occ_k", "plazas_totales"]
    cols = [c for c in cols if c in df_b.columns]
    df_b = df_b[cols].sort_values(["sol_id", "k"]).copy()

    df_b["capacidad_ampliada"] = df_b["plazas_totales"] + ncap * df_b["B_k"]
    df_b["S_k"] = np.maximum(df_b["occ_k"] - df_b["plazas_totales"], 0)
    df_b["Se_k"] = np.maximum(df_b["occ_k"] - df_b["capacidad_ampliada"], 0)

    df_b["Umbral_emergencia"] = np.ceil(0.20 * df_b["plazas_totales"])

    df_b["%umbral_ocupado"] = np.where(
        df_b["Umbral_emergencia"] > 0,
        100 * df_b["Se_k"] / df_b["Umbral_emergencia"],
        0.0
    )

    fila_total = {
        "sol_id": df_b["sol_id"].iloc[0] if len(df_b) > 0 else "",
        "k": "",
        "ccaa": "TOTAL",
        "B_k": df_b["B_k"].sum(),
        "occ_k": df_b["occ_k"].sum(),
        "S_k": df_b["S_k"].sum(),
        "Se_k": df_b["Se_k"].sum(),
        "plazas_totales": df_b["plazas_totales"].sum(),
        "capacidad_ampliada": df_b["capacidad_ampliada"].sum(),
        "Umbral_emergencia": df_b["Umbral_emergencia"].sum(),
        "%umbral_ocupado": (
            100 * df_b["Se_k"].sum() / df_b["Umbral_emergencia"].sum()
            if df_b["Umbral_emergencia"].sum() > 0 else 0.0
        )
    }

    df_b = pd.concat([df_b, pd.DataFrame([fila_total])], ignore_index=True)
    return df_b

def objetivos_resumen(path_summary, sol_id=None):
    df_s = pd.read_csv(path_summary)
    df_s = filtrar_solucion(df_s, sol_id)

    cols_preferidas = [
        "sol_id", "method", "primary", "f1", "f2", "f3",
        "eps_f1", "eps_f2", "eps_f3", "w1", "w2", "w3"
    ]
    cols = [c for c in cols_preferidas if c in df_s.columns]
    return df_s[cols].sort_values("sol_id")


df_total = construir_asignaciones_totales(PATH_X, PATH_XRES, PATH_XNEW)
df_sol = filtrar_solucion(df_total, SOL_ID)

if df_sol.empty:
    raise ValueError(f"No hay datos para SOL_ID={SOL_ID!r}")

if SOL_ID is None:
    df_metricas = metricas_todas_las_soluciones(df_total)
else:
    df_metricas = pd.DataFrame([metricas_globales_por_solucion(df_sol)])

df_resumen_origen = resumen_por_origen(df_sol)
df_flujos = flujos_i_k(df_sol)
df_mov_origen = movimientos_desde_comunidad(df_sol, COMUNIDAD_ORIGEN)
df_capacidad = capacidad_destinos(PATH_B, SOL_ID)
df_obj = objetivos_resumen(PATH_SUMMARY, SOL_ID)


print("\n=== MÉTRICAS GLOBALES ===")
print(df_metricas.to_string(index=False))

print(f"\n=== MOVIMIENTOS DESDE {COMUNIDAD_ORIGEN.upper()} ===")
if df_mov_origen.empty:
    print("No hay registros para esa comunidad.")
else:
    print(
        df_mov_origen[
            ["sol_id", "ccaa_origen", "ccaa_dest", "flujo", "pct_sobre_origen"]
        ].to_string(index=False)
    )

with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
    df_metricas.to_excel(writer, sheet_name="metricas_globales", index=False)
    df_resumen_origen.to_excel(writer, sheet_name="resumen_por_origen", index=False)
    df_flujos.to_excel(writer, sheet_name="flujos_i_k_mapa", index=False)
    df_mov_origen.to_excel(writer, sheet_name="movimientos_origen", index=False)
    df_capacidad.to_excel(writer, sheet_name="capacidad_destinos", index=False)
    df_obj.to_excel(writer, sheet_name="objetivos_resumen", index=False)
    df_sol.to_excel(writer, sheet_name="asignaciones_totales_ijk", index=False)

print(f"\nExcel creado: {OUTPUT_EXCEL}")