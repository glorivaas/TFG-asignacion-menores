# -*- coding: utf-8 -*-
"""
Created on Thu Feb 19 13:53:09 2026

@author: glori
"""

from gurobipy import Model, GRB, quicksum
import pandas as pd
import numpy as np
import itertools

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
   

def eval_objectives(obj):
    return {
        "f1": float(obj["f1"].getValue()),
        "f2": float(obj["f2"].getValue()),
        "f3": float(obj["f3"].getValue()),
    }


def extract_solution_rows(sol_id, meta, obj, vars_):
    """
    Extrae resumen + variables de una solución óptima
    con formato análogo a conjuntoeficiente_completo.
    """
    vals = eval_objectives(obj)

    summary_row = {
        "sol_id": sol_id,
        **meta,
        **vals,
    }

    B_rows = []
    for k in K:
        B_rows.append({
            "sol_id": sol_id,
            **meta,
            "k": k,
            "ccaa": nombre[k],
            "B_k": float(vars_["B"][k].X),
            "occ_k": float(vars_["occ"][k].X),
            "S_k": float(vars_["S"][k].X),
            "Se_k": float(vars_["Se"][k].X),
        })

    X_rows = []
    for i in I:
        for j in J:
            for k in K:
                val = vars_["X"][i, j, k].X
                if val > 1e-6:
                    X_rows.append({
                        "sol_id": sol_id,
                        **meta,
                        "i": i,
                        "ccaa_origen": nombre[i],
                        "j": j,
                        "ccaa_pref": nombre[j],
                        "k": k,
                        "ccaa_dest": nombre[k],
                        "X": float(val),
                    })

    Xres_rows = []
    for i in llegadas_idx:
        for j in J:
            for k in K:
                val = vars_["X_res"][i, j, k].X
                if val > 1e-6:
                    Xres_rows.append({
                        "sol_id": sol_id,
                        **meta,
                        "i": i,
                        "ccaa_origen": nombre[i],
                        "j": j,
                        "ccaa_pref": nombre[j],
                        "k": k,
                        "ccaa_dest": nombre[k],
                        "X_res": float(val),
                    })

    Xnew_rows = []
    for i in llegadas_idx:
        for j in J:
            for k in K:
                val = vars_["X_new"][i, j, k].X
                if val > 1e-6:
                    Xnew_rows.append({
                        "sol_id": sol_id,
                        **meta,
                        "i": i,
                        "ccaa_origen": nombre[i],
                        "j": j,
                        "ccaa_pref": nombre[j],
                        "k": k,
                        "ccaa_dest": nombre[k],
                        "X_new": float(val),
                    })

    return summary_row, B_rows, X_rows, Xres_rows, Xnew_rows


def guardar_soluciones(summary_rows, B_rows, X_rows, Xres_rows, Xnew_rows,
                       path_summary, path_B, path_X, path_Xres, path_Xnew):
    pd.DataFrame(summary_rows).to_csv(path_summary, index=False)
    pd.DataFrame(B_rows).to_csv(path_B, index=False)
    pd.DataFrame(X_rows).to_csv(path_X, index=False)
    pd.DataFrame(Xres_rows).to_csv(path_Xres, index=False)
    pd.DataFrame(Xnew_rows).to_csv(path_Xnew, index=False)
    
    
    
def lexicografico(time_limit=120, outputflag=1):
    """
    Resuelve 6 órdenes lexicográficos posibles de (f1,f2,f3).
    Devuelve resumen + variables, con estructura exportable.
    """
    summary_rows = []
    all_B = []
    all_X = []
    all_Xres = []
    all_Xnew = []

    def expr_for(objname, obj):
        if objname in ("f1", "f2"):
            return obj[objname], GRB.MINIMIZE
        if objname == "f3":
            return -obj["f3"], GRB.MINIMIZE
        raise ValueError("objname must be f1,f2,f3")

    orders = list(itertools.permutations(["f1", "f2", "f3"], 3))

    for ord_idx, order in enumerate(orders):
        m, obj, vars_ = build_model()
        m.ModelSense = GRB.MINIMIZE

        priority_map = {order[0]: 3, order[1]: 2, order[2]: 1}

        for idx_o, name in enumerate(order):
            expr, _sense = expr_for(name, obj)
            m.setObjectiveN(expr, index=idx_o, priority=priority_map[name], weight=1.0, name=f"lex_{name}")

        if time_limit is not None:
            m.Params.TimeLimit = time_limit
        m.Params.OutputFlag = outputflag
        m.Params.TimeLimit = 120
        m.Params.MIPGap = 0.0
        m.Params.MIPFocus = 1
        m.Params.OutputFlag = outputflag
        m.optimize()

        sol_id = f"lex_{ord_idx+1}"
        meta = {
            "method": "lexicographic",
            "order": " > ".join(order),
        }

        if m.status == GRB.OPTIMAL:
            summary_row, B_rows, X_rows, Xres_rows, Xnew_rows = extract_solution_rows(
                sol_id=sol_id,
                meta=meta,
                obj=obj,
                vars_=vars_,
            )
            summary_rows.append(summary_row)
            all_B.extend(B_rows)
            all_X.extend(X_rows)
            all_Xres.extend(Xres_rows)
            all_Xnew.extend(Xnew_rows)
        else:
            summary_rows.append({
                "sol_id": sol_id,
                **meta,
                "status": int(m.status),
            })

    return {
        "summary_rows": summary_rows,
        "B_rows": all_B,
        "X_rows": all_X,
        "Xres_rows": all_Xres,
        "Xnew_rows": all_Xnew,
    }



def wgp(goals, weights_grid, scenario=None, time_limit=120, outputflag=1,
        scales=None, eps_tie=1e-6):
    """
    WGP normalizado + desempate epsilon.
    Devuelve resumen + variables, con estructura exportable.
    """
    summary_rows = []
    all_B = []
    all_X = []
    all_Xres = []
    all_Xnew = []

    if scales is None:
        scales = {"f1": 1.0, "f2": 1.0, "f3": 1.0}

    for s_idx, (w1, w2, w3) in enumerate(weights_grid, start=1):
        m, obj, vars_ = build_model()

        d1 = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="d1_plus")
        d2 = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="d2_plus")
        d3 = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="d3_minus")

        if "f1" in goals:
            g1 = float(goals["f1"]["value"])
            m.addConstr(obj["f1"] - g1 <= d1, name="goal_f1")

        if "f2" in goals:
            g2 = float(goals["f2"]["value"])
            m.addConstr(obj["f2"] - g2 <= d2, name="goal_f2")

        if "f3" in goals:
            g3 = float(goals["f3"]["value"])
            m.addConstr(g3 - obj["f3"] <= d3, name="goal_f3")

        d1n = d1 / float(scales.get("f1", 1.0))
        d2n = d2 / float(scales.get("f2", 1.0))
        d3n = d3 / float(scales.get("f3", 1.0))

        wgp_main = w1 * d1n + w2 * d2n + w3 * d3n

        f1n = obj["f1"] / float(scales.get("f1", 1.0))
        f2n = obj["f2"] / float(scales.get("f2", 1.0))
        f3n = obj["f3"] / float(scales.get("f3", 1.0))
        tie_break = (f1n + f2n - f3n)

        m.setObjective(wgp_main + float(eps_tie) * tie_break, GRB.MINIMIZE)

        if time_limit is not None:
            m.Params.TimeLimit = time_limit
        m.Params.OutputFlag = outputflag
        m.Params.MIPGap = 0.01
        m.Params.MIPFocus = 1
        m.Params.Heuristics = 0.2
        m.Params.Threads = 12
        m.optimize()

        sol_id = f"wgp_{scenario}_{s_idx}"
        meta = {
            "method": "wgp",
            "scenario": scenario,
            "g1": goals["f1"]["value"] if "f1" in goals else None,
            "g2": goals["f2"]["value"] if "f2" in goals else None,
            "g3": goals["f3"]["value"] if "f3" in goals else None,
            "w1": float(w1),
            "w2": float(w2),
            "w3": float(w3),
        }

        if m.status == GRB.OPTIMAL:
            summary_row, B_rows, X_rows, Xres_rows, Xnew_rows = extract_solution_rows(
                sol_id=sol_id,
                meta={
                    **meta,
                    "wgp_score": float((w1 * (d1.X / scales["f1"])
                                        + w2 * (d2.X / scales["f2"])
                                        + w3 * (d3.X / scales["f3"]))),
                    "d1_plus": float(d1.X),
                    "d2_plus": float(d2.X),
                    "d3_minus": float(d3.X),
                },
                obj=obj,
                vars_=vars_,
            )
            summary_rows.append(summary_row)
            all_B.extend(B_rows)
            all_X.extend(X_rows)
            all_Xres.extend(Xres_rows)
            all_Xnew.extend(Xnew_rows)
        else:
            summary_rows.append({
                "sol_id": sol_id,
                **meta,
                "status": int(m.status),
            })

    return {
        "summary_rows": summary_rows,
        "B_rows": all_B,
        "X_rows": all_X,
        "Xres_rows": all_Xres,
        "Xnew_rows": all_Xnew,
    }



def percentile_goals(csv_path):
    df = pd.read_csv(csv_path)

    goals = {
        "f1": {
            "sense": "<=",
            "p25": np.percentile(df["f1"], 25),
            "p50": np.percentile(df["f1"], 50),
            "p75": np.percentile(df["f1"], 75),
        },
        "f2": {
            "sense": "<=",
            "p25": np.percentile(df["f2"], 25),
            "p50": np.percentile(df["f2"], 50),
            "p75": np.percentile(df["f2"], 75),
        },
        "f3": {
            "sense": ">=",
            "p25": np.percentile(df["f3"], 25),
            "p50": np.percentile(df["f3"], 50),
            "p75": np.percentile(df["f3"], 75),
        }
    }

    print("\nPercentiles calculados:")
    for f in goals:
        print(f"{f}: P25={goals[f]['p25']:.4g}, "
              f"P50={goals[f]['p50']:.4g}, "
              f"P75={goals[f]['p75']:.4g}")

    return goals


# ESCENARIOS WGP SUBJETIVOS
# Analizamos los rangos de los objetivos observados en el conjunto eficiente,
# para hacernos una idea de qué metas establecer.

def resumen_rangos(csv_path):
    """
    Resume el rango observado de f1, f2 y f3.
    """
    df = pd.read_csv(csv_path)

    resumen = pd.DataFrame({
        "objetivo": ["f1", "f2", "f3"],
        "min": [df["f1"].min(), df["f2"].min(), df["f3"].min()],
        "p25": [np.percentile(df["f1"], 25), np.percentile(df["f2"], 25), np.percentile(df["f3"], 25)],
        "p50": [np.percentile(df["f1"], 50), np.percentile(df["f2"], 50), np.percentile(df["f3"], 50)],
        "p75": [np.percentile(df["f1"], 75), np.percentile(df["f2"], 75), np.percentile(df["f3"], 75)],
        "max": [df["f1"].max(), df["f2"].max(), df["f3"].max()],
    })

    print("\nRango observado de los objetivos:")
    print(resumen.to_string(index=False))

    return resumen

# lexicográfico: 6 órdenes
lex_results = lexicografico(time_limit=None, outputflag=0)

guardar_soluciones(
    lex_results["summary_rows"],
    lex_results["B_rows"],
    lex_results["X_rows"],
    lex_results["Xres_rows"],
    lex_results["Xnew_rows"],
    path_summary="lexicographic_summary2.csv",
    path_B="lexicographic_B2.csv",
    path_X="lexicographic_Xpos2.csv",
    path_Xres="lexicographic_Xres_pos2.csv",
    path_Xnew="lexicographic_Xnew_pos2.csv",
)
print("Guardados archivos lexicográficos")

percentiles = percentile_goals("pareto_global_summary.csv")

scales = {
    "f1": float(percentiles["f1"]["p75"] - percentiles["f1"]["p25"] + 1e-9),
    "f2": float(percentiles["f2"]["p75"] - percentiles["f2"]["p25"] + 1e-9),
    "f3": float(percentiles["f3"]["p75"] - percentiles["f3"]["p25"] + 1e-9),
}

rangos = resumen_rangos("pareto_global_summary.csv")

expert_scenarios = [
    {
        "scenario": "equilibrado_exigente",
        "description": "Escenario exigente en los tres criterios, buscando un compromiso real entre equidad, coste y bienestar.",
        "goals": {
            "f1": {"sense": "<=", "value": 1400.0},
            "f2": {"sense": "<=", "value": 0.990e9},
            "f3": {"sense": ">=", "value": 51000.0},
        },
        "weights": [(0.34, 0.33, 0.33)],
    },
    {
        "scenario": "restriccion_presupuestaria_dura",
        "description": "Escenario con fuerte restricción presupuestaria, manteniendo requisitos razonables en equidad y bienestar.",
        "goals": {
            "f1": {"sense": "<=", "value": 1600.0},
            "f2": {"sense": "<=", "value": 9.8e8},
            "f3": {"sense": ">=", "value": 45000.0},
        },
        "weights": [(0.25, 0.50, 0.25)],
    },
    {
        "scenario": "bienestar_ambicioso",
        "description": "Escenario orientado a garantizar niveles muy altos de bienestar, admitiendo cierto sacrificio en coste y equidad.",
        "goals": {
            "f1": {"sense": "<=", "value": 1600.0},
            "f2": {"sense": "<=", "value": 1.00e9},
            "f3": {"sense": ">=", "value": 74000.0},
        },
        "weights": [(0.10, 0.10, 0.80)],
    },
]

wgp_summary = []
wgp_B = []
wgp_X = []
wgp_Xres = []
wgp_Xnew = []

for sc in expert_scenarios:
    sols = wgp(
        goals=sc["goals"],
        weights_grid=sc["weights"],
        scenario=sc["scenario"],
        time_limit=None,
        outputflag=0,
        scales=scales,
        eps_tie=1e-6,
    )

    for row in sols["summary_rows"]:
        row["description"] = sc["description"]

    for row in sols["B_rows"]:
        row["description"] = sc["description"]

    for row in sols["X_rows"]:
        row["description"] = sc["description"]

    for row in sols["Xres_rows"]:
        row["description"] = sc["description"]

    for row in sols["Xnew_rows"]:
        row["description"] = sc["description"]

    wgp_summary.extend(sols["summary_rows"])
    wgp_B.extend(sols["B_rows"])
    wgp_X.extend(sols["X_rows"])
    wgp_Xres.extend(sols["Xres_rows"])
    wgp_Xnew.extend(sols["Xnew_rows"])

guardar_soluciones(
    wgp_summary,
    wgp_B,
    wgp_X,
    wgp_Xres,
    wgp_Xnew,
    path_summary="wgp_summary2.csv",
    path_B="wgp_B2.csv",
    path_X="wgp_Xpos2.csv",
    path_Xres="wgp_Xres_pos2.csv",
    path_Xnew="wgp_Xnew_pos2.csv",
)
print("Guardados archivos WGP")