# sudo docker build --network=host -t docker.io/sharp6292/retuve_chris_plugin:1.0.0 .
# chris_plugin_info --dock-image docker.io/sharp6292/retuve_chris_plugin:1.0.0 > description.json
# sudo docker push docker.io/sharp6292/retuve_chris_plugin:1.0.0

FROM python:3.10

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libgl1-mesa-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/local/src
COPY . .
RUN pip install --no-cache-dir .
CMD ["retuve_chris_plugin", "--help"]