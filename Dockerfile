FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglx-mesa0 \
    libnss3 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/local/src

# Install uv (package manager)
COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/

# Copy only dependency files first for better caching
COPY requirements.txt requirements.txt

ENV UV_LINK_MODE=copy
# Install dependencies into the venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match

# Copy source code
COPY retuve_chris_plugin/ ./retuve_chris_plugin/
COPY setup.py setup.py
RUN uv pip install --system --no-cache-dir --no-deps .
RUN kaleido_get_chrome
RUN chown -R 1001:1001 /usr/local/lib/python3.11/site-packages/choreographer/
RUN chown -R 1001:1001 /usr/local/lib/python3.11/site-packages/retuve_yolo_plugin/weights/

USER 1001

WORKDIR /home/chris/

RUN chown -R 1001:1001 /home/chris/

COPY images/ /home/chris/images/

# Default command
CMD ["retuve_chris_plugin", "--help"]