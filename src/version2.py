# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 13:32:59 2026

@author: glori
"""

from gurobipy import Model, GRB, quicksum
import pandas as pd

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

# Subcuotas normalizadas
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

# Pesos del BOE
w_pob = 0.50
w_renta = 0.13
w_paro = 0.15
w_mena = 0.06
w_plazas = 0.10
w_frontera = 0.02
w_insularidad = 0.02
w_dispersion = 0.02

# Cuota compuesta final
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

# Asignación ideal asociada al objetivo de equidad
T_ideal = {k: N * cuota_equidad[k] for k in K}


# Umbral de personas en situación de emergencia
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


# Empezamos el modelo

m = Model("TFG_menores")

# ============================================
# 3. VARIABLES
# ============================================

# X[i,j,k] total (res + new) PARA TODAS las comunidades
X = m.addVars(I, J, K, vtype=GRB.INTEGER, lb=0.0, name="X")

# Variables X_res y X_new SOLO para comunidades de alta llegada
X_res = m.addVars(
    llegadas_idx, J, K,
    vtype=GRB.INTEGER, lb=0.0, name="X_res"
)

X_new = m.addVars(
    llegadas_idx, J, K,
    vtype=GRB.INTEGER, lb=0.0, name="X_new"
)
# Diferencia positiva con respecto a la asignación ideal
t = m.addVars(K, vtype=GRB.CONTINUOUS, lb=0, name="t")

# B_k: nº de centros a abrir en k (entera)
B = m.addVars(K, vtype=GRB.INTEGER, lb=0, name="B")

# S_k: nº de menores en situación de emergencia en k
S = m.addVars(K, vtype=GRB.CONTINUOUS, lb=0.0, name="S")
Se = m.addVars(K, vtype=GRB.CONTINUOUS, lb=0.0, name="Se+")

# Ocupación total en cada destino k
occ = m.addVars(K, vtype=GRB.CONTINUOUS, lb=0.0, name="occ")



# ============================================
# 4. RESTRICCIONES
# ============================================

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
    
    m.addConstr(    # menores en sit. emergencia
        S[k] - B[k] * n_center_cap[k] <= Se[k],
        name=f"emergencia_{nombre[k]}"
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


# ============================================
# 5. FUNCIONES OBJETIVO
# ============================================

# f1: minimizar la desigualdad territorial
f1 = quicksum(t[k] for k in K)

# f2: minimizar costes (transporte + emergencia + centros)
f2 = quicksum(
        (X[i, j, k]) * (c_trans[i, k] + c_plaza[k]*estancia)
        for i in I for j in J for k in K
     ) \
     + quicksum(Se[k] * (lambd[k] + c_emerg[k]*estancia - c_plaza[k]*estancia) for k in K) \
     + quicksum(B[k] * c_center[k] for k in K)

# f3: maximizar preferencias y bienestar => minimizamos -f3
f3 = quicksum(
        X[i, j, k] * W[k]* alpha
        for i in I for j in J for k in K
     ) \
     + quicksum(
        X[i, j, k] * (1.0 if j == k else 0.0)*beta
        for i in I for j in J for k in K
     )\
     - quicksum(
        X_res[i, j, k] * (1.0 if (i != k and j!=k) else 0.0)*gamma
        for i in llegadas_idx for j in J for k in K
     )\
     - quicksum(
        X[i, j, k] * (1.0 if (i != k and j!=k) else 0.0)*gamma    # REVISAR SI PONER if (i != k and j!=k) 
        for i in I if i not in llegadas_idx for j in J for k in K
     )

# Configuramos modelo multiobjetivo (lexicográfico)
m.ModelSense = GRB.MINIMIZE

# Objetivo 0: minimizar f1 (desigualdades) – prioridad más alta
m.setObjectiveN(f1, index=0, priority=3, weight=1.0, name="min_desigualdad")

# Objetivo 1: minimizar f2 (coste)
m.setObjectiveN(f2, index=1, priority=1, weight=1.0, name="min_coste")

# Objetivo 2: minimizar -f3 (maximizar preferencias)
m.setObjectiveN(-f3, index=2, priority=2, weight=1.0, name="max_preferencias")



# ============================================
# 6. OPTIMIZACIÓN
# ============================================

m.optimize()

# ============================================
# 7. RESULTADOS
# ============================================

if m.status == GRB.OPTIMAL:
    print("\n*** RESULTADOS ÓPTIMOS (multiobjetivo) ***\n")

    print(f"f1 (desigualdad territorial) = {f1.getValue():.2f}")
    print(f"f2 (coste total)      = {f2.getValue():.2f}")
    print(f"f3 (bienestar)     = {f3.getValue():.2f}\n")

    print("Centros a abrir por comunidad destino k:")
    for k in K:
        print(f"  k = {k} ({nombre[k]}): B_k = {B[k].X:.0f}, "
              f"occ = {occ[k].X:.1f}, S_k = {S[k].X:.1f}, Se = {Se[k].X:.1f}")

    print("\nAsignaciones (solo las positivas):")

    for i in llegadas_idx:
        for j in J:
            for k in K:
                val_res = X_res[i, j, k].X
                val_new = X_new[i, j, k].X
                if val_res > 1e-6 or val_new > 1e-6:
                    print(f"[LLEGADAS] i={i} ({ccaa[i]}), "
                      f"j={j} ({ccaa[j]}), "
                      f"k={k} ({ccaa[k]}): "
                      f"res={val_res:.2f}, new={val_new:.2f}")

    for i in I:
        if i not in llegadas_idx:
            for j in J:
                for k in K:
                    val = X[i, j, k].X
                    if val > 1e-6:
                        print(f"[RESTO]    i={i} ({ccaa[i]}), "
                          f"j={j} ({ccaa[j]}), "
                          f"k={k} ({ccaa[k]}): "
                          f"X={val:.2f}")
else:
    print("El modelo no encontró solución óptima. Status:", m.status)

if m.status == GRB.INFEASIBLE:
    print("Modelo infactible. Calculando IIS...")
    m.computeIIS()
    m.write("modelo_iis.ilp")
    print("IIS escrito en modelo_iis.ilp")
    
print("Total de menores N =", N) 


# ============================================
# ANÁLISIS DE RESULTADOS
# ============================================

from collections import defaultdict

print("\n============================================")
print("ANÁLISIS DE RESULTADOS")
print("============================================")

# 1. Recogemos todas las asignaciones positivas

asignaciones = []

for i in I:
    for j in J:
        for k in K:
            val = X[i, j, k].X
            if val > 1e-6:
                asignaciones.append({
                    "origen": nombre[i],
                    "preferencia": nombre[j],
                    "destino": nombre[k],
                    "i": i,
                    "j": j,
                    "k": k,
                    "menores": val
                })

df_asig = pd.DataFrame(asignaciones)

# 2. Preferencias cumplidas

preferencia_cumplida = df_asig[df_asig["j"] == df_asig["k"]]["menores"].sum()

porcentaje_preferencia = 100 * preferencia_cumplida / N

print(f"\n% menores que cumplen su preferencia (j=k): {porcentaje_preferencia:.2f}%")

# 3. Menores que se mueven de su comunidad

menores_movidos = df_asig[df_asig["i"] != df_asig["k"]]["menores"].sum()

porcentaje_movidos = 100 * menores_movidos / N

print(f"% menores que se trasladan a otra comunidad (i≠k): {porcentaje_movidos:.2f}%")

# 4. Flujos origen → destino final (i → k) agregando sobre preferencias j

flujos_ik = defaultdict(float)

for _, row in df_asig.iterrows():
    flujos_ik[(row["origen"], row["destino"])] += row["menores"]

df_flujos = pd.DataFrame([
    {"origen": o, "destino": d, "menores": v}
    for (o, d), v in flujos_ik.items()
])

# 5. Función para representación en un mapa

def movimientos_desde(comunidad):

    df = df_flujos[df_flujos["origen"] == comunidad].copy()
    df = df.sort_values("menores", ascending=False)

    total = df["menores"].sum()
    df["porcentaje"] = 100 * df["menores"] / total

    return df

mov_canarias = movimientos_desde("Canarias")
print("\nMovimientos desde Canarias:")
print(mov_canarias)

# 6. Resumen por comunidad de origen

resumen_origen = []

for i in I:

    total_i = df_asig[df_asig["i"] == i]["menores"].sum()

    movidos_i = df_asig[
        (df_asig["i"] == i) &
        (df_asig["k"] != i)
    ]["menores"].sum()

    preferencia_i = df_asig[
        (df_asig["i"] == i) &
        (df_asig["j"] == df_asig["k"])
    ]["menores"].sum()

    resumen_origen.append({
        "comunidad": nombre[i],
        "total_menores": total_i,
        "movidos": movidos_i,
        "%movidos": 100 * movidos_i / total_i if total_i > 0 else 0,
        "%preferencia_cumplida": 100 * preferencia_i / total_i if total_i > 0 else 0
    })

df_resumen = pd.DataFrame(resumen_origen)

# 7. Información de capacidad por destino

capacidad = []

for k in K:
    capacidad.append({
        "comunidad": nombre[k],
        "ocupacion_final": occ[k].X,
        "centros_nuevos": B[k].X,
        "plazas_estandar": S[k].X,
        "plazas_emergencia": Se[k].X
    })

df_capacidad = pd.DataFrame(capacidad)

# 8. Exportar todo a Excel

with pd.ExcelWriter("analisis_resultados_modelo_v2.xlsx") as writer:

    df_asig.to_excel(writer, sheet_name="asignaciones_ijk", index=False)
    df_flujos.to_excel(writer, sheet_name="flujos_i_k_mapa", index=False)
    df_resumen.to_excel(writer, sheet_name="resumen_por_origen", index=False)
    df_capacidad.to_excel(writer, sheet_name="capacidad_destinos", index=False)
    mov_canarias.to_excel(writer, sheet_name="movimientos_canarias", index=False)

print("\nArchivo Excel generado: analisis_resultados_modelo_v2.xlsx")