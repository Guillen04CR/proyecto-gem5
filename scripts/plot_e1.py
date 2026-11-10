#!/usr/bin/env python3
"""
plot_e1.py — Gráficas de E1 a partir de results/e1/summary.csv.

Uso (desde la raíz del repositorio, después de parse_e1.py):
    python3 scripts/plot_e1.py

Genera:
    results/e1/e1_ipc.png            IPC por modelo de CPU, N=64 vs N=128
    results/e1/e1_l1d_miss_rate.png  Tasa de fallos de L1D, N=64 vs N=128

Las dos se leen juntas: la caída de IPC con N=128 coincide con el salto en la tasa
de fallos de L1D (la columna de B deja de caber en la L1D de 32 kB, 2 vías).

Requiere matplotlib (apt install python3-matplotlib).
"""

import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")  # sin pantalla: sirve en Docker, WSL y por SSH
import matplotlib.pyplot as plt

CPUS = ["timing", "minor", "o3"]
CPU_LABELS = {"timing": "TimingSimple", "minor": "Minor (en orden)", "o3": "O3 (fuera de orden)"}
SIZES = [64, 128]

# Paleta categórica validada (azul, naranja) y tintas neutras.
SERIES = {64: "#2a78d6", 128: "#eb6834"}
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 6:
        sys.exit(f"ERROR: {path} tiene {len(rows)} filas, se esperaban 6")
    return {(r["cpu"], int(r["N"])): r for r in rows}


def grouped_bars(data, field, scale, fmt, title, ylabel, out):
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    width = 0.34
    gap = 0.02  # separación entre barras vecinas
    x = range(len(CPUS))
    for k, n in enumerate(SIZES):
        offset = (k - 0.5) * (width + gap)
        values = [float(data[(cpu, n)][field]) * scale for cpu in CPUS]
        bars = ax.bar([i + offset for i in x], values, width=width,
                      color=SERIES[n], label=f"N = {n}", zorder=3)
        for b, v in zip(bars, values):
            ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, b.get_height()),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8.5, color=TEXT_2)

    ax.set_xticks(list(x))
    ax.set_xticklabels([CPU_LABELS[c] for c in CPUS], color=TEXT, fontsize=10)
    ax.set_ylabel(ylabel, color=TEXT_2, fontsize=10)
    ax.set_title(title, color=TEXT, fontsize=12, loc="left", pad=26)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.12)  # espacio para las etiquetas
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(TEXT_2)
    ax.tick_params(axis="y", colors=TEXT_2, labelsize=9, length=0)
    ax.tick_params(axis="x", length=0)
    ax.legend(frameon=False, fontsize=9.5, labelcolor=TEXT, ncol=2,
              loc="lower right", bbox_to_anchor=(1.0, 1.0), borderaxespad=0.2)

    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    print(f"Escrito: {out}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.join(os.path.dirname(here), "results", "e1")
    ap = argparse.ArgumentParser(description="Gráficas de E1")
    ap.add_argument("--results", default=default, help="carpeta con summary.csv")
    args = ap.parse_args()

    data = load(os.path.join(args.results, "summary.csv"))

    grouped_bars(data, "ipc", 1.0, "{:.2f}",
                 "E1 · IPC en la ROI (GEMM escalar, 1 núcleo, 2 GHz)",
                 "IPC (instrucciones por ciclo)",
                 os.path.join(args.results, "e1_ipc.png"))
    grouped_bars(data, "l1d_miss_rate", 100.0, "{:.1f} %",
                 "E1 · Tasa de fallos de L1D en la ROI (32 kB, 2 vías)",
                 "Fallos L1D / accesos L1D (%)",
                 os.path.join(args.results, "e1_l1d_miss_rate.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
