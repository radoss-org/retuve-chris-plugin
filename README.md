# Retuve ChRIS Plugin

![](https://files.mcaq.me/22ha2.png)

Using:
- https://github.com/radoss-org/retuve
- https://chrisproject.org/


## Setup

We recommend using [MiniChRIS](https://github.com/FNNDSC/miniChRIS-docker) to run ChRIS.

## Plugin Building

```bash
sudo docker build -t docker.io/sharp6292/retuve_chris_plugin:1.0.0 .
sudo docker push docker.io/sharp6292/retuve_chris_plugin:1.0.0
```

```bash
sudo docker pull docker.io/sharp6292/retuve_chris_plugin:1.0.0
```

### Plugin Upload

```bash
curl -u "chris:chris1234" http://localhost:8000/chris-admin/api/v1/ \
    -H 'Accept: application/json' \
    -F fname=@description.json \
    -F compute_names=host
```

## Required Pipeline

This will be changed in the future to not require the unstacking of folders.

![](https://files.mcaq.me/kb495.png)

## Plugin Testing

```bash
sudo docker run --rm \
  -v $PWD/retuve-data/default/uploaded:/incoming \
  -v $PWD/retuve-data/default/savedir:/outgoing \
  --user 1001 \
  docker.io/sharp6292/retuve_chris_plugin:1.0.0 \
  retuve_chris_plugin /incoming /outgoing
```

```bash
pip install --no-deps .
retuve_chris_plugin retuve-data/default/uploaded retuve-data/default/savedir
```

Suitable files for testing purposes can be found here: https://github.com/radoss-org/radoss-creative-commons/tree/main/dicoms/ultrasound

```bash
sudo docker run --rm docker.io/sharp6292/retuve_chris_plugin:1.0.0 chris_plugin_info -d docker.io/sharp6292/retuve_chris_plugin:1.0.0 > description.json
```


## Useful Resources
- https://github.com/FNNDSC/python-chrisapp-template
