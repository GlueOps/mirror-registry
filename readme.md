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
            "name": "docker.io",
            "username": "",
            "email": "",
            "password": ""
        },
    ]
}
```

currently we support ghcr, quay.

so encode the file in base64 then save it as github secret with the following name: `SECRET_BASE64`

the second file is a reference for the images and their tags that will be copied, example

```yaml
destination_registry: 
    - 
images:
    - image: docker.io/hashicorp/vault
      tags:
        - v1.0
        - v2.*
        - v*.*.*-rc1
    - image: docker.io/grafana/loki
      tags: [] # pick the last 10 tags
```
