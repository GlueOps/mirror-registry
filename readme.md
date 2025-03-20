to run the action, you need two files:
the first file is `secret.json` contains the auths for the destination registries.

here is an example of the format:

```json
{
    "auths": [
        {
            "name": "ghcr.io",
            "username": "",
            "email": "",
            "password": ""
        },
        {
            "name": "quay.io",
            "username": "",
            "email": "",
            "password": ""
        },
        {
            "name": "index.docker.io",
            "username": "",
            "email": "",
            "password": ""
        },
    ]
}
```

currently we support ghcr, quay.

note: if you dont want to hit the rate limit, use short time_span or exact match tags

so encode the file in base64 then save it as github secret with the following name: `SECRET_BASE64`

the second file is a reference for the images and their tags that will be copied, example

```yaml
destination_registries: 
  - ghcr.io
  - quay.io
repo_prefix: "glueops/mirror"
time_span: 5d # d,m default to 3d
images:
  - image: docker.io/grafana/grafana
    tags:
      - "10.4.13"
  - image: docker.io/grafana/loki
    tags: 
      - "2.*"
```

here is an example of how you will use it in github action:

```yaml
name: Test Docker on GitHub Actions

on:
  pull_request:
  push:
    branches: 
      - master

jobs:
  push_container:
    runs-on: ubuntu-latest
    services:
      docker:
        image: docker:dind
        options: --privileged --shm-size=2g
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
    container:
      image: ubuntu:latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Mirror Image
        id: MirrorImage
        uses: actions/mirror-registr@v1
        with:
          config-file-path: 'images-config.yaml'
        env:
          SECRET_BASE64: ${{ secrets.SECRET_BASE64 }}
```