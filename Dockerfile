# MaSTRspy Dockerfile — GUI + full bioinformatics tool chain
# Usage: docker run -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix mastrspy

# ── Stage 1: builder (compile xatlas from source) ──────────────────────────
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        zlib1g-dev \
        libbz2-dev \
        liblzma-dev \
        libcurl4-openssl-dev \
        libhts-dev \
    && rm -rf /var/lib/apt/lists/*

# Build xatlas from source
RUN git clone --depth 1 https://github.com/broadinstitute/xatlas.git /tmp/xatlas \
    && cd /tmp/xatlas \
    && mkdir build && cd build \
    && cmake .. \
    && make -j"$(nproc)" \
    && cp xatlas /usr/local/bin/xatlas

# ── Stage 2: runtime ───────────────────────────────────────────────────────
FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System packages: Python 3.11, bioinformatics tools, X11/GL libs for PySide6
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-venv \
        python3.11-dev \
        python3-pip \
        samtools \
        bedtools \
        minimap2 \
        # X11 / OpenGL dependencies for PySide6 GUI
        libgl1 \
        libegl1 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libxkbcommon-x11-0 \
        libdbus-1-3 \
        libfontconfig1 \
        libxrender1 \
        # htslib runtime dependency for xatlas
        libhts3 \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 the default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python  python  /usr/bin/python3.11 1

# Copy xatlas binary from builder stage
COPY --from=builder /usr/local/bin/xatlas /usr/local/bin/xatlas

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY pyproject.toml ./
RUN python3 -m pip install --no-cache-dir --upgrade pip \
    && python3 -m pip install --no-cache-dir .

# Copy application code, database, and config
COPY src/        src/
COPY main.py     main.py
COPY MaSTRDB/    MaSTRDB/
COPY config/     config/

CMD ["python3", "main.py"]
