FROM python:3.10

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglx-mesa0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/local/src

# Install uv (package manager)
COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/

# Copy only dependency files first for better caching
COPY requirements.txt setup.py ./

ENV UV_LINK_MODE=copy
# Install dependencies into the venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system -r requirements.txt

# Copy source code
COPY retuve_chris_plugin/ ./retuve_chris_plugin/
RUN uv pip install --system --no-cache-dir --no-deps .
RUN chown -R 1001:1001 /usr/local/lib/python3.10/site-packages/choreographer/
RUN chown -R 1001:1001 /usr/local/lib/python3.10/site-packages/retuve_yolo_plugin/weights/

USER 1001

WORKDIR /home/chris/

RUN chown -R 1001:1001 /home/chris/

ENV MPLCONFIGDIR=/tmp/matplotlib
ENV XDG_CACHE_HOME=/tmp/.cache
ENV YOLO_CONFIG_DIR=/tmp/Ultralytics

COPY images/ /home/chris/images/

# Default command
CMD ["retuve_chris_plugin", "--help"]