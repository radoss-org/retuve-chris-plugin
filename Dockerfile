# sudo docker build --network=host -t docker.io/sharp6292/retuve_chris_plugin:1.0.0 .
# chris_plugin_info --dock-image docker.io/sharp6292/retuve_chris_plugin:1.0.0 > description.json
# sudo docker push docker.io/sharp6292/retuve_chris_plugin:1.0.0

FROM python:3.10
WORKDIR /usr/local/src
COPY . .
RUN pip install .
CMD ["retuve_chris_plugin", "--help"]