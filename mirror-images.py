from typing import Optional
import docker
import yaml
import json
import os
import base64
import requests
import re
import sys
import time
from datetime import timedelta,datetime, timezone

if len(sys.argv) < 2:
    print("❌ Error: No YAML file path provided!")
    sys.exit(1)

config_path = sys.argv[1]  # Get the file path from GitHub Actions input

if not os.path.isfile(config_path):
    print(f"❌ Error: Config file '{config_path}' not found!")
    sys.exit(1)


client = docker.DockerClient(base_url="unix://var/run/docker.sock")

secret_base64 = os.environ['SECRET_BASE64']
registry_auth_creds = json.loads(base64.b64decode(secret_base64))

config = {}
with open(config_path, "r") as f:
    config = yaml.safe_load(f)


def registry_auth(client,registry_authentication:dict[str])->None:
    for auth in registry_authentication:
        res = client.login(
            username=auth["username"],
            email=auth["email"],
            password=auth["password"],
            registry=auth["name"],
        )

def is_regex(tag:str) -> bool:
    regex_metachars = r"*+?[]{}()|^$\\"
    return any(char in tag for char in regex_metachars)



def list_tags(repo:str,token:str,patterns:list[str],date_limit:datetime) -> list[str]:
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags?page_size=100"
    tags = []
    headers = {}
    if token:
        headers = {
            "Authorization": f"Bearer {token}"
        }
    while url:
        time.sleep(0.5)
        response = requests.get(url,headers=headers).json()
        for result in response["results"]:
            if len(patterns) == 0:
                tags.append(result['name'])
            for pattern in patterns:
                matched = re.fullmatch(pattern, result['name'])
                if matched:
                    tags.append(result['name'])
                    break
            tag_date = datetime.fromisoformat(result['last_updated'][:-1])
            if tag_date < date_limit:
                return tags
        if patterns:
            url = response.get("next")
        else:
            url = None
    return tags


def check_tag(repo:str,token:str,tag:str):
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags/{tag}"
    headers = {}
    if token:
        headers = {
            "Authorization": f"Bearer {token}"
        }
    response = requests.get(url,headers=headers)
    return response.status_code == 200

def calculate_date_limit(time_span:Optional[str])-> datetime:
    desired_date = datetime.now(tz=timezone.utc) - timedelta(days=3)

    if time_span is None:
        pass
    elif 'm' in time_span:
        time_span = int(time_span.replace("m",""))
        desired_date = datetime.now() - timedelta(days=30*time_span)
    elif 'd' in time_span:
        time_span = int(time_span.replace("d",""))
        desired_date = datetime.now() - timedelta(days=time_span)
    return desired_date

def mirror_image(client,config:dict)->None:
    docker_images = config["images"]
    registry = list(filter(lambda i: i['name']=="index.docker.io",registry_auth_creds['auths']))
    
    token = None
    if registry:
        token = registry[0]['password']

    date_limit = calculate_date_limit(config['time_span'])
    
    for image_desc in docker_images:
        repo_name = image_desc['image'].replace("docker.io/","")
        regex_tags = []
        tags = []
        for t in image_desc['tags']:
            if is_regex(t):
                regex_tags.append(t)
            else:
                tag_exist = check_tag(repo_name,token,t)
                if tag_exist: tags.append(t)
        if regex_tags:
            tags.extend(list_tags(repo_name,token,regex_tags,date_limit))
        for tag in tags:
            pull_url = f"{repo_name}:{tag}"
            image = client.images.pull(
                image_desc["image"], tag=tag
            )
            for target_registry in config['destination_registries']:
                image.tag(
                    f"{target_registry}/{config['repo_prefix']}/{pull_url}",
                    tag=tag
                )
                print(
                    f"mirroring the image: {target_registry}/{config['repo_prefix']}/{pull_url}"
                )
                res = client.images.push(
                    f"{target_registry}/{config['repo_prefix']}/{pull_url}"
                )
    return None

registry_auth(client,registry_auth_creds['auths'])
mirror_image(client,config)
