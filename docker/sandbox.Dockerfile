# OpenManus Data Analysis Sandbox 镜像
# ======================================
# 用途：为 DataAnalysis Agent 提供隔离的 Python 执行环境，
#       预装 pandas / numpy / matplotlib 等数据分析核心包。
#
# 构建：
#   docker build -t openmanus-sandbox:latest -f docker/sandbox.Dockerfile .
#
# 验证：
#   docker run --rm openmanus-sandbox:latest python -c "import pandas; import numpy; import matplotlib; print('OK')"

FROM python:3.12-slim

# ── 系统依赖 ──────────────────────────────────────────
# build-essential: 编译 numpy / scipy
# libfreetype6-dev, libpng-dev, pkg-config: matplotlib 渲染
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6-dev \
    libpng-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ── Python 运行时配置 ──────────────────────────────────
ENV MPLBACKEND=Agg \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ── 数据分析核心包 ─────────────────────────────────────
RUN pip install --no-cache-dir \
    pandas~=2.2 \
    numpy~=2.0 \
    matplotlib~=3.9 \
    openpyxl~=3.1 \
    seaborn~=0.13 \
    scikit-learn~=1.5 \
    scipy~=1.14 \
    && python -c "import pandas, numpy, matplotlib; print('✓ Data analysis packages OK')"

# ── 工作目录 ──────────────────────────────────────────
WORKDIR /workspace

# 保持容器运行（等待命令）
CMD ["tail", "-f", "/dev/null"]
