# Retuve ChRIS Plugin

![](https://files.mcaq.me/22ha2.png)

Using:
- https://github.com/radoss-org/retuve
- https://chrisproject.org/


## Setup

We recommend using [MiniChRIS](https://github.com/FNNDSC/miniChRIS-docker) to run ChRIS.

## Plugin Building

```bash
sudo docker build --network=host -t docker.io/sharp6292/retuve_chris_plugin:1.0.0 .
chris_plugin_info --dock-image docker.io/sharp6292/retuve_chris_plugin:1.0.0 > description.json
sudo docker push docker.io/sharp6292/retuve_chris_plugin:1.0.0
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
docker run --rm -v $PWD/retuve-data/default/uploaded:/incoming \
    -v $PWD/retuve-data/default/savedir:/outgoing docker.io/sharp6292/retuve_chris_plugin:1.0.0 \
    retuve_chris_plugin /incoming /outgoing
```

```bash
retuve_chris_plugin retuve-data/default/uploaded retuve-data/default/savedir

## Useful Resources
- https://github.com/FNNDSC/python-chrisapp-template