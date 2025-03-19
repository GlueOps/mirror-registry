import docker
import yaml
import json
import os
import base64
import requests
import re
import argparse

client = docker.DockerClient(base_url="unix://var/run/docker.sock")

secret_base64 = os.environ['SECRET_BASE64']
registry_auth_creds = json.loads(base64.b64decode(secret_base64))

config = {}
config_path = os.environ['INPUT_CONFIG-FILE-PATH']
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

def registry_auth(client,registry_authentication:dict[str])->None:
    for auth in registry_authentication:
        client.login(
            username=auth["username"],
            email=auth["email"],
            password=auth["password"],
            registry=auth["name"],
        )

def list_tags(repo:str,patterns:list[str]) -> list[str]:
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags"
    tags = []
    while url:
        response = requests.get(url).json()
        for result in response["results"]:
            if len(patterns) == 0:
                tags.append(result['name'])
            for pattern in patterns:
                matched = re.fullmatch(pattern, result['name'])
                if matched:
                    tags.append(result['name'])
                    break
        if patterns:
            url = response.get("next")
        else:
            url = None
    return tags

def mirror_image(client,config:dict)->None:
    docker_images = config["images"]
    for image_desc in docker_images:
        repo_name = image_desc['image'].replace("docker.io/","")
        tags = list_tags(repo_name,image_desc['tags'])
        for tag in tags:
            pull_url = f"{image_desc['image']}:{tag}"
            image = client.images.pull(
                image_desc["image"], tag=tag
            )
            for target_registry in config['destination_registries']:
                image.tag(
                    f"{target_registry}/glueops/mirror/{image_desc['image']}",
                    tag=tag
                )
                print(
                    f"mirroring the image: {target_registry}/glueops/mirror/{pull_url}"
                )
                res = client.images.push(
                    f"{target_registry}/glueops/mirror/{pull_url}"
                )
    return None

registry_auth(client,registry_auth_creds['auths'])
mirror_image(client,config)