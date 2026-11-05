import argparse
import os
import m5

from m5.objects import *

# ============================================================
# CONFIGURACION FIJA E1
# ============================================================

CPU_TYPES = {
    "timing": TimingSimpleCPU,
    "minor": MinorCPU,
    "o3": DerivO3CPU
}

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

parser = argparse.ArgumentParser(description="Experimento E1 GEMM")

parser.add_argument(
    "--cpu",
    required=True,
    choices=["timing", "minor", "o3"]
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

# Un solo nucleo
system.cpu = CPU_TYPES[args.cpu](cpu_id=0)

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

print("\n========== EXPERIMENTO E1 ==========")
print("Arquitectura: AArch64")
print("Modo: SE")
print("CPU:", args.cpu)
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
