# -*- coding: utf-8 -*-
"""
Created on Fri Feb  6 12:39:44 2026

@author: glori
"""

from gurobipy import Model, GRB, quicksum
import pandas as pd
import numpy as np

# ============================================
# 1. CONJUNTOS
# ============================================

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

# Ocupación ideal por comunidad destino k
df_pob = pd.read_excel("poblacion.xlsx")
poblacion = {i: df_pob.loc[i, "Poblacion"] for i in range(len(ccaa))}
poblacionT = sum(poblacion.values())
T_ideal = {k: N*(poblacion[k]/poblacionT) for k in K}

# Umbral de personas en situación de emergencia
import math
T = {k: math.ceil(0.2 * cap[k]) for k in K}

B_max = {k: 10 for k in K} 

# índice de bienestar por comunidad
df = pd.read_excel("indice_bienestar_comunidades.xlsx",skiprows = 47)
W_list = df["Índice compuesto"].tolist()[:len(ccaa)]
W = {k: float(W_list[k]) for k in range(len(W_list))}

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
      X_rows:      list[dict]     (solo i no llegadas)
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

# se calculan extremos
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

def linspace_safe(a, b, n):
    """Genera linspace robusto aunque a>b."""
    lo, hi = (a, b) if a <= b else (b, a)
    return np.linspace(lo, hi, n)

def dominates(a, b):
    not_worse = (a["f1"] <= b["f1"]) and (a["f2"] <= b["f2"]) and (a["f3"] >= b["f3"])
    strictly_better = (a["f1"] < b["f1"]) or (a["f2"] < b["f2"]) or (a["f3"] > b["f3"])
    return not_worse and strictly_better

def pareto_filter(sols):
    eff = []
    for i,s in enumerate(sols):
        dominated = False
        for j,t_ in enumerate(sols):
            if i != j and dominates(t_, s):
                dominated = True
                break
        if not dominated:
            eff.append(s)
    return eff

def epsilon_search(primary, n1=8, n2=8, time_limit=None, outputflag=0):
    """
    Constrained method (ε-constraints).
    primary: "f1" o "f2" o "f3".
    - Si primary="f1": min f1 s.a. f2<=eps2, f3>=eps3
    - Si primary="f2": min f2 s.a. f1<=eps1, f3>=eps3
    - Si primary="f3": max f3 s.a. f1<=eps1, f2<=eps2
    n1,n2: tamaño rejilla para epsilons (n1 para el primer eps, n2 para el segundo).
    """

    ext1 = solve_single_objective("f1", outputflag=outputflag)
    ext2 = solve_single_objective("f2", outputflag=outputflag)
    ext3 = solve_single_objective("f3", outputflag=outputflag)

    if ext1 is None or ext2 is None or ext3 is None:
        raise RuntimeError("Algún extremo monoobjetivo no es óptimo. Revisa factibilidad/datos.")

    # rangos observados para construir eps
    f1_vals = [ext1["f1"], ext2["f1"], ext3["f1"]]
    f2_vals = [ext1["f2"], ext2["f2"], ext3["f2"]]
    f3_vals = [ext1["f3"], ext2["f3"], ext3["f3"]]

    f1_min, f1_max = min(f1_vals), max(f1_vals)
    f2_min, f2_max = min(f2_vals), max(f2_vals)
    f3_min, f3_max = min(f3_vals), max(f3_vals)

    summaries, B_all, X_all, Xres_all, Xnew_all = [], [], [], [], []
    solutions = []

    if primary == "f1":
        eps2_grid = linspace_safe(f2_min, f2_max, n1)
        eps3_grid = linspace_safe(f3_min, f3_max, n2)

        for eps2 in eps2_grid:
            for eps3 in eps3_grid:
                m, obj, vars_ = build_model()
                m.setObjective(obj["f1"], GRB.MINIMIZE)

                m.addConstr(obj["f2"] <= float(eps2), name="eps_f2")
                m.addConstr(obj["f3"] >= float(eps3), name="eps_f3")

                if time_limit is not None:
                    m.Params.TimeLimit = time_limit
                m.Params.OutputFlag = outputflag
                m.optimize()

                if m.status == GRB.OPTIMAL:
                    sol_id = f"eps_{primary}_{len(summaries)}"
                    meta = {"primary": primary}
                    meta.update({"eps_f2": float(eps2), "eps_f3": float(eps3)})
                    summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                        sol_id=sol_id,
                        method="eps",
                        m=m,
                        obj=obj,
                        vars_=vars_,
                        extra_meta=meta,
                        x_threshold=1e-6
                        )

                    summaries.append(summary)
                    B_all.extend(B_rows)
                    X_all.extend(X_rows)
                    Xres_all.extend(Xres_rows)
                    Xnew_all.extend(Xnew_rows)
                    solutions.append(summary)

    elif primary == "f2":
        eps1_grid = linspace_safe(f1_min, f1_max, n1)
        eps3_grid = linspace_safe(f3_min, f3_max, n2)

        for eps1 in eps1_grid:
            for eps3 in eps3_grid:
                m, obj, vars_ = build_model()
                m.setObjective(obj["f2"], GRB.MINIMIZE)

                m.addConstr(obj["f1"] <= float(eps1), name="eps_f1")
                m.addConstr(obj["f3"] >= float(eps3), name="eps_f3")

                if time_limit is not None:
                    m.Params.TimeLimit = time_limit
                m.Params.OutputFlag = outputflag
                m.optimize()

                if m.status == GRB.OPTIMAL:
                    sol_id = f"eps_{primary}_{len(summaries)}"
                    meta = {"primary": primary}
                    meta.update({"eps_f1": float(eps1), "eps_f3": float(eps3)})
                    summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                        sol_id=sol_id,
                        method="eps",
                        m=m,
                        obj=obj,
                        vars_=vars_,
                        extra_meta=meta,
                        x_threshold=1e-6
                        )

                    summaries.append(summary)
                    B_all.extend(B_rows)
                    X_all.extend(X_rows)
                    Xres_all.extend(Xres_rows)
                    Xnew_all.extend(Xnew_rows)
                    solutions.append(summary)

    elif primary == "f3":
        eps1_grid = linspace_safe(f1_min, f1_max, n1)
        eps2_grid = linspace_safe(f2_min, f2_max, n2)

        for eps1 in eps1_grid:
            for eps2 in eps2_grid:
                m, obj, vars_ = build_model()
                m.setObjective(obj["f3"], GRB.MAXIMIZE)

                m.addConstr(obj["f1"] <= float(eps1), name="eps_f1")
                m.addConstr(obj["f2"] <= float(eps2), name="eps_f2")

                if time_limit is not None:
                    m.Params.TimeLimit = time_limit
                m.Params.OutputFlag = outputflag
                m.optimize()

                if m.status == GRB.OPTIMAL:
                    sol_id = f"eps_{primary}_{len(summaries)}"
                    meta = {"primary": primary}
                    meta.update({"eps_f1": float(eps1), "eps_f2": float(eps2)})
                    summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                        sol_id=sol_id,
                        method="eps",
                        m=m,
                        obj=obj,
                        vars_=vars_,
                        extra_meta=meta,
                        x_threshold=1e-6
                        )

                    summaries.append(summary)
                    B_all.extend(B_rows)
                    X_all.extend(X_rows)
                    Xres_all.extend(Xres_rows)
                    Xnew_all.extend(Xnew_rows)
                    solutions.append(summary)

    else:
        raise ValueError("primary must be 'f1', 'f2' or 'f3'.")

    efficient = pareto_filter(solutions)

    return {
    "extremos": {"f1": ext1, "f2": ext2, "f3": ext3},
    "raw": summaries,           
    "efficient": efficient,
    "B_rows": B_all,
    "X_rows": X_all,
    "Xres_rows": Xres_all,
    "Xnew_rows": Xnew_all
}


res_f1 = epsilon_search(primary="f1", n1=8, n2=8, time_limit=None, outputflag=0)
res_f2 = epsilon_search(primary="f2", n1=8, n2=8, time_limit=None, outputflag=0)
res_f3 = epsilon_search(primary="f3", n1=8, n2=8, time_limit=None, outputflag=0)

df_eff_f1 = pd.DataFrame(res_f1["efficient"])
df_eff_f2 = pd.DataFrame(res_f2["efficient"])
df_eff_f3 = pd.DataFrame(res_f3["efficient"])

df_eff_f1.to_csv("pareto_eps_prioridad_f1.csv", index=False)
df_eff_f2.to_csv("pareto_eps_prioridad_f2.csv", index=False)
df_eff_f3.to_csv("pareto_eps_prioridad_f3.csv", index=False)

all_eff = res_f1["efficient"] + res_f2["efficient"] + res_f3["efficient"]
global_eff = pareto_filter(all_eff)
pd.DataFrame(global_eff).to_csv("pareto_eps_global.csv", index=False)

print("Eficientes con prioridad f1:", len(df_eff_f1))
print("Eficientes con prioridad f2:", len(df_eff_f2))
print("Eficientes con prioridad f3:", len(df_eff_f3))
print("Eficientes global:", len(global_eff))
print("Extremos:", res_f1["extremos"])

# preparamos el conjunto eficiente aproximado

df = pd.DataFrame(global_eff)
df = df.round({"f1": 6, "f2": 2, "f3": 6}) \
       .drop_duplicates(subset=["f1","f2","f3"]) \
       .reset_index(drop=True)

print("Soluciones eficientes limpias:", len(df))

import matplotlib.pyplot as plt

df = pd.read_csv("pareto_eps_global.csv")
plt.scatter(df["f2"], df["f3"], c=df["f1"], cmap="viridis")
plt.colorbar(label="Desigualdad territorial (f1)")
plt.xlabel("Coste total (f2)")
plt.ylabel("Bienestar (f3)")
plt.title("Proyección coste–bienestar coloreada por equidad")
plt.show()




# _________________________________________________________________
# Usamos ahora el método de pesos ponderados:
    
import numpy as np
import pandas as pd
from gurobipy import GRB

def weight_grid(step=0.1):
    """Genera pesos (w1,w2,w3) en el simplex con paso dado."""
    ws = []
    vals = np.arange(0, 1 + 1e-9, step)
    for w1 in vals:
        for w2 in vals:
            w3 = 1.0 - w1 - w2
            if w3 >= -1e-9:
                w3 = max(0.0, w3)
                ws.append((float(w1), float(w2), float(w3)))
    ws = list({(round(a,6), round(b,6), round(c,6)) for a,b,c in ws})
    return ws

def compute_norm_params(ext1, ext2, ext3):
    f1_vals = [ext1["f1"], ext2["f1"], ext3["f1"]]
    f2_vals = [ext1["f2"], ext2["f2"], ext3["f2"]]
    f3_vals = [ext1["f3"], ext2["f3"], ext3["f3"]]
    p = {
        "f1_min": min(f1_vals), "f1_max": max(f1_vals),
        "f2_min": min(f2_vals), "f2_max": max(f2_vals),
        "f3_min": min(f3_vals), "f3_max": max(f3_vals),
    }
    for k in ["f1","f2","f3"]:
        if abs(p[f"{k}_max"] - p[f"{k}_min"]) < 1e-12:  
            p[f"{k}_max"] = p[f"{k}_min"] + 1.0
    return p

def weighted_sum_search(step=0.1, time_limit=None, outputflag=0):
    ext1 = solve_single_objective("f1", outputflag=outputflag)
    ext2 = solve_single_objective("f2", outputflag=outputflag)
    ext3 = solve_single_objective("f3", outputflag=outputflag)
    if ext1 is None or ext2 is None or ext3 is None:
        raise RuntimeError("No se pudieron obtener extremos monoobjetivo.")

    norm = compute_norm_params(ext1, ext2, ext3)

    weights = weight_grid(step=step)
    sols = []
    summaries, B_all, X_all, Xres_all, Xnew_all = [], [], [], [], []


    for (w1, w2, w3) in weights:
        m, obj, vars_ = build_model()

        f1n = (obj["f1"] - norm["f1_min"]) / (norm["f1_max"] - norm["f1_min"])
        f2n = (obj["f2"] - norm["f2_min"]) / (norm["f2_max"] - norm["f2_min"])
        f3n = (obj["f3"] - norm["f3_min"]) / (norm["f3_max"] - norm["f3_min"])

        m.setObjective(w1*f1n + w2*f2n + w3*(1 - f3n), GRB.MINIMIZE)

        if time_limit is not None:
            m.Params.TimeLimit = time_limit
        m.Params.OutputFlag = outputflag
        m.optimize()

        if m.status == GRB.OPTIMAL:
            sol_id = f"wgt_{len(summaries)}"
            meta = {"w1": w1, "w2": w2, "w3": w3}

            summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                sol_id=sol_id,
                method="weighting",
                m=m,
                obj=obj,
                vars_=vars_,
                extra_meta=meta,
                x_threshold=1e-6
                )

            summaries.append(summary)
            B_all.extend(B_rows)
            X_all.extend(X_rows)
            Xres_all.extend(Xres_rows)
            Xnew_all.extend(Xnew_rows)

    eff = pareto_filter(summaries)
    return {
        "extremos": {"f1": ext1, "f2": ext2, "f3": ext3},
        "raw": summaries,
        "efficient": eff,
        "B_rows": B_all,
        "X_rows": X_all,
        "Xres_rows": Xres_all,
        "Xnew_rows": Xnew_all
        }

res_w = weighted_sum_search(step=0.1, time_limit=None, outputflag=0)
df_w = pd.DataFrame(res_w["efficient"])
df_w = df_w.round({"f1":6, "f2":2, "f3":6}).drop_duplicates(subset=["f1","f2","f3"]).reset_index(drop=True)
df_w.to_csv("pareto_weighting.csv", index=False)

print("Soluciones eficientes (weighting):", len(df_w))




# COMPARACIÓN
df_eps = pd.read_csv("pareto_eps_global.csv").round({"f1":6,"f2":2,"f3":6}).drop_duplicates(subset=["f1","f2","f3"])
df_w   = pd.read_csv("pareto_weighting.csv").round({"f1":6,"f2":2,"f3":6}).drop_duplicates(subset=["f1","f2","f3"])

print("EPS: #puntos =", len(df_eps))
print("WGT: #puntos =", len(df_w))

def ranges(df, name):
    print(f"\nRangos {name}:")
    for f in ["f1","f2","f3"]:
        print(f"  {f}: [{df[f].min():.4g}, {df[f].max():.4g}]")
ranges(df_eps, "ε-constraints")
ranges(df_w, "weighting")

A = df_eps[["f1","f2","f3"]].to_numpy()
B = df_w[["f1","f2","f3"]].to_numpy()

tol_f1 = 1e-2     
tol_f2 = 1e5
tol_f3 = 1e-2

def count_matches(A, B):
    count = 0
    for a in A:
        close = np.where(
            (np.abs(B[:,0]-a[0])<=tol_f1) &
            (np.abs(B[:,1]-a[1])<=tol_f2) &
            (np.abs(B[:,2]-a[2])<=tol_f3)
        )[0]
        if len(close)>0:
            count += 1
    return count

m_eps_w = count_matches(A, B)
m_w_eps = count_matches(B, A)

print("ε → weighting:", m_eps_w)
print("weighting → ε:", m_w_eps)


print("Cobertura ε:", m_eps_w / len(A))
print("Cobertura weighting:", m_w_eps / len(B))  # vemos la cobertura de cada método

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


all_summaries, all_B, all_X, all_Xres, all_Xnew = [], [], [], [], []

for res in [res_f1, res_f2, res_f3]:
    all_summaries.extend(res["efficient"])
all_summaries.extend(res_w["efficient"])

global_union = pareto_filter(all_summaries)
df_union = pd.DataFrame(global_union)
df_union = df_union.round({"f1":6, "f2":2, "f3":6}) \
                   .drop_duplicates(subset=["f1","f2","f3"]) \
                   .reset_index(drop=True)

print("Pareto de la unión:", len(df_union))

keep = set(df_union["sol_id"].astype(str))

for res in [res_f1, res_f2, res_f3, res_w]:
    all_B.extend(res["B_rows"])
    all_X.extend(res["X_rows"])
    all_Xres.extend(res["Xres_rows"])
    all_Xnew.extend(res["Xnew_rows"])


pareto_summaries = [s for s in all_summaries if str(s["sol_id"]) in keep]
pareto_B = [r for r in all_B if str(r["sol_id"]) in keep]
pareto_X = [r for r in all_X if str(r["sol_id"]) in keep]
pareto_Xres = [r for r in all_Xres if str(r["sol_id"]) in keep]
pareto_Xnew = [r for r in all_Xnew if str(r["sol_id"]) in keep]

guardar_soluciones(
    pareto_summaries, pareto_B, pareto_X, pareto_Xres, pareto_Xnew,
    path_summary="pareto_global_summary.csv",
    path_B="pareto_global_B.csv",
    path_X="pareto_global_Xpos.csv",
    path_Xres="pareto_global_Xres_pos.csv",
    path_Xnew="pareto_global_Xnew_pos.csv"
)

# ____________________________________________________________________________
# gráfico comparativo
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.ticker import ScalarFormatter
# normalización común del color (f1) para ambas nubes
f1_all = np.concatenate([df_eps["f1"].to_numpy(), df_w["f1"].to_numpy()])
norm = Normalize(vmin=float(np.min(f1_all)), vmax=float(np.max(f1_all)))

fig, ax = plt.subplots(figsize=(9, 6))

sc1 = ax.scatter(
    df_eps["f2"], -df_eps["f3"],
    c=df_eps["f1"], norm=norm,
    marker="o", alpha=0.75
)
sc2 = ax.scatter(
    df_w["f2"], -df_w["f3"],
    c=df_w["f1"], norm=norm,
    marker="x", alpha=0.95
)

ax.set_xlabel("f2 (coste)")
ax.set_ylabel("-f3 (malestar)")
ax.set_title("Pareto aproximado: ε-constraints (o) vs weighting (x) — color = f1 (inequidad)")
ax.grid(True, alpha=0.25)
cbar = fig.colorbar(sc1, ax=ax, pad=0.02)
cbar.set_label("f1 (inequidad)")
fig.tight_layout()
plt.show()

# representación en 3D
fig = plt.figure(figsize=(11, 7), constrained_layout=True)
ax = fig.add_subplot(111, projection="3d")
sc_eps = ax.scatter(
    df_eps["f2"], -df_eps["f3"], df_eps["f1"],
    c=df_eps["f1"], norm=norm,
    marker="o", s=40, alpha=0.85,
    depthshade=False
)
sc_w = ax.scatter(
    df_w["f2"], -df_w["f3"], df_w["f1"],
    c=df_w["f1"], norm=norm,
    marker="x", s=35, alpha=0.95,
    depthshade=False
)
ax.set_xlabel("f2 (coste)", labelpad=10)
ax.set_ylabel("-f3 (malestar)", labelpad=10)
ax.set_zlabel("f1 (equidad)", labelpad=10)
ax.set_title("Frontera Pareto en 3D: (f2, -f3, f1)", pad=16)
ax.view_init(elev=22, azim=-55)
ax.grid(True, alpha=0.25)

for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
    axis.pane.set_alpha(0.0)
    
import matplotlib.tri as mtri

df_surf = pd.concat([df_eps, df_w], ignore_index=True).drop_duplicates()

x = df_surf["f2"].values
y = -df_surf["f3"].values
z = df_surf["f1"].values

tri = mtri.Triangulation(x, y)

ax.plot_trisurf(
    tri, z,
    cmap="viridis",
    alpha=0.25,
    edgecolor="none"
)






# =========================
# SOLUCIONES REPRESENTATIVAS
# =========================

representativas_10 = pd.read_csv("representativas_10_2.csv")
df_rep = representativas_10.copy()
df_rep["tag"] = df_rep["tag"].fillna("representativa").astype(str).str.strip()
df_rep["method"] = df_rep["method"].fillna("rep").astype(str).str.strip()

# marcador según método
marker_map = {
    "eps": "s",          # cuadrado
    "weighting": "D"     # diamante
}

# gráfico 2D
fig, ax = plt.subplots(figsize=(9, 6))

sc1 = ax.scatter(
    df_eps["f2"], -df_eps["f3"],
    c=df_eps["f1"], norm=norm,
    marker="o", alpha=0.75, label="Pareto ε-constraints"
)

sc2 = ax.scatter(
    df_w["f2"], -df_w["f3"],
    c=df_w["f1"], norm=norm,
    marker="x", alpha=0.95, label="Pareto weighting"
)

label_map = {
    "extremo: min f2 (mínimo coste)": "min f2",
    "extremo: max f3 (máximo bienestar)": "max f3",
    "extremo: min f1 (máxima equidad)": "min f1",
    "compromise: Linf": "L∞",
    "compromise: L2": "L2",
    "compromise: L1": "L1",
    "diversidad: farthest-point": "div"
}

label_offsets = {
    "L1": (10, 8),
    "L2": (10, -18),
    "L∞": (-30, 10),
    "min f1": (8, 8),
    "min f2": (8, 8),
    "max f3": (8, 8),
    "div": (8, 8),
}

df_rep["label_short"] = df_rep["tag"].map(label_map).fillna(df_rep["tag"])

for _, row in df_rep.iterrows():
    ax.scatter(
        row["f2"], -row["f3"],
        c=[row["f1"]], norm=norm,
        cmap="viridis",
        marker=marker_map.get(row["method"], "*"),
        s=180,
        edgecolors="black",
        linewidths=1.2,
        zorder=5
    )
    
    label = row["label_short"]
    dx, dy = label_offsets.get(label, (6, 6))
    
    ax.annotate(
        label,
        (row["f2"], -row["f3"]),
        xytext=(dx, dy),
        textcoords="offset points",
        fontsize=9
    )

ax.set_xlabel("f2 (coste)")
ax.set_ylabel("-f3 (malestar)")
ax.set_title("Pareto aproximado con soluciones representativas destacadas")
ax.grid(True, alpha=0.25)

cbar = fig.colorbar(sc1, ax=ax, pad=0.02)
cbar.set_label("f1 (inequidad)")

ax.legend()
fig.tight_layout()
plt.show()






#____________________________________________________________
# frontera pareto 2D o proyecciones bidimensionales

def pareto_front_2d(df, x, y, sense_x="min", sense_y="min"):
    """
    Devuelve puntos no dominados en 2D (x,y) con sentidos 'min'/'max'.
    Dominancia: A domina B si es >= igual de bueno en ambos y estrictamente mejor en alguno.
    """
    data = df[[x, y]].to_numpy().astype(float)

    if sense_x == "max":
        data[:, 0] *= -1
    if sense_y == "max":
        data[:, 1] *= -1

    n = len(df)
    dominated = np.zeros(n, dtype=bool)

    for i in range(n):
        if dominated[i]:
            continue
        dom_i = (data[:, 0] <= data[i, 0]) & (data[:, 1] <= data[i, 1]) & (
            (data[:, 0] < data[i, 0]) | (data[:, 1] < data[i, 1])
        )
        dom_i[i] = False
        if np.any(dom_i):
            dominated[i] = True

    front = df.loc[~dominated].copy()

    ascending = (sense_x == "min")
    front = front.sort_values(by=x, ascending=ascending)
    return front

df_pareto = df_union.copy()

def pretty_axis(ax, xlabel, ylabel, title, sci_x=False, sci_y=False):
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.25)

    if sci_x:
        fmt = ScalarFormatter(useMathText=True)
        fmt.set_scientific(True)
        fmt.set_powerlimits((0, 0))
        ax.xaxis.set_major_formatter(fmt)
    if sci_y:
        fmt = ScalarFormatter(useMathText=True)
        fmt.set_scientific(True)
        fmt.set_powerlimits((0, 0))
        ax.yaxis.set_major_formatter(fmt)


df_pareto["minus_f3"] = -df_pareto["f3"]

# (a) f1 vs f2 : min vs min
x, y = "f1", "f2"
front1 = pareto_front_2d(df_pareto, x, y, sense_x="min", sense_y="min")

fig, ax = plt.subplots(figsize=(8.5, 6))
ax.scatter(df_pareto[x], df_pareto[y], alpha=0.35, label="Pareto 3D (proyección)")
ax.scatter(front1[x], front1[y], alpha=0.95, label="Frontera 2D en la proyección")
ax.plot(front1[x], front1[y], linewidth=1)
pretty_axis(ax, "Equidad (f1) ↓", "Coste (f2) ↓",
            "Proyección sobre Pareto 3D: f1 vs f2", sci_y=True)
ax.legend()
plt.tight_layout()
plt.show()


# (b) f1 vs f3 : min vs max  (f3 tal cual, más alto mejor)
x, y = "f1", "minus_f3"
front2 = pareto_front_2d(df_pareto, x, y, sense_x="min", sense_y="min")

fig, ax = plt.subplots(figsize=(8.5, 6))
ax.scatter(df_pareto[x], df_pareto[y], alpha=0.35, label="Pareto 3D (proyección)")
ax.scatter(front2[x], front2[y], alpha=0.95, label="Frontera 2D en la proyección")
ax.plot(front2[x], front2[y], linewidth=1)
pretty_axis(ax, "Equidad (f1) ↓", "Malestar (-f3) ↓",
            "Proyección sobre Pareto 3D: f1 vs -f3")
ax.legend()
plt.tight_layout()
plt.show()


# (c) f2 vs f3 : min vs max
x, y = "f2", "minus_f3"
front3 = pareto_front_2d(df_pareto, x, y, sense_x="min", sense_y="min")

fig, ax = plt.subplots(figsize=(8.5, 6))
ax.scatter(df_pareto[x], df_pareto[y], alpha=0.35, label="Pareto 3D (proyección)")
ax.scatter(front3[x], front3[y], alpha=0.95, label="Frontera 2D en la proyección")
ax.plot(front3[x],front3[y], linewidth=1)
pretty_axis(ax, "Coste (f2) ↓", "Malestar (-f3) ↓",
            "Proyección sobre Pareto 3D: f2 vs -f3", sci_x=True)
ax.legend()
plt.tight_layout()
plt.show()


#________________________________________________________________________________________
# Cálculo de trade-offs

def tradeoffs_any_slope(front, x, y, sense_x="min", sense_y="min", sol_id_col="sol_id"):

    df = front.copy()

    # si hay múltiples puntos con mismo x, nos quedamos con el "mejor y"
    if sense_y == "min":
        df = df.sort_values(by=[x, y], ascending=[True, True])
    else:  # max
        df = df.sort_values(by=[x, y], ascending=[True, False])

    df = df.drop_duplicates(subset=[x], keep="first")

    df = df.sort_values(by=x, ascending=(sense_x == "min")).reset_index(drop=True)

    df["dx"] = df[x].diff()
    df["dy"] = df[y].diff()
    df["slope_dy_dx"] = df["dy"] / df["dx"]

    df["tradeoff_abs"] = df["dy"].abs() / df["dx"].abs()

    df_valid = df.dropna(subset=["dx", "dy"]).copy()
    df_valid = df_valid[df_valid["dx"] != 0]

    cols = []
    if sol_id_col in df_valid.columns:
        cols.append(sol_id_col)
    cols += [x, y, "dx", "dy", "slope_dy_dx", "tradeoff_abs"]
    return df_valid[cols], df 


def summarize_tradeoffs_slopes(tr_df, x_label, y_label, units_y="", top_k=5):
    if len(tr_df) == 0:
        return f"No se pudieron calcular pendientes: probablemente todos los puntos tienen {x_label} idéntico o hay muy pocos puntos."

    med = tr_df["tradeoff_abs"].median()
    q25 = tr_df["tradeoff_abs"].quantile(0.25)
    q75 = tr_df["tradeoff_abs"].quantile(0.75)

    tmp = tr_df.copy()
    tmp["abs_trade"] = tmp["tradeoff_abs"]
    worst = tmp.sort_values("abs_trade", ascending=False).head(top_k)

    lines = []
    lines.append(
        f"Trade-off típico (mediana) entre {x_label} y {y_label}: "
        f"{med:,.3g} {units_y} por 1 unidad de cambio en {x_label} "
        f"(IQR: {q25:,.3g}–{q75:,.3g})."
    )
    lines.append("Segmentos con mayor intercambio (trade-off más alto):")
    for _, r in worst.iterrows():
        lines.append(
            f"  - Δ{x_label}={r['dx']:.3g}, Δ{y_label}={r['dy']:.3g} -> "
            f"|Δ{y_label}|/|Δ{x_label}|={r['tradeoff_abs']:.3g}"
        )
    return "\n".join(lines)
    return "\n".join(lines)



# _______________________________________________________________________
# Vamos a calcular tradeoffs solo teniendo en cuenta 2 objetivos 


def dominates_2d(a, b, objx, objy, sense_x="min", sense_y="min"):
    def no_worse(v1, v2, sense):
        return v1 <= v2 if sense == "min" else v1 >= v2

    def strictly_better(v1, v2, sense):
        return v1 < v2 if sense == "min" else v1 > v2

    nw_x = no_worse(a[objx], b[objx], sense_x)
    nw_y = no_worse(a[objy], b[objy], sense_y)

    sb_x = strictly_better(a[objx], b[objx], sense_x)
    sb_y = strictly_better(a[objy], b[objy], sense_y)

    return (nw_x and nw_y) and (sb_x or sb_y)


def pareto_filter_2d(sols, objx, objy, sense_x="min", sense_y="min"):
    eff = []
    for i, s in enumerate(sols):
        dominated = False
        for j, t in enumerate(sols):
            if i != j and dominates_2d(t, s, objx, objy, sense_x, sense_y):
                dominated = True
                break
        if not dominated:
            eff.append(s)
    return eff

def epsilon_search_2obj(pair, primary, n=15, time_limit=None, outputflag=0):

    valid_pairs = [("f1", "f2"), ("f2", "f3")]
    if pair not in valid_pairs:
        raise ValueError("pair debe ser ('f1','f2') o ('f2','f3').")

    if primary not in pair:
        raise ValueError("primary debe pertenecer al par.")

    # extremos monoobjetivo del par
    ext_a = solve_single_objective(pair[0], outputflag=outputflag)
    ext_b = solve_single_objective(pair[1], outputflag=outputflag)

    if ext_a is None or ext_b is None:
        raise RuntimeError("No se pudieron obtener extremos monoobjetivo.")

    summaries, B_all, X_all, Xres_all, Xnew_all = [], [], [], [], []
    solutions = []

    # CASO 1: f1 vs f2   (min, min)
    if pair == ("f1", "f2"):
        f1_vals = [ext_a["f1"], ext_b["f1"]]
        f2_vals = [ext_a["f2"], ext_b["f2"]]

        f1_min, f1_max = min(f1_vals), max(f1_vals)
        f2_min, f2_max = min(f2_vals), max(f2_vals)

        if primary == "f1":
            eps_grid = linspace_safe(f2_min, f2_max, n)

            for eps2 in eps_grid:
                m, obj, vars_ = build_model()
                m.setObjective(obj["f1"], GRB.MINIMIZE)
                m.addConstr(obj["f2"] <= float(eps2), name="eps_f2")

                if time_limit is not None:
                    m.Params.TimeLimit = time_limit
                m.Params.OutputFlag = outputflag
                m.optimize()

                if m.status == GRB.OPTIMAL:
                    sol_id = f"eps2d_f1f2_f1_{len(summaries)}"
                    meta = {"pair": "f1_f2", "primary": "f1", "eps_f2": float(eps2)}
                    summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                        sol_id=sol_id,
                        method="eps_2obj",
                        m=m,
                        obj=obj,
                        vars_=vars_,
                        extra_meta=meta,
                        x_threshold=1e-6
                    )
                    summaries.append(summary)
                    solutions.append(summary)
                    B_all.extend(B_rows)
                    X_all.extend(X_rows)
                    Xres_all.extend(Xres_rows)
                    Xnew_all.extend(Xnew_rows)

        elif primary == "f2":
            eps_grid = linspace_safe(f1_min, f1_max, n)

            for eps1 in eps_grid:
                m, obj, vars_ = build_model()
                m.setObjective(obj["f2"], GRB.MINIMIZE)
                m.addConstr(obj["f1"] <= float(eps1), name="eps_f1")

                if time_limit is not None:
                    m.Params.TimeLimit = time_limit
                m.Params.OutputFlag = outputflag
                m.optimize()

                if m.status == GRB.OPTIMAL:
                    sol_id = f"eps2d_f1f2_f2_{len(summaries)}"
                    meta = {"pair": "f1_f2", "primary": "f2", "eps_f1": float(eps1)}
                    summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                        sol_id=sol_id,
                        method="eps_2obj",
                        m=m,
                        obj=obj,
                        vars_=vars_,
                        extra_meta=meta,
                        x_threshold=1e-6
                    )
                    summaries.append(summary)
                    solutions.append(summary)
                    B_all.extend(B_rows)
                    X_all.extend(X_rows)
                    Xres_all.extend(Xres_rows)
                    Xnew_all.extend(Xnew_rows)

        efficient = pareto_filter_2d(solutions, "f1", "f2", "min", "min")

    # CASO 2: f2 vs f3   (min, max)
    elif pair == ("f2", "f3"):
        f2_vals = [ext_a["f2"], ext_b["f2"]]
        f3_vals = [ext_a["f3"], ext_b["f3"]]

        f2_min, f2_max = min(f2_vals), max(f2_vals)
        f3_min, f3_max = min(f3_vals), max(f3_vals)

        if primary == "f2":
            eps_grid = linspace_safe(f3_min, f3_max, n)

            for eps3 in eps_grid:
                m, obj, vars_ = build_model()
                m.setObjective(obj["f2"], GRB.MINIMIZE)
                m.addConstr(obj["f3"] >= float(eps3), name="eps_f3")

                if time_limit is not None:
                    m.Params.TimeLimit = time_limit
                m.Params.OutputFlag = outputflag
                m.optimize()

                if m.status == GRB.OPTIMAL:
                    sol_id = f"eps2d_f2f3_f2_{len(summaries)}"
                    meta = {"pair": "f2_f3", "primary": "f2", "eps_f3": float(eps3)}
                    summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                        sol_id=sol_id,
                        method="eps_2obj",
                        m=m,
                        obj=obj,
                        vars_=vars_,
                        extra_meta=meta,
                        x_threshold=1e-6
                    )
                    summaries.append(summary)
                    solutions.append(summary)
                    B_all.extend(B_rows)
                    X_all.extend(X_rows)
                    Xres_all.extend(Xres_rows)
                    Xnew_all.extend(Xnew_rows)

        elif primary == "f3":
            eps_grid = linspace_safe(f2_min, f2_max, n)

            for eps2 in eps_grid:
                m, obj, vars_ = build_model()
                m.setObjective(obj["f3"], GRB.MAXIMIZE)
                m.addConstr(obj["f2"] <= float(eps2), name="eps_f2")

                if time_limit is not None:
                    m.Params.TimeLimit = time_limit
                m.Params.OutputFlag = outputflag
                m.optimize()

                if m.status == GRB.OPTIMAL:
                    sol_id = f"eps2d_f2f3_f3_{len(summaries)}"
                    meta = {"pair": "f2_f3", "primary": "f3", "eps_f2": float(eps2)}
                    summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                        sol_id=sol_id,
                        method="eps_2obj",
                        m=m,
                        obj=obj,
                        vars_=vars_,
                        extra_meta=meta,
                        x_threshold=1e-6
                    )
                    summaries.append(summary)
                    solutions.append(summary)
                    B_all.extend(B_rows)
                    X_all.extend(X_rows)
                    Xres_all.extend(Xres_rows)
                    Xnew_all.extend(Xnew_rows)

        efficient = pareto_filter_2d(solutions, "f2", "f3", "min", "max")

    return {
        "extremos": {pair[0]: ext_a, pair[1]: ext_b},
        "raw": summaries,
        "efficient": efficient,
        "B_rows": B_all,
        "X_rows": X_all,
        "Xres_rows": Xres_all,
        "Xnew_rows": Xnew_all
    }

def weighted_sum_search_2obj(pair, step=0.05, time_limit=None, outputflag=0):

    valid_pairs = [("f1", "f2"), ("f2", "f3")]
    if pair not in valid_pairs:
        raise ValueError("pair debe ser ('f1','f2') o ('f2','f3').")

    ext_a = solve_single_objective(pair[0], outputflag=outputflag)
    ext_b = solve_single_objective(pair[1], outputflag=outputflag)

    if ext_a is None or ext_b is None:
        raise RuntimeError("No se pudieron obtener extremos monoobjetivo.")

    summaries, B_all, X_all, Xres_all, Xnew_all = [], [], [], [], []
    solutions = []

    vals = np.arange(0, 1 + 1e-9, step)

    if pair == ("f1", "f2"):
        f1_min, f1_max = min(ext_a["f1"], ext_b["f1"]), max(ext_a["f1"], ext_b["f1"])
        f2_min, f2_max = min(ext_a["f2"], ext_b["f2"]), max(ext_a["f2"], ext_b["f2"])

        if abs(f1_max - f1_min) < 1e-12:
            f1_max = f1_min + 1.0
        if abs(f2_max - f2_min) < 1e-12:
            f2_max = f2_min + 1.0

        for w1 in vals:
            w2 = 1.0 - w1

            m, obj, vars_ = build_model()

            f1n = (obj["f1"] - f1_min) / (f1_max - f1_min)
            f2n = (obj["f2"] - f2_min) / (f2_max - f2_min)

            m.setObjective(w1 * f1n + w2 * f2n, GRB.MINIMIZE)

            if time_limit is not None:
                m.Params.TimeLimit = time_limit
            m.Params.OutputFlag = outputflag
            m.optimize()

            if m.status == GRB.OPTIMAL:
                sol_id = f"w2d_f1f2_{len(summaries)}"
                meta = {"pair": "f1_f2", "w1": float(w1), "w2": float(w2)}
                summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                    sol_id=sol_id,
                    method="weighting_2obj",
                    m=m,
                    obj=obj,
                    vars_=vars_,
                    extra_meta=meta,
                    x_threshold=1e-6
                )
                summaries.append(summary)
                solutions.append(summary)
                B_all.extend(B_rows)
                X_all.extend(X_rows)
                Xres_all.extend(Xres_rows)
                Xnew_all.extend(Xnew_rows)

        efficient = pareto_filter_2d(solutions, "f1", "f2", "min", "min")

    elif pair == ("f2", "f3"):
        f2_min, f2_max = min(ext_a["f2"], ext_b["f2"]), max(ext_a["f2"], ext_b["f2"])
        f3_min, f3_max = min(ext_a["f3"], ext_b["f3"]), max(ext_a["f3"], ext_b["f3"])

        if abs(f2_max - f2_min) < 1e-12:
            f2_max = f2_min + 1.0
        if abs(f3_max - f3_min) < 1e-12:
            f3_max = f3_min + 1.0

        for w2 in vals:
            w3 = 1.0 - w2

            m, obj, vars_ = build_model()

            f2n = (obj["f2"] - f2_min) / (f2_max - f2_min)
            f3n = (obj["f3"] - f3_min) / (f3_max - f3_min)

            m.setObjective(w2 * f2n + w3 * (1 - f3n), GRB.MINIMIZE)

            if time_limit is not None:
                m.Params.TimeLimit = time_limit
            m.Params.OutputFlag = outputflag
            m.optimize()

            if m.status == GRB.OPTIMAL:
                sol_id = f"w2d_f2f3_{len(summaries)}"
                meta = {"pair": "f2_f3", "w2": float(w2), "w3": float(w3)}
                summary, B_rows, X_rows, Xres_rows, Xnew_rows = extraer_soluciones(
                    sol_id=sol_id,
                    method="weighting_2obj",
                    m=m,
                    obj=obj,
                    vars_=vars_,
                    extra_meta=meta,
                    x_threshold=1e-6
                )
                summaries.append(summary)
                solutions.append(summary)
                B_all.extend(B_rows)
                X_all.extend(X_rows)
                Xres_all.extend(Xres_rows)
                Xnew_all.extend(Xnew_rows)

        efficient = pareto_filter_2d(solutions, "f2", "f3", "min", "max")

    return {
        "extremos": {pair[0]: ext_a, pair[1]: ext_b},
        "raw": summaries,
        "efficient": efficient,
        "B_rows": B_all,
        "X_rows": X_all,
        "Xres_rows": Xres_all,
        "Xnew_rows": Xnew_all
    }

# PAREJA 1: f1 vs f2

res_eps_f1f2_a = epsilon_search_2obj(pair=("f1", "f2"), primary="f1", n=25, outputflag=0)
res_eps_f1f2_b = epsilon_search_2obj(pair=("f1", "f2"), primary="f2", n=25, outputflag=0)

sols_f1f2 = res_eps_f1f2_a["efficient"] + res_eps_f1f2_b["efficient"]
sols_f1f2 = pareto_filter_2d(sols_f1f2, "f1", "f2", "min", "min")
df_f1f2_eps = pd.DataFrame(sols_f1f2).round({"f1": 6, "f2": 2, "f3": 6}).drop_duplicates()

res_w_f1f2 = weighted_sum_search_2obj(pair=("f1", "f2"), step=0.05, outputflag=0)
df_f1f2_w = pd.DataFrame(res_w_f1f2["efficient"]).round({"f1": 6, "f2": 2, "f3": 6}).drop_duplicates()

df_f1f2_union = pd.concat([df_f1f2_eps, df_f1f2_w], ignore_index=True).drop_duplicates()
front_f1f2 = pd.DataFrame(
    pareto_filter_2d(df_f1f2_union.to_dict("records"), "f1", "f2", "min", "min")
).sort_values("f1").reset_index(drop=True)


# PAREJA 2: f2 vs f3

res_eps_f2f3_a = epsilon_search_2obj(pair=("f2", "f3"), primary="f2", n=25, outputflag=0)
res_eps_f2f3_b = epsilon_search_2obj(pair=("f2", "f3"), primary="f3", n=25, outputflag=0)

sols_f2f3 = res_eps_f2f3_a["efficient"] + res_eps_f2f3_b["efficient"]
sols_f2f3 = pareto_filter_2d(sols_f2f3, "f2", "f3", "min", "max")
df_f2f3_eps = pd.DataFrame(sols_f2f3).round({"f1": 6, "f2": 2, "f3": 6}).drop_duplicates()

res_w_f2f3 = weighted_sum_search_2obj(pair=("f2", "f3"), step=0.05, outputflag=0)
df_f2f3_w = pd.DataFrame(res_w_f2f3["efficient"]).round({"f1": 6, "f2": 2, "f3": 6}).drop_duplicates()

df_f2f3_union = pd.concat([df_f2f3_eps, df_f2f3_w], ignore_index=True).drop_duplicates()
front_f2f3 = pd.DataFrame(
    pareto_filter_2d(df_f2f3_union.to_dict("records"), "f2", "f3", "min", "max")
).sort_values("f2").reset_index(drop=True)



# GRÁFICAS

fig, ax = plt.subplots(figsize=(8.5, 6))
ax.scatter(df_f1f2_union["f1"], df_f1f2_union["f2"], alpha=0.30, label="Soluciones 2D")
ax.scatter(front_f1f2["f1"], front_f1f2["f2"], alpha=0.95, label="Frontera Pareto 2D")
ax.plot(front_f1f2["f1"], front_f1f2["f2"], linewidth=1.5)
pretty_axis(ax, "Equidad (f1) ↓", "Coste (f2) ↓", "Pareto biobjetivo: f1 vs f2", sci_y=True)
ax.legend()
plt.tight_layout()
plt.show()

fig, ax = plt.subplots(figsize=(8.5, 6))
ax.scatter(df_f2f3_union["f2"], df_f2f3_union["f3"], alpha=0.30, label="Soluciones 2D")
ax.scatter(front_f2f3["f2"], front_f2f3["f3"], alpha=0.95, label="Frontera Pareto 2D")
ax.plot(front_f2f3["f2"], front_f2f3["f3"], linewidth=1.5)
pretty_axis(ax, "Coste (f2) ↓", "Bienestar (f3) ↑", "Pareto biobjetivo: f2 vs f3", sci_x=True)
ax.legend()
plt.tight_layout()
plt.show()

# TRADE-OFFS

tr_12, clean_12 = tradeoffs_any_slope(front_f1f2, "f1", "f2", "min", "min")
tr_12 = tr_12[(np.abs(tr_12["dx"]) > 1e-6) & (tr_12["tradeoff_abs"] < 1e12)]

print("\n=== Trade-offs biobjetivo f1 vs f2 ===")
print(summarize_tradeoffs_slopes(tr_12, "f1", "f2", units_y="€"))

tr_23, clean_23 = tradeoffs_any_slope(front_f2f3, "f2", "f3", "min", "max")
tr_23 = tr_23[(np.abs(tr_23["dx"]) > 1e-6) & (tr_23["tradeoff_abs"] < 1e12)]

print("\n=== Trade-offs biobjetivo f2 vs f3 ===")
print(summarize_tradeoffs_slopes(tr_23, "f2", "f3", units_y="unid. bienestar"))

# QUEREMOS EL ÚLTIMO MÁS INTERPRETABE
# ============================================================
# TRADE-OFFS BIOBJETIVO f2 vs f3
# en euros por unidad de bienestar: |Δf2| / |Δf3|
# ============================================================

def tradeoffs_cost_per_wellbeing(front, x_cost="f2", y_well="f3"):
    """
    Calcula trade-offs locales sobre la frontera f2-f3 como:

        |Δf2| / |Δf3|

    Interpretación:
        euros necesarios por cada unidad adicional de bienestar.

    Se asume que la frontera viene ordenada por f2 ascendente.
    """
    df = front[[x_cost, y_well]].copy().reset_index(drop=True)

    df["dx_cost"] = df[x_cost].diff()
    df["dy_well"] = df[y_well].diff()

    eps = 1e-12
    df["tradeoff_eur_per_well"] = np.where(
        df["dy_well"].abs() > eps,
        df["dx_cost"].abs() / df["dy_well"].abs(),
        np.nan
    )

    out = df.dropna(subset=["dx_cost", "dy_well", "tradeoff_eur_per_well"]).copy()
    return out


def summarize_tradeoffs_cost_per_wellbeing(tr_df, top_k=5):
    if len(tr_df) == 0:
        print("No se pudieron calcular trade-offs para f2 vs f3.")
        return

    vals = tr_df["tradeoff_eur_per_well"].dropna()

    q25 = vals.quantile(0.25)
    med = vals.median()
    q75 = vals.quantile(0.75)

    print("\n=== Trade-offs biobjetivo f2 vs f3 ===")
    print(
        f"Trade-off típico (mediana): {med:.3e} € por 1 unidad de bienestar "
        f"(IQR: {q25:.3e}–{q75:.3e})"
    )

    top = tr_df.nlargest(top_k, "tradeoff_eur_per_well")
    print("Segmentos con mayor coste marginal de bienestar:")
    for _, row in top.iterrows():
        print(
            f"  - Δf2={row['dx_cost']:.3e}, Δf3={row['dy_well']:.3e} "
            f"-> |Δf2|/|Δf3| = {row['tradeoff_eur_per_well']:.3e} €"
        )


tr_23_eur = tradeoffs_cost_per_wellbeing(front_f2f3, x_cost="f2", y_well="f3")

tr_23_eur = tr_23_eur[
    (np.abs(tr_23_eur["dy_well"]) > 1e-9) &
    (tr_23_eur["tradeoff_eur_per_well"] < 1e12)
]

summarize_tradeoffs_cost_per_wellbeing(tr_23_eur)