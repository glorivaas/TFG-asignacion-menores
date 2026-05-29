# -*- coding: utf-8 -*-
"""
Created on Wed May 13 20:37:40 2026

@author: glori
"""

from gurobipy import Model, GRB, quicksum
import pandas as pd
import numpy as np
import os

# ============================================
# 1. CONJUNTOS
# ============================================

OUTPUT_DIR = "resultados_cp"

ccaa = [
    "Andalucía",
    "Aragón",
    "Asturias",
    "Baleares",
    "Canarias",
    "Cantabria",
    "Castilla y León",
    "Castilla-La Mancha",
    "Cataluña",
    "Comunidad Valenciana",
    "Extremadura",
    "Galicia",
    "Madrid",
    "Murcia",
    "Navarra",
    "País Vasco",
    "La Rioja",
    "Ceuta",
    "Melilla",
]

# Conjuntos de índices que usará Gurobi
I = range(len(ccaa))  # origen
J = range(len(ccaa))  # comunidad que prefieren
K = range(len(ccaa))  # destino/asignación

ccaa_llegadas = {
    "Andalucía",
    "Baleares",
    "Canarias",  
    "Ceuta",
    "Melilla",
}

idx = {c: i for i, c in enumerate(ccaa)}    
nombre = {i: c for i, c in enumerate(ccaa)}  
llegadas_idx = {ccaa.index(c) for c in ccaa_llegadas}


# ============================================
# 2. DATOS
# ============================================

df_res = pd.read_excel("plazasCCAA.xlsx")
df_lleg = pd.read_excel("llegadas.xlsx")
R_list = df_res["Plazas ocupadas"].tolist()
L_por_nombre = {
    fila["CCAA"]: float(fila["Llegadas"])
    for _, fila in df_lleg.iterrows()
}
L_list = df_lleg["Llegadas"].tolist()
R = {i: float(R_list[i]) for i in I}
L = {
    i: L_por_nombre.get(ccaa[i], 0.0)
    for i in I
}

N = sum(R[i] + L[i] for i in I)

df_Rij = pd.read_excel("R_ij.xlsx", index_col=0)
df_Lij = pd.read_excel("L_ij.xlsx", index_col=0)

R_ij = {(i, j): int(df_Rij.iloc[i, j]) for i in I for j in J}
L_ij = {(i, j): int(df_Lij.iloc[i, j]) for i in I for j in J} 

# Costes de transporte por (i,k)
df_cost = pd.read_excel("Costestraslado.xlsx", index_col=0)
c_trans = {
    (i, k): float(df_cost.iloc[i, k])
    for i in I
    for k in K
}

# Coste por menor en emergencia en k
df_cost2 = pd.read_excel("costesCCAA2.xlsx")
C_list = df_cost2["Costes plaza ordinaria"].tolist()
c_plaza = {k: float(C_list[k]) for k in K}
estancia = 365
c_emerg = {k: 20 for k in K}

# Coste de abrir un centro en k
c_center = {k: 1000000.0 for k in K}

# Capacidad base existente en k
plazas_list = df_res["Plazas totales"].tolist()
cap = {k: float(plazas_list[k]) for k in K}

# Capacidad ordinaria supuesta por la ley
ord_list = df_res["Capacidad ordinaria"].tolist()
cap_ord = {k: float(ord_list[k]) for k in K}

# Capacidad que añade cada centro nuevo en k
n_center_cap = {k: 50 for k in K}

# Ocupación ideal por comunidad destino k (VERSIÓN 2: equidad territorial compuesta)
# -------------------------------------------------------------------------------
# Ficheros:
#   - poblacion.xlsx                    columnas: ['CCAA', 'Poblacion']
#   - renta_hogares.xlsx             columnas: ['CCAA', 'Renta']
#   - tasa_paro.xlsx                    columnas: ['CCAA', 'Tasa_paro']
#   - dispersion.xlsx                   columnas: ['CCAA', 'Dispersion']
#   - plazas_dimensionamiento.xlsx      columnas: ['CCAA', 'Plazas_diff_2500']
#
# Notas:
#   - En paro y plazas se usa criterio inverso: menor paro / menor sobredimensionamiento => más cuota.
#   - Para Melilla, Ceuta, Canarias y Baleares se aplica ponderación negativa del -100% en su respectivo criterio,
#     tal y como recoge el BOE para frontera e insularidad.

def normaliza_directo(dic):
    total = sum(dic.values())
    return {k: (dic[k] / total if total > 0 else 0.0) for k in dic}

def normaliza_inverso(dic, eps=1e-9):
    inv = {k: 1.0 / max(dic[k], eps) for k in dic}
    total = sum(inv.values())
    return {k: (inv[k] / total if total > 0 else 0.0) for k in dic}

def alinear_diccionario(df, col_valor):
    base = dict(zip(df["CCAA"], df[col_valor]))
    return {k: float(base[ccaa[k]]) for k in K}

df_pob  = pd.read_excel("poblacion.xlsx")
df_ren = pd.read_excel("renta_hogares.xlsx", sheet_name="Datos", header=5)
df_paro = pd.read_excel("tasa_paro.xlsx", sheet_name="Datos", header=5)
df_disp = pd.read_excel("dispersion.xlsx", sheet_name="Datos", header=5)
df_plz  = pd.read_excel("plazas_dimensionamiento.xlsx", sheet_name="criterio_e", header=4)
df_mena = pd.read_excel("esfuerzo_mena.xlsx",sheet_name="Proxy_esfuerzo_MENA", header=8)

poblacion = alinear_diccionario(df_pob, "Poblacion")
renta_pc = alinear_diccionario(df_ren, "Renta")
tasa_paro = alinear_diccionario(df_paro, "Tasa_paro")
dispersion = alinear_diccionario(df_disp, "Entidades_singulares")
plazas_diff_2500 = alinear_diccionario(df_plz,"Cuota normalizada\ncriterio e)")
base_mena = dict(zip(df_mena["CCAA"], df_mena["Cuota normalizada criterio d)"]))

# subcuotas normalizadas 
# a) 50% población (directo)
q_pob = normaliza_directo(poblacion)

# b) 13% renta disponible bruta per cápita (directo)
q_renta = normaliza_directo(renta_pc)

# c) 15% tasa de paro (inverso)
q_paro = normaliza_inverso(tasa_paro)

# d) 6% esfuerzo mena
q_mena = {k: float(base_mena[ccaa[k]]) for k in K}

# e) 10% dimensionamiento estructural (inverso)
#    Se usa la diferencia respecto a 1 plaza / 2.500 hab.
#    Cuanto menor sea esa diferencia, mayor cuota.
q_plazas = normaliza_inverso(plazas_diff_2500)

# f) 2% ciudad fronteriza
#    BOE: ponderación negativa del -100% a Melilla y Ceuta.
#    Lo implementamos dejando las seleccionadas en 0 y repartiendo el peso entre el resto.
frontera_base = {k: 1.0 for k in K}
frontera_base[idx["Melilla"]] = 0.0
frontera_base[idx["Ceuta"]] = 0.0
q_frontera = normaliza_directo(frontera_base)

# g) 2% insularidad
#    BOE: ponderación negativa del -100% a Baleares y Canarias.
#    Lo implementamos dejando a Baleares y Canarias en 0 y repartiendo el peso entre el resto.
insularidad_base = {k: 1.0 for k in K}
insularidad_base[idx["Baleares"]] = 0.0
insularidad_base[idx["Canarias"]] = 0.0
q_insularidad = normaliza_directo(insularidad_base)

# h) 2% dispersión de la población (directo)
q_dispersion = normaliza_directo(dispersion)

w_pob = 0.50
w_renta = 0.13
w_paro = 0.15
w_mena = 0.06
w_plazas = 0.10
w_frontera = 0.02
w_insularidad = 0.02
w_dispersion = 0.02

cuota_equidad = {
    k:
        w_pob * q_pob[k]
        + w_renta * q_renta[k]
        + w_paro * q_paro[k]
        + w_mena * q_mena[k]
        + w_plazas * q_plazas[k]
        + w_frontera * q_frontera[k]
        + w_insularidad * q_insularidad[k]
        + w_dispersion * q_dispersion[k]
    for k in K
}

# asignación ideal asociada al objetivo de equidad
T_ideal = {k: N * cuota_equidad[k] for k in K}

# umbral de personas en situación de emergencia
import math
T = {k: math.ceil(0.2 * cap[k]) for k in K}

B_max = {k: 10 for k in K} 

# ============================================
# Índice de bienestar por comunidad (VERSIÓN 2 con adaptaciones educativas)
# ============================================

df_w = pd.read_excel(
    "indice_bienestar_v2.xlsx",
    sheet_name="Indice_bienestar_v2"
)
df_w.columns = df_w.columns.astype(str).str.strip()

base_w = dict(zip(df_w["CCAA"], df_w["Indice_compuesto_v2"]))

W = {k: float(base_w[ccaa[k]]) for k in K}

# Pesos de preferencias (recompensa - penalización)
alpha = 2.0   # recompensa por indice 
beta = 5.0    # recompensa por pref
gamma = 10.0   # penalización por residentes
lambd = {
    k: (max(c_plaza[k] - c_emerg[k],0))*estancia + 50
    for k in K
} 
# λk​=(coste emergencia)−(coste ordinario) sería neutral

def extraer_soluciones(sol_id, method, m, obj, vars_, extra_meta=None, x_threshold=1e-6):
    """
    Extrae una solución óptima y guarda asignaciones SIN duplicar:
      - Si i ∈ llegadas_idx  -> guarda X_res y X_new (no guarda X)
      - Si i ∉ llegadas_idx  -> guarda X (no existe descomposición)
    Devuelve:
      summary_row: dict
      B_rows:      list[dict]     (por k)
      X_rows:      list[dict]     (solo i no-llegadas)
      Xres_rows:   list[dict]     (solo i llegadas)
      Xnew_rows:   list[dict]     (solo i llegadas)
    """
    if extra_meta is None:
        extra_meta = {}

    summary = {
        "sol_id": sol_id,
        "method": method,
        **extra_meta,
        "f1": float(obj["f1"].getValue()),
        "f2": float(obj["f2"].getValue()),
        "f3": float(obj["f3"].getValue()),
    }

    B_rows = []
    for k in K:
        row = {
            "sol_id": sol_id,
            "k": int(k),
            "ccaa": nombre[k],
            "B_k": int(round(vars_["B"][k].X)),
        }
        if "occ" in vars_:
            row["occ_k"] = float(vars_["occ"][k].X)
        if "S" in vars_:
            row["S_k"] = float(vars_["S"][k].X)
        if "Se" in vars_:
            row["Se_k"] = float(vars_["Se"][k].X)
        B_rows.append(row)

    X_rows, Xres_rows, Xnew_rows = [], [], []

    if "X" in vars_:
        for (i, j, k), varx in vars_["X"].items():
            if i in llegadas_idx:
                continue  
            v = float(varx.X)
            if v > x_threshold:
                X_rows.append({
                    "sol_id": sol_id,
                    "i": int(i), "j": int(j), "k": int(k),
                    "ccaa_origen": nombre[i],
                    "ccaa_pref": nombre[j],
                    "ccaa_dest": nombre[k],
                    "X": v
                })

    if "X_res" in vars_:
        for (i, j, k), varx in vars_["X_res"].items():
            v = float(varx.X)
            if v > x_threshold:
                Xres_rows.append({
                    "sol_id": sol_id,
                    "i": int(i), "j": int(j), "k": int(k),
                    "ccaa_origen": nombre[i],
                    "ccaa_pref": nombre[j],
                    "ccaa_dest": nombre[k],
                    "X_res": v
                })

    if "X_new" in vars_:
        for (i, j, k), varx in vars_["X_new"].items():
            v = float(varx.X)
            if v > x_threshold:
                Xnew_rows.append({
                    "sol_id": sol_id,
                    "i": int(i), "j": int(j), "k": int(k),
                    "ccaa_origen": nombre[i],
                    "ccaa_pref": nombre[j],
                    "ccaa_dest": nombre[k],
                    "X_new": v
                })

    return summary, B_rows, X_rows, Xres_rows, Xnew_rows


def build_model():
    m = Model("TFG_menores")

    X = m.addVars(I, J, K, vtype=GRB.INTEGER, lb=0.0, name="X")
    X_res = m.addVars(llegadas_idx, J, K, vtype=GRB.INTEGER, lb=0.0, name="X_res")
    X_new = m.addVars(llegadas_idx, J, K, vtype=GRB.INTEGER, lb=0.0, name="X_new")
    t = m.addVars(K, vtype=GRB.CONTINUOUS, lb=0, name="t")
    B = m.addVars(K, vtype=GRB.INTEGER, lb=0, name="B")
    S = m.addVars(K, vtype=GRB.CONTINUOUS, lb=0.0, name="S")
    Se = m.addVars(K, vtype=GRB.CONTINUOUS, lb=0.0, name="Se+")
    occ = m.addVars(K, vtype=GRB.CONTINUOUS, lb=0.0, name="occ")


    # RESTRICCIONES
    # En comunidades de alta llegada: X = X_res + X_new
    for i in llegadas_idx:
        for j in J:
            for k in K:
                m.addConstr(
                    X[i, j, k] == X_res[i, j, k] + X_new[i, j, k],
                    name=f"X_{i}_{j}_{k}_cca_llegadas"
                )
  
    # Datos de menores en el origen
    for i in I:
        if i in llegadas_idx:
            m.addConstr(
                quicksum(X_res[i,j,k] for j in J for k in K) == R[i],
                name=f"res_origen_{i}"
            )

            m.addConstr(
                quicksum(X_new[i,j,k] for j in J for k in K) == L[i],
                name=f"new_origen_{i}"
            )
        else:
            m.addConstr(
                quicksum(X[i,j,k] for j in J for k in K) == R[i],
                name=f"menores_origen_{i}"
            )
        
    # Datos de preferencias de menores
    for i in I:
        for j in J:
            if i in llegadas_idx:
                m.addConstr(
                    quicksum(X_res[i,j,k] for k in K) == R_ij[i,j],
                    name=f"pref_res_{i}_{j}"
                )

                m.addConstr(
                    quicksum(X_new[i,j,k] for k in K) == L_ij[i,j],
                    name=f"pref_new_{i}_{j}"
                )
            else:
                m.addConstr(
                    quicksum(X[i,j,k] for k in K) == R_ij[i,j],
                    name=f"preferencias2_{i}_{j}"
                )

    for k in K:
        m.addConstr(    # ocupación total occ[k]
            occ[k] == quicksum(
                X[i, j, k]       
                for i in I for j in J
            ),
            name=f"ocupacion_{nombre[k]}"
        )

        m.addConstr(    # restricciones de destino
            cap_ord[k] <= quicksum(
                X[i, j, k] for i in I for j in J
            ),
            name=f"inferior_X{k}"
        )
    
        m.addConstr(    # restricciones de destino 2
            quicksum(
                X[i, j, k] for i in I for j in J
            ) <= cap[k] + S[k],
            name=f"superior_X{k}"
        )
    
        m.addConstr(    # menores sobrantes
            S[k] <= T[k] + B[k] * n_center_cap[k],
            name=f"sobrantes2_{nombre[k]}"
        )
    
        m.addConstr(
            Se[k] >= occ[k] - cap[k] - B[k]*n_center_cap[k],
            name=f"emergencia_lb_{nombre[k]}"
        )
        m.addConstr(
            Se[k] >= 0,
            name=f"emergencia_nn_{nombre[k]}"
        )
        
        m.addConstr(    # linearizar la f1
            t[k] >= occ[k] - T_ideal[k],
            name=f"desviacion1_{nombre[k]}"
        )
    
        m.addConstr(    # linearizar la f1
            t[k] >= -occ[k] + T_ideal[k],
            name=f"desviacion2_{nombre[k]}"
        )

        m.addConstr(
            B[k] <= B_max[k],
            name=f"max_centros_{ccaa[k]}"
        )


    # OBJETIVOS
    f1 = quicksum(t[k] for k in K)

    f2 = quicksum(
            (X[i, j, k]) * (c_trans[i, k] + c_plaza[k]*estancia)
            for i in I for j in J for k in K
        ) \
        + quicksum(Se[k] * (lambd[k] + c_emerg[k]*estancia - c_plaza[k]*estancia) for k in K) \
        + quicksum(B[k] * c_center[k] for k in K)

    f3 = quicksum(X[i, j, k] * W[k] * alpha for i in I for j in J for k in K) \
        + quicksum(X[i, j, k] * (1.0 if j == k else 0.0) * beta for i in I for j in J for k in K) \
        - quicksum(X_res[i, j, k] * (1.0 if (i != k and j!=k) else 0.0) * gamma for i in llegadas_idx for j in J for k in K) \
        - quicksum(X[i, j, k] * (1.0 if (i != k and j!=k) else 0.0) * gamma for i in I if i not in llegadas_idx for j in J for k in K)

    obj = {"f1": f1, "f2": f2, "f3": f3}
    vars_ = {"X": X, "X_res": X_res, "X_new": X_new, "t": t, "B": B, "S": S, "Se": Se, "occ": occ}
    return m, obj, vars_
    

# CONSTRAINED METHOD

# extremos
def solve_single_objective(which, outputflag=0):
    m, obj, _ = build_model()
    if which == "f1":
        m.setObjective(obj["f1"], GRB.MINIMIZE)
    elif which == "f2":
        m.setObjective(obj["f2"], GRB.MINIMIZE)
    elif which == "f3":
        m.setObjective(-obj["f3"], GRB.MINIMIZE)
    else:
        raise ValueError("which must be f1, f2 or f3")

    m.optimize()
    if m.status != GRB.OPTIMAL:
        return None
    return {
       "f1": float(obj["f1"].getValue()),
       "f2": float(obj["f2"].getValue()),
       "f3": float(obj["f3"].getValue())
   }

ext_f1 = solve_single_objective("f1")
ext_f2 = solve_single_objective("f2")
ext_f3 = solve_single_objective("f3")
print("Extremos:", ext_f1, ext_f2, ext_f3)

def guardar_soluciones(
    summaries, B_rows, X_rows, Xres_rows, Xnew_rows,
    path_summary="eficientes_resumen.csv",
    path_B="eficientes_B.csv",
    path_X="eficientes_Xpos.csv",
    path_Xres="eficientes_Xres_pos.csv",
    path_Xnew="eficientes_Xnew_pos.csv"
):
    pd.DataFrame(summaries).to_csv(path_summary, index=False)
    pd.DataFrame(B_rows).to_csv(path_B, index=False)
    pd.DataFrame(X_rows).to_csv(path_X, index=False)
    pd.DataFrame(Xres_rows).to_csv(path_Xres, index=False)
    pd.DataFrame(Xnew_rows).to_csv(path_Xnew, index=False)
    print("Guardado:",
          path_summary, "|", path_B, "|", path_X, "|", path_Xres, "|", path_Xnew)




def compromise_programming_direct(p=2, weights=(1/3, 1/3, 1/3),
                                  time_limit=None, outputflag=0):
    """
    Programación por compromiso directamente sobre el modelo.
    """

    ext1 = solve_single_objective("f1", outputflag=outputflag)
    ext2 = solve_single_objective("f2", outputflag=outputflag)
    ext3 = solve_single_objective("f3", outputflag=outputflag)

    payoff = pd.DataFrame([ext1, ext2, ext3], index=["min_f1", "min_f2", "max_f3"])

    ideal = {
        "f1": payoff["f1"].min(),
        "f2": payoff["f2"].min(),
        "f3": payoff["f3"].max(),
    }

    nadir_aprox = {
        "f1": payoff["f1"].max(),
        "f2": payoff["f2"].max(),
        "f3": payoff["f3"].min(),
    }

    ranges = {
        "f1": max(nadir_aprox["f1"] - ideal["f1"], 1e-9),
        "f2": max(nadir_aprox["f2"] - ideal["f2"], 1e-9),
        "f3": max(ideal["f3"] - nadir_aprox["f3"], 1e-9),
    }

    m, obj, vars_ = build_model()

    w1, w2, w3 = weights

    d1 = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="d1_cp")
    d2 = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="d2_cp")
    d3 = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="d3_cp")

    m.addConstr(d1 >= (obj["f1"] - ideal["f1"]) / ranges["f1"], name="dev_f1_cp")
    m.addConstr(d2 >= (obj["f2"] - ideal["f2"]) / ranges["f2"], name="dev_f2_cp")

    m.addConstr(d3 >= (ideal["f3"] - obj["f3"]) / ranges["f3"], name="dev_f3_cp")

    if p == 1:
        m.setObjective(w1*d1 + w2*d2 + w3*d3, GRB.MINIMIZE)

    elif p == 2:
        m.setObjective(w1*d1*d1 + w2*d2*d2 + w3*d3*d3, GRB.MINIMIZE)

    elif p == "inf":
        D = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="D_cp")
        m.addConstr(D >= w1*d1, name="D_f1")
        m.addConstr(D >= w2*d2, name="D_f2")
        m.addConstr(D >= w3*d3, name="D_f3")
        m.setObjective(D, GRB.MINIMIZE)

    else:
        raise ValueError("p debe ser 1, 2 o 'inf'.")

    if time_limit is not None:
        m.Params.TimeLimit = time_limit

    m.Params.OutputFlag = outputflag
    m.Params.MIPGap = 0.0
    m.optimize()

    if m.status != GRB.OPTIMAL:
        print("No se encontró solución óptima. Status:", m.status)
        return None

    sol_id = f"cp_direct_L{p}"

    meta = {
        "method": "compromise_direct",
        "metric": f"L{p}",
        "w1": w1,
        "w2": w2,
        "w3": w3,
        "d1": float(d1.X),
        "d2": float(d2.X),
        "d3": float(d3.X),
        "ideal_f1": ideal["f1"],
        "ideal_f2": ideal["f2"],
        "ideal_f3": ideal["f3"],
    }

    summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
        sol_id=sol_id,
        method="compromise_direct",
        m=m,
        obj=obj,
        vars_=vars_,
        extra_meta=meta,
        x_threshold=1e-6
    )

    guardar_soluciones(
        [summary],
        B_rows,
        X_rows,
        Xres_rows,
        Xnew_rows,
        path_summary=os.path.join(OUTPUT_DIR, f"cp_direct_L{p}_summary2.csv"),
        path_B=os.path.join(OUTPUT_DIR, f"cp_direct_L{p}_B2.csv"),
        path_X=os.path.join(OUTPUT_DIR, f"cp_direct_L{p}_Xpos2.csv"),
        path_Xres=os.path.join(OUTPUT_DIR, f"cp_direct_L{p}_Xres_pos2.csv"),
        path_Xnew=os.path.join(OUTPUT_DIR, f"cp_direct_L{p}_Xnew_pos2.csv"),
    )

    return summary


os.makedirs(OUTPUT_DIR, exist_ok=True)
print("Directorio actual:", os.getcwd())
print("Guardando resultados en:", os.path.abspath(OUTPUT_DIR))

sol_cp_L1 = compromise_programming_direct(p=1, weights=(1/3, 1/3, 1/3), outputflag=0)
sol_cp_L2 = compromise_programming_direct(p=2, weights=(1/3, 1/3, 1/3), outputflag=0)
sol_cp_Linf = compromise_programming_direct(p="inf", weights=(1/3, 1/3, 1/3), outputflag=0)

print("Solución CP L1:", sol_cp_L1)
print("Solución CP L2:", sol_cp_L2)
print("Solución CP Linf:", sol_cp_Linf)