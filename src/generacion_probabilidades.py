# -*- coding: utf-8 -*-
"""
Created on Thu Dec 11 14:52:00 2025

@author: glori
"""

import pandas as pd
import numpy as np


CCAA = [
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
IDX = {c: i for i, c in enumerate(CCAA)}

NEIGHBORS = {
    "Andalucía": {"Extremadura", "Castilla-La Mancha", "Murcia", "Ceuta", "Melilla"},
    "Aragón": {"Cataluña", "Comunidad Valenciana", "Castilla-La Mancha", "Castilla y León", "La Rioja", "Navarra"},
    "Asturias": {"Galicia", "Castilla y León", "Cantabria"},
    "Baleares": {"Cataluña", "Comunidad Valenciana"},
    "Canarias": {"Andalucía"},
    "Cantabria": {"Asturias", "Castilla y León", "País Vasco"},
    "Castilla y León": {"Galicia", "Asturias", "Cantabria", "País Vasco", "La Rioja",
                         "Aragón", "Castilla-La Mancha", "Madrid", "Extremadura"},
    "Castilla-La Mancha": {"Madrid", "Castilla y León", "Aragón",
                           "Comunidad Valenciana", "Murcia", "Andalucía", "Extremadura"},
    "Cataluña": {"Aragón", "Comunidad Valenciana", "Navarra"},
    "Comunidad Valenciana": {"Cataluña", "Aragón", "Castilla-La Mancha", "Murcia", "Baleares"},
    "Extremadura": {"Castilla y León", "Castilla-La Mancha", "Andalucía"},
    "Galicia": {"Asturias", "Castilla y León"},
    "Madrid": {"Castilla y León", "Castilla-La Mancha"},
    "Murcia": {"Comunidad Valenciana", "Castilla-La Mancha", "Andalucía"},
    "Navarra": {"País Vasco", "La Rioja", "Aragón", "Cataluña"},
    "País Vasco": {"Cantabria", "Castilla y León", "La Rioja", "Navarra"},
    "La Rioja": {"País Vasco", "Navarra", "Aragón", "Castilla y León"},
    "Ceuta": {"Andalucía"},
    "Melilla": {"Andalucía"},
}


def leer_R_L(
    fichero_res="plazasCCAA.xlsx",
    fichero_lleg="llegadas.xlsx",
    col_res_ccaa="Comunidad Autónoma",
    col_res_val="Plazas ocupadas",
    col_lleg_ccaa="CCAA",
    col_lleg_val="Llegadas",
    peninsula_va_todo_a_andalucia=True,
):
    """
    Lee los datos de residentes (R) y llegadas (L) desde dos Excels.
    Devuelve dos diccionarios:
        R[i] = residentes en la CCAA i
        L[i] = llegadas en la CCAA i
    en el orden definido por CCAA / IDX.
    """

    df_res = pd.read_excel(fichero_res)
    df_lleg = pd.read_excel(fichero_lleg)

    R = {}
    for c in CCAA:
        fila = df_res[df_res[col_res_ccaa] == c]
        if not fila.empty:
            R[IDX[c]] = float(fila[col_res_val].iloc[0])
        else:
            R[IDX[c]] = 0.0

    L = {i: 0.0 for i in range(len(CCAA))}
    L_zona = {row[col_lleg_ccaa]: float(row[col_lleg_val]) for _, row in df_lleg.iterrows()}

    especiales = {"Baleares", "Canarias", "Ceuta", "Melilla"}

    for nombre in especiales:
        if nombre in L_zona:
            L[IDX[nombre]] = L_zona[nombre]

    if peninsula_va_todo_a_andalucia:
        if "Andalucía" in L_zona:
            L[IDX["Andalucía"]] += L_zona["Andalucía"]
    else:
        # Repartir entre peninsulares
        if "Andalucía" in L_zona:
            lleg_peninsula = L_zona["Andalucía"]
            peninsulares = [i for i, c in enumerate(CCAA) if c not in especiales]
            total_R_pen = sum(R[i] for i in peninsulares)
            for i in peninsulares:
                if total_R_pen > 0:
                    L[i] += lleg_peninsula * (R[i] / total_R_pen)
                else:
                    L[i] += lleg_peninsula / len(peninsulares)

    return R, L


def construir_probabilidades_preferencia(R, L, neighbors=NEIGHBORS, p_stay=0.7):
    """
    A partir de R[i] y L[i], construye:
        - N_ij: número entero de menores de i que prefieren j
        - P_ij: probabilidad p_ij = N_ij / N_i

    Parámetros:
        R, L: diccionarios {i: valor}
        neighbors: diccionario de vecindades {nombre_CCAA: set(nombres_vecinos)}
        p_stay: probabilidad (0-1) de querer quedarse en su propia comunidad.

    Devuelve:
        N_ij (np.array n x n, int), P (np.array n x n, float)
    """

    n = len(CCAA)
    N_ij = np.zeros((n, n), dtype=int)

    N_tot = {i: float(R[i] + L[i]) for i in range(n)}

    for i, origen in enumerate(CCAA):
        Ni = int(round(N_tot[i]))
        if Ni <= 0:
            continue

        # menores que quieren quedarse en su propia comunidad (entero)
        stay = int(round(p_stay * Ni))
        if stay > Ni:
            stay = Ni
        if stay < 0:
            stay = 0
        N_ij[i, i] = stay

        remaining = Ni - stay
        if remaining <= 0:
            continue

        # repartir el resto entre las otras CCAA según cercanía
        pesos = []
        destinos = []
        orig_neighbors = neighbors.get(origen, set())

        for j, destino in enumerate(CCAA):
            if j == i:
                continue
            w = 2.0 if destino in orig_neighbors else 1.0
            pesos.append(w)
            destinos.append(j)

        pesos = np.array(pesos, dtype=float)
        suma_pesos = pesos.sum()

        if suma_pesos <= 0:
            ideales = np.full_like(pesos, remaining / len(pesos), dtype=float)
        else:
            ideales = remaining * pesos / suma_pesos

        # asignación entera: método de restos mayores
        base = np.floor(ideales).astype(int)
        asignados = base.sum()
        resto = remaining - asignados

        fracs = ideales - base
        order = np.argsort(-fracs)  # índices ordenados por fracción descendente
        for idx_extra in order[:resto]:
            base[idx_extra] += 1

        for dest_idx, j in enumerate(destinos):
            N_ij[i, j] = base[dest_idx]

    # construir matriz de probabilidades P[i,j] = N_ij / N_i
    P = np.zeros((n, n), dtype=float)
    for i in range(n):
        Ni = N_tot[i]
        if Ni > 0:
            P[i, :] = N_ij[i, :] / Ni

    return N_ij, P


if __name__ == "__main__":
    R, L = leer_R_L(
        fichero_res="plazasCCAA.xlsx",
        fichero_lleg="llegadas.xlsx",
        peninsula_va_todo_a_andalucia=True,
    )

    N_ij, P = construir_probabilidades_preferencia(R, L, neighbors=NEIGHBORS, p_stay=0.7)

    df_P = pd.DataFrame(P, index=CCAA, columns=CCAA)
    df_P.to_excel("probabilidades_preferencia_generadas.xlsx")

    df_N = pd.DataFrame(N_ij, index=CCAA, columns=CCAA)
    df_N.to_excel("N_ij_enteros_generados.xlsx")

    print("He generado:")
    print(" - probabilidades_preferencia_generadas.xlsx")
    print(" - N_ij_enteros_generados.xlsx")
