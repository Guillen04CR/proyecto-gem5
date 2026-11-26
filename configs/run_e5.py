import argparse
import os
import sys

import m5
from m5.defines import buildEnv
from m5.objects import (
    AddrRange,
    ArmTimingSimpleCPU,
    Process,
    Root,
    SEWorkload,
    SrcClockDomain,
    System,
    VoltageDomain,
)

from gem5.isas import ISA


# Ruby, Options y sus topologias viven en el clon externo de gem5, no en este
# repositorio. run_e5.sh exportara esta ruta de forma reproducible.
GEM5_CONFIGS = os.environ.get("GEM5_CONFIGS")
if not GEM5_CONFIGS or not os.path.isdir(GEM5_CONFIGS):
    raise SystemExit(
        "ERROR: GEM5_CONFIGS debe apuntar al directorio <gem5>/configs"
    )
sys.path.insert(0, GEM5_CONFIGS)

from common import Options  # noqa: E402  (requiere GEM5_CONFIGS arriba)
from ruby import Ruby  # noqa: E402


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BINARY = os.path.join(PROJECT_DIR, "bin", "false_sharing")
VALID_PROTOCOLS = {"MESI_Two_Level", "MOESI_CMP_directory"}


def positive_int(value):
    """Argumento argparse para una cantidad positiva de iteraciones."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("debe ser un entero") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("debe ser mayor que cero")
    return parsed

parser = argparse.ArgumentParser(
    description="E5: coherencia Ruby para el microbenchmark false_sharing"
)

# Ruby define parametros de memoria, caches y red.
# Se usa ARM como ISA por defecto aunque los CPU se crean explicitamente abajo.
Options.addCommonOptions(parser, default_isa=ISA.ARM)
Ruby.define_options(parser)

parser.add_argument(
    "--threads",
    type=int,
    choices=[2, 4, 8],
    default=4,
    help="CPU simulados y hilos del benchmark (default: 4)",
)
parser.add_argument(
    "--layout",
    choices=["unpadded", "padded"],
    required=True,
    help="Distribucion de contadores del benchmark",
)
parser.add_argument(
    "--iterations",
    type=positive_int,
    default=100000,
    help="Incrementos por hilo (default: 100000)",
)
parser.add_argument(
    "--binary",
    default=DEFAULT_BINARY,
    help="Ruta al binario AArch64 false_sharing",
)

args = parser.parse_args()

# ---------------------------------------------------------------------------
# Validaciones del contrato E5
# ---------------------------------------------------------------------------
protocol = buildEnv.get("PROTOCOL")
if protocol not in VALID_PROTOCOLS:
    raise SystemExit(
        "ERROR: este experimento requiere un gem5 compilado con MESI_Two_Level "
        "o MOESI_CMP_directory; protocolo actual: " + str(protocol)
    )

if not os.path.isfile(args.binary):
    raise SystemExit("ERROR: no existe el binario AArch64: " + args.binary)
if not os.access(args.binary, os.X_OK):
    raise SystemExit("ERROR: el binario no tiene permiso de ejecucion")

# ---------------------------------------------------------------------------
# Parametros fijos: no se barren en E5
# ---------------------------------------------------------------------------
# Estos valores se establecen despues de parsear para que ninguna opcion casual
# de la linea de comandos cambie una comparacion de protocolos.
args.ruby = True
args.cpu_type = "ArmTimingSimpleCPU"
args.num_cpus = args.threads
args.num_l2caches = args.threads
args.num_dirs = 1
args.sys_clock = "2GHz"
args.cpu_clock = "2GHz"
args.ruby_clock = "2GHz"
args.mem_size = "512MiB"
args.cacheline_size = 64
args.l1i_size = "32kB"
args.l1d_size = "32kB"
args.l2_size = "256kB"
args.topology = "Crossbar"
args.network = "simple"

# ---------------------------------------------------------------------------
# Sistema ARM en modo syscall emulation (SE)
# ---------------------------------------------------------------------------
system = System(
    cpu=[ArmTimingSimpleCPU(cpu_id=index) for index in range(args.threads)],
    mem_mode="timing",
    mem_ranges=[AddrRange(args.mem_size)],
    cache_line_size=args.cacheline_size,
)

system.voltage_domain = VoltageDomain(voltage=args.sys_voltage)
system.clk_domain = SrcClockDomain(
    clock=args.sys_clock, voltage_domain=system.voltage_domain
)
system.cpu_voltage_domain = VoltageDomain()
system.cpu_clk_domain = SrcClockDomain(
    clock=args.cpu_clock, voltage_domain=system.cpu_voltage_domain
)
for cpu in system.cpu:
    cpu.clk_domain = system.cpu_clk_domain

# Un proceso multihilo compartido por los CPU simulados. Cada hilo del programa
# actualiza un contador distinto y gem5 lo programa sobre estos contextos.
process = Process(pid=100)
process.executable = args.binary
process.cmd = [
    args.binary,
    str(args.threads),
    args.layout,
    str(args.iterations),
]
process.cwd = os.getcwd()
process.gid = os.getgid()

for cpu in system.cpu:
    cpu.workload = process
    cpu.createThreads()


# Ruby crea las caches, directorio, red y controladoras del protocolo que ya
# viene incorporado en gem5.opt. No se combinan estas caches con las clasicas
# de E1.
Ruby.create_system(args, False, system)
if args.threads != len(system.ruby._cpu_ports):
    raise SystemExit("ERROR: Ruby no creo un puerto por CPU")

system.ruby.clk_domain = SrcClockDomain(
    clock=args.ruby_clock, voltage_domain=system.voltage_domain
)
for index, cpu in enumerate(system.cpu):
    cpu.createInterruptController()
    system.ruby._cpu_ports[index].connectCpuPorts(cpu)

system.workload = SEWorkload.init_compatible(args.binary)

# Un proceso multihilo compartido por los CPU simulados. Cada hilo del programa
# actualiza un contador distinto y gem5 lo programa sobre estos contextos.
process = Process(pid=100)
process.executable = args.binary
process.cmd = [
    args.binary,
    str(args.threads),
    args.layout,
    str(args.iterations),
]
process.cwd = os.getcwd()
process.gid = os.getgid()

for cpu in system.cpu:
    cpu.workload = process
    cpu.createThreads()


# Ruby crea las caches, directorio, red y controladoras del protocolo que ya
# viene incorporado en gem5.opt. No se combinan estas caches con las clasicas
# de E1.
Ruby.create_system(args, False, system)
if args.threads != len(system.ruby._cpu_ports):
    raise SystemExit("ERROR: Ruby no creo un puerto por CPU")

system.ruby.clk_domain = SrcClockDomain(
    clock=args.ruby_clock, voltage_domain=system.voltage_domain
)
for index, cpu in enumerate(system.cpu):
    cpu.createInterruptController()
    system.ruby._cpu_ports[index].connectCpuPorts(cpu)

system.workload = SEWorkload.init_compatible(args.binary)


# ---------------------------------------------------------------------------
# Simulacion
# ---------------------------------------------------------------------------
root = Root(full_system=False, system=system)
m5.instantiate()

print("\n========== EXPERIMENTO E5 ==========")
print("Arquitectura: AArch64")
print("Modo: SE + Ruby")
print("Protocolo:", protocol)
print("CPU: ArmTimingSimpleCPU")
print("Nucleos / hilos:", args.threads)
print("Layout:", args.layout)
print("Iteraciones por hilo:", args.iterations)
print("Frecuencia CPU/Ruby:", args.cpu_clock, "/", args.ruby_clock)
print("Linea de cache:", str(args.cacheline_size) + "B")
print("L1I/L1D/L2:", args.l1i_size, "/", args.l1d_size, "/", args.l2_size)
print("Topologia:", args.topology)
print("Binario:", args.binary)
print("===================================\n")

exit_event = m5.simulate()
print("Simulacion finalizada:", exit_event.getCause())

# El benchmark ya escribio el bloque 1 de stats.txt al cerrar la ROI. Este
# volcado final conserva un segundo bloque acumulado, igual que en E1.
m5.stats.dump()
