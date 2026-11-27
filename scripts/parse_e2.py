#!/usr/bin/env python3
"""
parse_e2.py — Convierte las 24 corridas de E2 en results/e2/summary.csv.

Uso (desde la raíz del repositorio):
    python3 scripts/parse_e2.py                 # lee results/e2, escribe results/e2/summary.csv
    python3 scripts/parse_e2.py --results DIR   # otra carpeta de resultados

Qué hace:
  1. Para cada combinación N × ancho × ROB lee results/e2/w<W>_rob<R>_N<N>/stats.txt.
  2. Toma el bloque 1 (la ROI), con las mismas funciones y comprobaciones que
     parse_e1.py: exactamente 2 bloques, IPC propio igual al de gem5 e
     instrucciones iguales al modelo 6n³ + 9n² + 8n + 20.
  3. Exige "E1_VALIDATION: PASS" en el run.log de cada corrida.
  4. Además de IPC y fallos de caché, extrae los contadores que dicen POR QUÉ el
     núcleo se detiene (ROB, IQ, LQ y SQ llenos, saltos mal predichos).
  5. Compara la corrida ancho 8 / ROB 192 con la de O3 en E1 (results/e1/summary.csv):
     son la misma configuración, así que los ciclos deben ser idénticos.

Solo usa la biblioteca estándar de Python.
"""

import argparse
import csv
import os
import sys

# Reutiliza el lector de bloques de E1, para que E1 y E2 lean stats.txt igual.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_e1 import (  # noqa: E402
    EXPECTED_BLOCKS, ROI_BLOCK, ParseError, insts_model, number, read_blocks,
)

SIZES = [64, 128]
WIDTHS = [1, 2, 4, 8]
ROBS = [32, 64, 192]
BASE = (1, 32)        # (ancho, ROB) contra el que se calcula el speedup
E1_POINT = (8, 192)   # valores por defecto de O3 = corrida O3 de E1

# Estadísticas que SIEMPRE aparecen en el bloque ROI.
STATS = {
    "sim_ticks": "simTicks",
    "cycles": "system.cpu.numCycles",
    "insts": "system.cpu.commitStats0.numInsts",   # mismo contador que E1
    "ipc_gem5": "system.cpu.ipc",
    "l1d_accesses": "system.cpu.dcache.demandAccesses::total",
    "l1d_misses": "system.cpu.dcache.demandMisses::total",
    # Instrucciones emitidas a ejecución por ciclo (promedio).
    "issued_mean": "system.cpu.numIssuedDist::mean",
    # Saltos condicionales mal predichos.
    "mispredicts": "system.cpu.branchPred.condIncorrect",
    # Ciclos promedio desde que se emite una carga hasta que su dato está listo.
    "load_to_use": "system.cpu.lsq0.loadToUse::mean",
}

# Contadores de bloqueo de la etapa rename. gem5 los suma una vez por ciclo en que
# rename no puede avanzar por falta de ese recurso, así que dividirlos entre los
# ciclos da la FRACCIÓN de ciclos bloqueados por cada causa. gem5 NO los imprime
# cuando valen 0 (prereq), por eso aquí faltar significa 0.
FULL_STATS = {
    "rob_full": "system.cpu.rename.ROBFullEvents",
    "iq_full": "system.cpu.rename.IQFullEvents",
    "lq_full": "system.cpu.rename.LQFullEvents",
    "sq_full": "system.cpu.rename.SQFullEvents",
    "regs_full": "system.cpu.rename.fullRegistersEvents",
}

FIELDS = [
    "N", "width", "rob",
    "cycles", "insts", "ipc", "cpi", "speedup_vs_w1_rob32",
    "issued_per_cycle",
    "rob_full_frac", "iq_full_frac", "lq_full_frac", "sq_full_frac", "regs_full_frac",
    "l1d_miss_rate", "load_to_use_cycles",
    "mispredicts", "mispredicts_pki",
    "sim_ticks", "insts_match_model", "same_as_e1_o3",
]


def parse_run(results_dir, width, rob, n):
    run_dir = os.path.join(results_dir, f"w{width}_rob{rob}_N{n}")
    path = os.path.join(run_dir, "stats.txt")
    log = os.path.join(run_dir, "run.log")
    if not os.path.isfile(path):
        raise ParseError(f"no existe {path}")
    if not os.path.isfile(log):
        raise ParseError(f"no existe {log}")
    with open(log, encoding="utf-8", errors="replace") as f:
        if "E1_VALIDATION: PASS" not in f.read():
            raise ParseError(f"{log}: no contiene 'E1_VALIDATION: PASS'")

    blocks = read_blocks(path)
    if len(blocks) != EXPECTED_BLOCKS:
        raise ParseError(f"{path}: tiene {len(blocks)} bloques y se esperaban {EXPECTED_BLOCKS}")
    roi = blocks[ROI_BLOCK - 1]

    v = {key: number(roi, name, path) for key, name in STATS.items()}
    full = {key: (number(roi, name, path) if name in roi else 0.0)
            for key, name in FULL_STATS.items()}

    cycles, insts = v["cycles"], v["insts"]
    if cycles <= 0 or insts <= 0:
        raise ParseError(f"{path}: ciclos o instrucciones en cero")
    ipc = insts / cycles
    if abs(ipc - v["ipc_gem5"]) > 1e-4 * max(1.0, ipc):
        raise ParseError(f"{path}: IPC calculado {ipc:.6f} != ipc de gem5 {v['ipc_gem5']:.6f}")

    row = {
        "N": n, "width": width, "rob": rob,
        "cycles": int(cycles),
        "insts": int(insts),
        "ipc": round(ipc, 6),
        "cpi": round(cycles / insts, 6),
        "speedup_vs_w1_rob32": None,  # se llena después
        "issued_per_cycle": round(v["issued_mean"], 6),
        "l1d_miss_rate": round(v["l1d_misses"] / v["l1d_accesses"], 6),
        "load_to_use_cycles": round(v["load_to_use"], 3),
        "mispredicts": int(v["mispredicts"]),
        "mispredicts_pki": round(v["mispredicts"] / (insts / 1000.0), 3),
        "sim_ticks": int(v["sim_ticks"]),
        "insts_match_model": "yes" if int(insts) == insts_model(n) else "no",
        "same_as_e1_o3": "",          # se llena después, solo en (8, 192)
    }
    for key, value in full.items():
        row[f"{key}_frac"] = round(value / cycles, 6)
    return row


def load_e1_o3(path):
    """Ciclos de O3 en E1 por N, o {} si no existe el CSV de E1."""
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {int(r["N"]): int(r["cycles"]) for r in csv.DictReader(f) if r["cpu"] == "o3"}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", default=os.path.join(repo, "results", "e2"),
                    help="carpeta con las 24 corridas (por defecto results/e2)")
    ap.add_argument("--e1", default=os.path.join(repo, "results", "e1", "summary.csv"),
                    help="summary.csv de E1 para la comprobación (8, 192)")
    ap.add_argument("--out", default=None, help="CSV de salida (por defecto <results>/summary.csv)")
    args = ap.parse_args()
    out = args.out or os.path.join(args.results, "summary.csv")

    rows = []
    try:
        for n in SIZES:
            for w in WIDTHS:
                for r in ROBS:
                    rows.append(parse_run(args.results, w, r, n))
    except ParseError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    assert len(rows) == len(SIZES) * len(WIDTHS) * len(ROBS) == 24

    # Speedup respecto al núcleo más chico (ancho 1, ROB 32) con el mismo N.
    base = {r["N"]: r["cycles"] for r in rows if (r["width"], r["rob"]) == BASE}
    for r in rows:
        r["speedup_vs_w1_rob32"] = round(base[r["N"]] / r["cycles"], 4)

    # Control de calidad contra E1.
    e1 = load_e1_o3(args.e1)
    problems = []
    for r in rows:
        if (r["width"], r["rob"]) == E1_POINT:
            if r["N"] not in e1:
                r["same_as_e1_o3"] = "sin_e1"
            elif r["cycles"] == e1[r["N"]]:
                r["same_as_e1_o3"] = "yes"
            else:
                r["same_as_e1_o3"] = "no"
                problems.append(f"w8_rob192_N{r['N']}: {r['cycles']} ciclos, E1 O3 tiene {e1[r['N']]}")
        if r["insts_match_model"] != "yes":
            problems.append(f"w{r['width']}_rob{r['rob']}_N{r['N']}: instrucciones distintas del modelo")

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # Resumen legible: % de ciclos en que rename se bloqueó por cada recurso.
    print(f"{'N':>4}{'ancho':>6}{'ROB':>5}{'ciclos':>11}{'IPC':>7}{'speedup':>9}"
          f"{'ROB%':>7}{'IQ%':>7}{'LQ%':>7}{'SQ%':>6}{'L1D%':>7}{'fallosBP':>10}")
    for r in rows:
        print(f"{r['N']:>4}{r['width']:>6}{r['rob']:>5}{r['cycles']:>11}{r['ipc']:>7.3f}"
              f"{r['speedup_vs_w1_rob32']:>8.2f}x"
              f"{100 * r['rob_full_frac']:>7.1f}{100 * r['iq_full_frac']:>7.1f}"
              f"{100 * r['lq_full_frac']:>7.1f}{100 * r['sq_full_frac']:>6.1f}"
              f"{100 * r['l1d_miss_rate']:>7.1f}{r['mispredicts']:>10}")

    for r in rows:
        if (r["width"], r["rob"]) == E1_POINT:
            print(f"Control E1 (ancho 8, ROB 192, N={r['N']}): {r['same_as_e1_o3']}")
    if problems:
        print("AVISO:\n  " + "\n  ".join(problems), file=sys.stderr)
    print(f"\nEscrito: {out} ({len(rows)} filas)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
