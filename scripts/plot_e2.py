#!/usr/bin/env python3
"""
plot_e2.py — Gráficas de E2 a partir de results/e2/summary.csv.

Uso (desde la raíz del repositorio, después de parse_e2.py):
    python3 scripts/plot_e2.py

Genera:
    results/e2/e2_ipc.png      IPC según el ancho, una línea por tamaño de ROB,
                               un panel por N (mismo eje Y para comparar).
    results/e2/e2_stalls.png   % de ciclos en que la etapa rename se bloqueó por
                               ROB, IQ, LQ o SQ llenos, para las 12 configuraciones
                               de cada N.

Se leen juntas: la primera muestra DÓNDE se satura el IPC; la segunda, POR QUÉ
(qué recurso está lleno mientras el IPC deja de subir).

Requiere matplotlib (apt install python3-matplotlib).
"""

import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")  # sin pantalla: sirve en Docker, WSL y por SSH
import matplotlib.pyplot as plt

SIZES = [64, 128]
WIDTHS = [1, 2, 4, 8]
ROBS = [32, 64, 192]

# Mismas tintas que plot_e1.py.
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"

# ROB es una magnitud ordenada (32 < 64 < 192): un solo tono, de claro a oscuro.
# Rampa azul validada como ordinal (validate_palette.js --ordinal).
ROB_COLORS = {32: "#6da7ec", 64: "#2a78d6", 192: "#104281"}

# Causas de bloqueo: identidad, no magnitud → paleta categórica en orden fijo.
CAUSES = [
    ("lq_full_frac", "LQ llena", "#2a78d6"),
    ("rob_full_frac", "ROB lleno", "#eb6834"),
    ("iq_full_frac", "IQ llena", "#1baf7a"),
    ("sq_full_frac", "SQ llena", "#eda100"),
]


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 24:
        sys.exit(f"ERROR: {path} tiene {len(rows)} filas, se esperaban 24")
    return {(int(r["N"]), int(r["width"]), int(r["rob"])): r for r in rows}


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(TEXT_2)
    ax.tick_params(axis="y", colors=TEXT_2, labelsize=9, length=0)
    ax.tick_params(axis="x", colors=TEXT, labelsize=9, length=0)


def plot_ipc(data, out):
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.2), dpi=200, sharey=True)
    fig.patch.set_facecolor(SURFACE)
    x = list(range(len(WIDTHS)))  # anchos equiespaciados: 1, 2, 4, 8
    ends = {}  # (panel, rob) -> IPC final, para las etiquetas directas
    for ax, n in zip(axes, SIZES):
        style(ax)
        for rob in ROBS:
            y = [float(data[(n, w, rob)]["ipc"]) for w in WIDTHS]
            ax.plot(x, y, color=ROB_COLORS[rob], linewidth=2, marker="o", markersize=6,
                    markeredgecolor=SURFACE, markeredgewidth=1.5,
                    label=f"ROB {rob}", zorder=3)
            ends[(n, rob)] = y[-1]
        ax.set_xticks(x)
        ax.set_xticklabels([str(w) for w in WIDTHS])
        ax.set_xlim(-0.25, len(WIDTHS) - 0.25 + 0.6)  # espacio para las etiquetas
        ax.set_xlabel("Ancho del pipeline (instrucciones/ciclo en cada etapa)",
                      color=TEXT_2, fontsize=9.5)
        ax.set_title(f"N = {n}", color=TEXT, fontsize=11, loc="left")
    axes[0].set_ylabel("IPC en la ROI", color=TEXT_2, fontsize=10)
    axes[0].set_ylim(0, axes[0].get_ylim()[1] * 1.08)

    # Etiquetas directas al final de cada línea (además de la leyenda). Si dos
    # líneas terminan casi en el mismo IPC, se separan verticalmente para que no
    # se encimen; un trazo fino une la etiqueta desplazada con su punto.
    ymin, ymax = axes[0].get_ylim()
    gap = 0.05 * (ymax - ymin)  # separación mínima entre etiquetas
    for ax, n in zip(axes, SIZES):
        order = sorted(ROBS, key=lambda r: ends[(n, r)])
        placed = []
        for rob in order:
            y_label = ends[(n, rob)]
            if placed and y_label < placed[-1] + gap:
                y_label = placed[-1] + gap
            placed.append(y_label)
            ax.annotate(f"ROB {rob}", xy=(x[-1], ends[(n, rob)]),
                        xytext=(x[-1] + 0.18, y_label), textcoords="data",
                        va="center", fontsize=8.5, color=TEXT_2,
                        arrowprops=dict(arrowstyle="-", color=GRID, linewidth=0.8,
                                        shrinkA=0, shrinkB=4))
    axes[1].legend(frameon=False, fontsize=9, labelcolor=TEXT, loc="upper left")
    fig.suptitle("E2 · IPC según ancho y tamaño del ROB (O3, GEMM escalar, 2 GHz)",
                 color=TEXT, fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    print(f"Escrito: {out}")


def plot_stalls(data, out):
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6), dpi=200, sharey=True)
    fig.patch.set_facecolor(SURFACE)
    configs = [(w, r) for w in WIDTHS for r in ROBS]
    # Separación extra entre grupos de ancho para leerlos como bloques.
    pos = [i + 0.5 * (i // len(ROBS)) for i in range(len(configs))]
    for ax, n in zip(axes, SIZES):
        style(ax)
        bottom = [0.0] * len(configs)
        for key, label, color in CAUSES:
            vals = [100 * float(data[(n, w, r)][key]) for (w, r) in configs]
            # Las fracciones se pueden apilar: rename registra UNA causa por ciclo.
            ax.bar(pos, vals, bottom=bottom, width=0.8, color=color, label=label,
                   edgecolor=SURFACE, linewidth=1, zorder=3)
            bottom = [b + v for b, v in zip(bottom, vals)]
        ax.set_xticks(pos)
        ax.set_xticklabels([str(r) for (_, r) in configs], fontsize=8)
        # Rótulo de cada grupo de ancho debajo de los tamaños de ROB.
        for k, w in enumerate(WIDTHS):
            center = sum(pos[k * len(ROBS):(k + 1) * len(ROBS)]) / len(ROBS)
            ax.annotate(f"ancho {w}", (center, 0), xytext=(0, -26),
                        textcoords="offset points", xycoords=("data", "axes fraction"),
                        ha="center", fontsize=9, color=TEXT)
        ax.set_xlabel("Entradas del ROB, agrupadas por ancho", color=TEXT_2,
                      fontsize=9.5, labelpad=22)
        ax.set_title(f"N = {n}", color=TEXT, fontsize=11, loc="left")
    axes[0].set_ylabel("% de ciclos con rename bloqueado", color=TEXT_2, fontsize=10)
    axes[0].set_ylim(0, 100)
    # Leyenda a nivel de figura, en la fila del título, para no tapar "N = 128".
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=9, labelcolor=TEXT, ncol=4,
               loc="upper right", bbox_to_anchor=(0.995, 0.985))
    fig.suptitle("E2 · Qué recurso detiene al núcleo (bloqueos de la etapa rename)",
                 color=TEXT, fontsize=12, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    print(f"Escrito: {out}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.join(os.path.dirname(here), "results", "e2")
    ap = argparse.ArgumentParser(description="Gráficas de E2")
    ap.add_argument("--results", default=default, help="carpeta con summary.csv")
    args = ap.parse_args()

    data = load(os.path.join(args.results, "summary.csv"))
    plot_ipc(data, os.path.join(args.results, "e2_ipc.png"))
    plot_stalls(data, os.path.join(args.results, "e2_stalls.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
