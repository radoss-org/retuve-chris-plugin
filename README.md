# Retuve ChRIS Plugin

![](https://files.mcaq.me/22ha2.png)

Using:
- https://github.com/radoss-org/retuve
- https://chrisproject.org/


## Setup

We recommend using [MiniChRIS](https://github.com/FNNDSC/miniChRIS-docker) to run ChRIS.

## Plugin Building

The Docker image is automatically built and published to GitHub Container Registry via GitHub Actions when code is pushed to the main branch or when tags are created.

### Manual Building (if needed)

```bash
sudo docker build -t ghcr.io/radoss-org/retuve-chris-plugin:latest .
sudo docker push ghcr.io/radoss-org/retuve-chris-plugin:latest
```

### Pulling the Image

```bash
sudo docker pull ghcr.io/radoss-org/retuve-chris-plugin:latest
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
  ghcr.io/radoss-org/retuve-chris-plugin:latest \
  retuve_chris_plugin /incoming /outgoing
```

```bash
uv pip install --no-deps .
dotenv run -- retuve_chris_plugin retuve-data/default/uploaded retuve-data/default/savedir
```

Suitable files for testing purposes can be found here: https://github.com/radoss-org/radoss-creative-commons/tree/main/dicoms/ultrasound

```bash
sudo docker run --rm ghcr.io/radoss-org/retuve-chris-plugin:latest chris_plugin_info -d ghcr.io/radoss-org/retuve-chris-plugin:latest > description.json
```

## Useful Resources
- https://github.com/FNNDSC/python-chrisapp-template
