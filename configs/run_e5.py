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