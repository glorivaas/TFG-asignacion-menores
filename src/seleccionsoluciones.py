# -*- coding: utf-8 -*-
"""
Created on Wed Feb  4 13:52:22 2026

@author: glori
"""

import pandas as pd
import numpy as np

def normalizar_minmax(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    xmin = np.nanmin(x)
    xmax = np.nanmax(x)
    denom = max(xmax - xmin, eps)
    return (x - xmin) / denom

def espacio_objetivo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye un espacio de objetivos normalizado en modo minimización:
      v1 = f1_n (min)
      v2 = f2_n (min)
      v3 = (f3_max - f3) / (f3_max - f3_min)  (min)  => maximizar f3 equivale a minimizar v3
    """
    f1 = df["f1"].to_numpy(dtype=float)
    f2 = df["f2"].to_numpy(dtype=float)
    f3 = df["f3"].to_numpy(dtype=float)

    v1 = normalizar_minmax(f1)
    v2 = normalizar_minmax(f2)

    f3_min = np.nanmin(f3)
    f3_max = np.nanmax(f3)
    denom = max(f3_max - f3_min, 1e-12)
    v3 = (f3_max - f3) / denom 

    out = df.copy()
    out["_v1"] = v1
    out["_v2"] = v2
    out["_v3"] = v3
    return out

def compromiso_punt(dfv: pd.DataFrame, p: str = "2", weights=(1.0, 1.0, 1.0)) -> np.ndarray:
    """
    Distancia al punto ideal (0,0,0) en el espacio normalizado de minimización.
    p = métrica utilizada: "1", "2", "inf"
    weights: pesos para cada objetivo en la distancia (opcional).
    """
    w1, w2, w3 = weights
    a = dfv[["_v1", "_v2", "_v3"]].to_numpy()
    a = a * np.array([w1, w2, w3], dtype=float)

    if p == "1":
        return np.sum(np.abs(a), axis=1)
    if p == "2":
        return np.sqrt(np.sum(a**2, axis=1))
    if p == "inf":
        return np.max(np.abs(a), axis=1)
    raise ValueError("p must be '1', '2' or 'inf'")

def farthest_sampling(dfv: pd.DataFrame, chosen_idx: list[int], k: int) -> list[int]:
    """
    Completa la selección con puntos "diversos" en el espacio [_v1,_v2,_v3]
    usando un greedy maximin (farthest point sampling).
    """
    V = dfv[["_v1", "_v2", "_v3"]].to_numpy()
    n = V.shape[0]

    elegido = chosen_idx[:]
    remaining = [i for i in range(n) if i not in set(elegido)]

    if len(elegido) == 0:
        elegido.append(remaining.pop(0))

    while len(elegido) < k and remaining:
        C = V[elegido]
        R = V[remaining]
        dmins = []
        for r in R:
            dmins.append(np.min(np.linalg.norm(C - r, axis=1)))
        dmins = np.array(dmins)

        best_pos = int(np.argmax(dmins))
        best_idx = remaining[best_pos]
        elegido.append(best_idx)
        remaining.pop(best_pos)

    return elegido


def soluciones_representativas(
    csv_path: str,
    out_csv_path: str = "representativas_10.csv",
    n_rep: int = 10,
    weights_cp=(1.0, 1.0, 1.0),
) -> pd.DataFrame:
    """
    Selecciona n_rep soluciones representativas desde un CSV con columnas f1,f2,f3.

    1) Extremos: min f1, min f2, max f3.
    2) Compromise Programming: mejores por L1, L2, Linf del conjunto eficiente aproximado.
    3) Completa con diversidad (farthest-point sampling) hasta n_rep.

    Devuelve DataFrame con columna 'tag' indicando criterio.
    """
    df = pd.read_csv(csv_path)

    required = {"f1", "f2", "f3"}
    if not required.issubset(df.columns):
        raise ValueError(f"El CSV debe contener columnas {required}. Columnas encontradas: {list(df.columns)}")

    df = df.copy().reset_index(drop=True)
    dfv = espacio_objetivo(df)

    elegidos: dict[int, str] = {}

    # extremos
    i_min_f1 = int(df["f1"].astype(float).idxmin())
    elegidos[i_min_f1] = "extremo: min f1 (máxima equidad)"

    i_min_f2 = int(df["f2"].astype(float).idxmin())
    elegidos[i_min_f2] = "extremo: min f2 (mínimo coste)"

    i_max_f3 = int(df["f3"].astype(float).idxmax())
    elegidos[i_max_f3] = "extremo: max f3 (máximo bienestar)"

    # compromise aproximados
    for p, label in [("1", "compromise: L1"), ("2", "compromise: L2"), ("inf", "compromise: Linf")]:
        punt = compromiso_punt(dfv, p=p, weights=weights_cp)
        imejor = int(np.argmin(punt))
        if imejor in elegidos:
            order_idx = np.argsort(punt)
            for idx in order_idx:
                idx = int(idx)
                if idx not in elegidos:
                    imejor = idx
                    break
        elegidos[imejor] = label


    # completar con diversidad
    elegidos_idx = list(elegidos.keys())
    if len(elegidos_idx) < n_rep:
        final_idx = farthest_sampling(dfv, elegidos_idx, k=n_rep)
        for idx in final_idx:
            if idx not in elegidos:
                elegidos[idx] = "diversidad: farthest-point"

    idxs = list(elegidos.keys())
    df_sel = df.loc[idxs].copy()
    df_sel["tag"] = [elegidos[i] for i in idxs]


    def tag_orden(s: str) -> int:
        if s.startswith("extremo"):
            return 0
        if s.startswith("compromise"):
            return 1
        return 4

    df_sel.insert(0, "_order", df_sel["tag"].map(tag_orden))
    df_sel = df_sel.sort_values(["_order", "f2", "f1", "f3"], ascending=[True, True, True, False]).drop(columns="_order")
    df_sel = df_sel.reset_index(drop=True)

    df_sel.to_csv(out_csv_path, index=False)


    print(f"Guardado: {out_csv_path}  (n={len(df_sel)})")

    return df_sel


df10 = soluciones_representativas(
    "pareto_global_summary.csv",
    out_csv_path="representativas_10_2.csv",
    n_rep=10,
    weights_cp=(1.0, 1.0, 1.0),
)

print(df10[["f1","f2","f3","tag"]])