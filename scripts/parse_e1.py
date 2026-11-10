#!/usr/bin/env python3
"""
parse_e1.py — Convierte las seis corridas de E1 en results/e1/summary.csv.

Uso (desde la raíz del repositorio):
    python3 scripts/parse_e1.py                 # lee results/e1, escribe results/e1/summary.csv
    python3 scripts/parse_e1.py --results DIR   # otra carpeta de resultados

Qué hace:
  1. Para cada combinación CPU × N lee results/e1/<cpu>_N<n>/stats.txt.
  2. Toma EXPLÍCITAMENTE el bloque 1 (el que escribe m5_dump_stats al cerrar la ROI).
     El bloque 2 lo escribe m5.stats.dump() al final de run_e1.py y es acumulado:
     ROI + check() + printf + salida. Nunca se usa.
  3. Exige que el archivo tenga exactamente 2 bloques; si no, la corrida no sigue
     el flujo acordado y el script se detiene.
  4. Extrae ciclos, instrucciones, IPC, CPI, fallos L1D y fallos L2, y escribe un
     CSV de exactamente seis filas.

Solo usa la biblioteca estándar de Python.
"""

import argparse
import csv
import os
import re
import sys

CPUS = ["timing", "minor", "o3"]
SIZES = [64, 128]

BEGIN = "---------- Begin Simulation Statistics ----------"
END = "---------- End Simulation Statistics   ----------"
EXPECTED_BLOCKS = 2
ROI_BLOCK = 1  # 1 = primer bloque

# Estadísticas que se leen del bloque ROI. Nombres de gem5 v26 con cachés clásicas
# (las define configs/run_e1.py: system.cpu.dcache y system.l2cache).
STATS = {
    "sim_ticks": "simTicks",
    "cycles": "system.cpu.numCycles",
    # Instrucciones confirmadas, CONTANDO los NOP. Ver nota sobre O3 abajo.
    "insts": "system.cpu.commitStats0.numInsts",
    "insts_not_nop": "system.cpu.commitStats0.numInstsNotNOP",
    "sim_insts": "simInsts",
    "ipc_gem5": "system.cpu.ipc",
    "cpi_gem5": "system.cpu.cpi",
    "l1d_accesses": "system.cpu.dcache.demandAccesses::total",
    "l1d_misses": "system.cpu.dcache.demandMisses::total",
    "l2_accesses": "system.l2cache.demandAccesses::total",
    "l2_misses": "system.l2cache.demandMisses::total",
}
# Nota sobre instrucciones: GCC deja un NOP de alineación que se ejecuta una vez por
# cada (i, j), o sea n² veces. TimingSimple y Minor cuentan los NOP en simInsts; O3
# no. Por eso simInsts de O3 es exactamente n² menor. commitStats0.numInsts sí es
# igual en los tres modelos y coincide con el modelo 6n³ + 9n² + 8n + 20, así que es
# el contador que se usa para comparar CPU entre sí. gem5 también calcula su ipc
# con ese contador.

FIELDS = [
    "cpu", "N",
    "cycles", "insts", "ipc", "cpi",
    "l1d_misses", "l1d_accesses", "l1d_miss_rate", "l1d_mpki",
    "l2_misses", "l2_accesses", "l2_miss_rate", "l2_mpki",
    "roi_time_ms", "speedup_vs_timing",
    "sim_ticks", "sim_insts", "insts_not_nop", "insts_model", "insts_match_model",
]

STAT_LINE = re.compile(r"^(\S+)\s+(\S+)")


class ParseError(Exception):
    pass


def insts_model(n):
    """Instrucciones esperadas en la ROI (docs/gemm_scalar.md, GCC 13.3 -O2)."""
    return 6 * n**3 + 9 * n**2 + 8 * n + 20


def read_blocks(path):
    """Devuelve la lista de bloques; cada bloque es un dict nombre -> texto del valor."""
    blocks = []
    current = None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.startswith(BEGIN):
                if current is not None:
                    raise ParseError(f"{path}: bloque sin 'End' antes de un nuevo 'Begin'")
                current = {}
            elif line.startswith(END):
                if current is None:
                    raise ParseError(f"{path}: 'End' sin 'Begin'")
                blocks.append(current)
                current = None
            elif current is not None:
                m = STAT_LINE.match(line)
                if m:
                    current[m.group(1)] = m.group(2)
    if current is not None:
        raise ParseError(f"{path}: el último bloque no tiene 'End' (¿corrida cortada?)")
    return blocks


def number(block, name, path):
    if name not in block:
        raise ParseError(f"{path}: falta la estadística '{name}' en el bloque ROI")
    text = block[name]
    try:
        value = float(text)
    except ValueError:
        raise ParseError(f"{path}: '{name}' no es numérico: {text!r}")
    if value != value:  # NaN
        raise ParseError(f"{path}: '{name}' es NaN")
    return value


def parse_run(results_dir, cpu, n):
    path = os.path.join(results_dir, f"{cpu}_N{n}", "stats.txt")
    if not os.path.isfile(path):
        raise ParseError(f"no existe {path}")

    blocks = read_blocks(path)
    if len(blocks) != EXPECTED_BLOCKS:
        raise ParseError(
            f"{path}: tiene {len(blocks)} bloques y se esperaban {EXPECTED_BLOCKS} "
            "(1 = ROI con m5_dump_stats, 2 = dump final)")
    roi = blocks[ROI_BLOCK - 1]

    v = {key: number(roi, name, path) for key, name in STATS.items()}

    cycles = v["cycles"]
    insts = v["insts"]
    if cycles <= 0 or insts <= 0:
        raise ParseError(f"{path}: ciclos o instrucciones en cero")

    ipc = insts / cycles
    # gem5 calcula su propio ipc; si no coincide, se está leyendo un contador distinto.
    if abs(ipc - v["ipc_gem5"]) > 1e-4 * max(1.0, ipc):
        raise ParseError(f"{path}: IPC calculado {ipc:.6f} != ipc de gem5 {v['ipc_gem5']:.6f}")

    kinsts = insts / 1000.0
    model = insts_model(n)
    return {
        "cpu": cpu,
        "N": n,
        "cycles": int(cycles),
        "insts": int(insts),
        "ipc": round(ipc, 6),
        "cpi": round(cycles / insts, 6),
        "l1d_misses": int(v["l1d_misses"]),
        "l1d_accesses": int(v["l1d_accesses"]),
        "l1d_miss_rate": round(v["l1d_misses"] / v["l1d_accesses"], 6),
        "l1d_mpki": round(v["l1d_misses"] / kinsts, 3),
        "l2_misses": int(v["l2_misses"]),
        "l2_accesses": int(v["l2_accesses"]),
        "l2_miss_rate": round(v["l2_misses"] / v["l2_accesses"], 6) if v["l2_accesses"] else 0.0,
        "l2_mpki": round(v["l2_misses"] / kinsts, 3),
        "roi_time_ms": round(v["sim_ticks"] / 1e9, 6),  # 1 tick = 1 ps
        "speedup_vs_timing": None,  # se llena después
        "sim_ticks": int(v["sim_ticks"]),
        "sim_insts": int(v["sim_insts"]),
        "insts_not_nop": int(v["insts_not_nop"]),
        "insts_model": model,
        "insts_match_model": "yes" if int(insts) == model else "no",
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", default=os.path.join(repo, "results", "e1"),
                    help="carpeta con las seis corridas (por defecto results/e1)")
    ap.add_argument("--out", default=None, help="CSV de salida (por defecto <results>/summary.csv)")
    args = ap.parse_args()
    out = args.out or os.path.join(args.results, "summary.csv")

    rows = []
    try:
        for cpu in CPUS:
            for n in SIZES:
                rows.append(parse_run(args.results, cpu, n))
    except ParseError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Speedup de cada CPU respecto a TimingSimple con el mismo N (mismo trabajo).
    base = {r["N"]: r["sim_ticks"] for r in rows if r["cpu"] == "timing"}
    for r in rows:
        r["speedup_vs_timing"] = round(base[r["N"]] / r["sim_ticks"], 4)

    assert len(rows) == len(CPUS) * len(SIZES) == 6

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # Resumen legible en la terminal.
    print(f"{'cpu':<7}{'N':>5}{'ciclos':>12}{'insts':>12}{'IPC':>7}{'CPI':>7}"
          f"{'L1D miss':>10}{'L1D %':>8}{'L2 miss':>9}{'t (ms)':>9}{'speedup':>9}")
    for r in rows:
        print(f"{r['cpu']:<7}{r['N']:>5}{r['cycles']:>12}{r['insts']:>12}"
              f"{r['ipc']:>7.3f}{r['cpi']:>7.3f}{r['l1d_misses']:>10}"
              f"{100 * r['l1d_miss_rate']:>7.2f}%{r['l2_misses']:>9}"
              f"{r['roi_time_ms']:>9.3f}{r['speedup_vs_timing']:>8.2f}x")
    bad = [f"{r['cpu']}_N{r['N']}" for r in rows if r["insts_match_model"] != "yes"]
    if bad:
        print(f"AVISO: instrucciones distintas del modelo 6n³+9n²+8n+20 en: {', '.join(bad)}",
              file=sys.stderr)
    print(f"\nEscrito: {out} ({len(rows)} filas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
