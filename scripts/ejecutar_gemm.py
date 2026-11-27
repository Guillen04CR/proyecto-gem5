
import subprocess
from pathlib import Path

# ============================================================
# 1. CONFIGURACION DE RUTAS
# ============================================================

PROYECTO = Path(__file__).resolve().parent.parent
GEM5 = Path.home() / "proyectos/gem5"

SIMULADOR = GEM5 / "build/X86/gem5.opt"
CONFIG = GEM5 / "configs/deprecated/example/se.py"
BINARIO = PROYECTO / "bin/gemm"
RESULTADOS = PROYECTO / "results"

# ============================================================
# 2. VERIFICACION DE ARCHIVOS
# ============================================================

for archivo in [SIMULADOR, CONFIG, BINARIO]:
    if not archivo.is_file():
        raise FileNotFoundError(f"No se encontro: {archivo}")

RESULTADOS.mkdir(parents=True, exist_ok=True)

# ============================================================
# 3. CONFIGURACION DEL EXPERIMENTO E4
# ============================================================

nucleos = [1, 2, 4, 8]

for n in nucleos:

    salida = RESULTADOS / f"gemm_{n}_check"
    salida.mkdir(parents=True, exist_ok=True)

    comando = [
        str(SIMULADOR),
        "-d", str(salida),
        str(CONFIG),
        "--cpu-type=O3CPU",
        f"--num-cpus={n}",
        "--caches",
        "--l2cache",
        "-P", "system.cpu[:].fetchWidth=2",
        "-P", "system.cpu[:].decodeWidth=2",
        "-P", "system.cpu[:].renameWidth=2",
        "-P", "system.cpu[:].dispatchWidth=2",
        "-P", "system.cpu[:].issueWidth=2",
        "-P", "system.cpu[:].wbWidth=2",
        "-P", "system.cpu[:].commitWidth=2",
        "-P", "system.cpu[:].forwardComSize=10",
        "-c", str(BINARIO),
        "-o", f"128 {n}"
    ]

    print(f"\nEjecutando GEMM con {n} nucleos...")

    with open(salida / "console.txt", "w") as archivo:

        resultado = subprocess.run(
            comando,
            stdout=archivo,
            stderr=subprocess.STDOUT,
            cwd=PROYECTO
        )

    if resultado.returncode == 0:
        print(f"Simulacion de {n} nucleos completada.")
    else:
        print(f"Error en la simulacion de {n} nucleos.")
        print(f"Revisar: {salida / 'console.txt'}")
        break
