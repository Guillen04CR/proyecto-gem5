# Entorno reproducible del proyecto (mismo que docs/SETUP.md, pero en contenedor).
# La imagen solo trae dependencias: gem5 y el repo viven en ~/arqui del anfitrión
# y se montan como volumen, así la compilación de gem5 (~2 h) se hace una vez y persiste.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential scons python3-dev python3-pydot git m4 \
        zlib1g zlib1g-dev libprotobuf-dev protobuf-compiler libprotoc-dev \
        libgoogle-perftools-dev libboost-all-dev libhdf5-dev libpng-dev \
        libelf-dev libcapstone-dev pkg-config \
        gcc-aarch64-linux-gnu g++-aarch64-linux-gnu qemu-user \
        python3-matplotlib ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# git se queja de "dubious ownership" cuando el repo montado tiene otro dueño.
RUN git config --system --add safe.directory '*'

# HOME del contenedor (/work). Se deja escribible para cualquier usuario: el
# contenedor corre con el UID del anfitrión y scons, git y python guardan caché en ~.
RUN mkdir -p /work && chmod 1777 /work

# Imprime las versiones al construir: deben coincidir con la tabla de SETUP.md
# (aarch64-linux-gnu-gcc 13.3.0). Si no, simInsts y simTicks cambian.
RUN aarch64-linux-gnu-gcc --version | head -n1 && scons --version | tail -n1

WORKDIR /work/arqui/proyecto-gem5
CMD ["bash"]
