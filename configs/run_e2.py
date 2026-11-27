"""
run_e2.py — Sistema de gem5 para E2 (arquitectura superescalar).

Es una copia de configs/run_e1.py con UNA sola diferencia: el núcleo es siempre
O3 y se le fijan el ancho del pipeline y el tamaño del ROB desde la línea de
comandos. Todo lo demás (2 GHz, cachés, DRAM, binario, modo SE) es idéntico,
para que E2 sea comparable con E1.

Control de calidad: --width 8 --rob 192 son los valores por defecto de O3 en
gem5 v26, o sea exactamente la corrida O3 de E1. Con el mismo N deben dar los
mismos ciclos que results/e1/o3_N<N>.

Uso (desde la raíz del repo):
    gem5.opt -d <salida> configs/run_e2.py --width 4 --rob 64 --size 128
"""

import argparse
import os
import m5

from m5.objects import *

# ============================================================
# CONFIGURACION FIJA (igual que E1)
# ============================================================

# Valores que barre E2 (enunciado: ancho 1, 2, 4, 8 y ROB 32, 64, 192).
WIDTHS = [1, 2, 4, 8]
ROB_SIZES = [32, 64, 192]

FREQUENCY = "2GHz"
L1I_SIZE = "32kB"
L1D_SIZE = "32kB"
L2_SIZE = "256kB"

# Binario AArch64 dentro del repositorio proyecto-gem5
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.path.join(PROJECT_DIR, "bin", "gemm_scalar")


# ============================================================
# CONFIGURACION DE CACHES
# ============================================================

class L1Cache(Cache):
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20


class L2Cache(Cache):
    assoc = 8
    tag_latency = 10
    data_latency = 10
    response_latency = 10
    mshrs = 16
    tgts_per_mshr = 20


# ============================================================
# ARGUMENTOS SELECCIONABLES
# ============================================================

parser = argparse.ArgumentParser(description="Experimento E2 GEMM (O3 superescalar)")

# Ancho del pipeline: se aplica igual a TODAS las etapas (ver más abajo).
parser.add_argument(
    "--width",
    required=True,
    type=int,
    choices=WIDTHS
)

# Entradas del reorder buffer (ROB).
parser.add_argument(
    "--rob",
    required=True,
    type=int,
    choices=ROB_SIZES
)

parser.add_argument(
    "--size",
    required=True,
    type=int,
    choices=[64, 128]
)

args = parser.parse_args()


# ============================================================
# VALIDACIONES
# ============================================================

if not os.path.isfile(BINARY):
    raise SystemExit("ERROR: No existe el binario AArch64: " + BINARY)

if not os.access(BINARY, os.X_OK):
    raise SystemExit("ERROR: El binario no tiene permisos de ejecucion")


# ============================================================
# SISTEMA
# ============================================================

system = System()

# Un solo nucleo O3 (la misma clase que usa E1 para "o3")
system.cpu = DerivO3CPU(cpu_id=0)

# Ancho coherente: todas las etapas mueven el mismo número de instrucciones por
# ciclo. Si solo se cambiara issueWidth, fetch o commit seguirían en 8 y el
# experimento no mediría "un núcleo de ancho W". squashWidth no se toca: por
# defecto gem5 descarta las instrucciones de un fallo de predicción en un ciclo.
system.cpu.fetchWidth = args.width
system.cpu.decodeWidth = args.width
system.cpu.renameWidth = args.width
system.cpu.dispatchWidth = args.width
system.cpu.issueWidth = args.width
system.cpu.wbWidth = args.width
system.cpu.commitWidth = args.width

# Parámetro DEL SIMULADOR, no del hardware: cuántos ciclos hacia adelante puede
# reservar IEW un puerto de escritura cuando terminan más instrucciones que
# wbWidth en el mismo ciclo. Con ancho 1 o 2, varias cargas que esperaban la misma
# línea terminan juntas y se pasan del valor por defecto (5): gem5 aborta con
# "TimeBuffer out-of-bounds access! ... Increase forwardComSize". 64 cubre el peor
# caso (LQ de 32 + las emitidas en el ciclo). Se aplica a TODAS las configuraciones;
# parse_e2.py comprueba que ancho 8 / ROB 192 siga dando los ciclos exactos de E1.
system.cpu.forwardComSize = 64

# Tamaño del ROB. El resto de las colas queda en sus valores por defecto de
# gem5 v26 (IQ = 64, LQ = 32, SQ = 32, 256 registros físicos por tipo), igual
# que en E1. Se dejan fijos a propósito: E2 aísla el efecto del ancho y del ROB.
system.cpu.numROBEntries = args.rob

# Frecuencia fija
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = FREQUENCY
system.clk_domain.voltage_domain = VoltageDomain()
system.cpu.clk_domain = system.clk_domain

# Memoria principal
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MiB")]

system.membus = SystemXBar()

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

system.system_port = system.membus.cpu_side_ports


# ============================================================
# JERARQUIA DE CACHES FIJA
# ============================================================

system.l2bus = L2XBar()

system.cpu.icache = L1Cache(size=L1I_SIZE)
system.cpu.dcache = L1Cache(size=L1D_SIZE)
system.l2cache = L2Cache(size=L2_SIZE)

system.cpu.icache.cpu_side = system.cpu.icache_port
system.cpu.icache.mem_side = system.l2bus.cpu_side_ports

system.cpu.dcache.cpu_side = system.cpu.dcache_port
system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

system.l2cache.cpu_side = system.l2bus.mem_side_ports
system.l2cache.mem_side = system.membus.cpu_side_ports

system.cpu.createInterruptController()
system.cpu.connectUncachedPorts(system.membus.cpu_side_ports, system.membus.mem_side_ports)


# ============================================================
# PROGRAMA AARCH64 EN MODO SE
# ============================================================

process = Process()
process.executable = BINARY
process.cmd = [BINARY, str(args.size)]

system.workload = SEWorkload.init_compatible(BINARY)

system.cpu.workload = process
system.cpu.createThreads()


# ============================================================
# SIMULACION
# ============================================================

root = Root(full_system=False, system=system)

m5.instantiate()

print("\n========== EXPERIMENTO E2 ==========")
print("Arquitectura: AArch64")
print("Modo: SE")
print("CPU: o3")
print("Ancho (fetch/decode/rename/dispatch/issue/wb/commit):", args.width)
print("ROB:", args.rob)
print("Nucleos: 1")
print("N:", args.size)
print("Frecuencia:", FREQUENCY)
print("L1I:", L1I_SIZE)
print("L1D:", L1D_SIZE)
print("L2:", L2_SIZE)
print("Binario:", BINARY)
print("===================================\n")

exit_event = m5.simulate()

print("Simulacion finalizada:", exit_event.getCause())

m5.stats.dump()
