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



def list_ghcr_tags(repo:str,token:str,patterns:list[str],date_limit:datetime)->list[str]:
    current_page = 1
    tags = []
    base_registry = repo.split("/")[0]
    package_name = "%2F".join(repo.split("/")[1:])
    headers = {}
    if token:
        headers = {
            "Authorization": f"Bearer {token}"
        }
    print(base_registry,package_name)
    while True:
        time.sleep(0.5)
        url = f"https://api.github.com/orgs/{base_registry}/packages/container/{package_name}/versions?per_page=100&page={current_page}"
        response = requests.get(url,headers=headers)
        if response.status_code != 200:
            print(response.text)
            return tags
        response = response.json()
        for result in response:
            for pattern in patterns:
                matched = re.fullmatch(pattern, result['metadata']['container']['tags'][0])
                if matched:
                    tags.append(result['metadata']['container']['tags'][0])
                    break
            tag_date = datetime.fromisoformat(result['created_at'])
            if tag_date < date_limit:
                return tags
        if response:
            current_page+=1
        else:
            return tags

def list_quay_tags(repo:str,token:str,patterns:list[str],date_limit:datetime)->list[str]:
    current_page = 1
    date_format = "%a, %d %b %Y %H:%M:%S %z"
    tags = []
    headers = {}
    
    if token:
        headers = {
            "Authorization": f"Bearer {token}"
        }
    while True:
        time.sleep(0.5)
        url = f"https://quay.io/api/v1/repository/{repo}/tag?limit=100&page={current_page}"
        response = requests.get(url,headers=headers)
        if response.status_code != 200:
            print(response.text)
            return tags
        response = response.json()
        for result in response['tags']:
            for pattern in patterns:
                matched = re.fullmatch(pattern, result['name'])
                if matched:
                    tags.append(result['name'])
                    break
            tag_date = datetime.strptime(result['last_modified'], date_format)
            if tag_date < date_limit:
                return tags
        if response['has_additional']:
            current_page+=1
        else:
            return tags


def list_dockerhub_tags(repo:str,token:str,patterns:list[str],date_limit:datetime) -> list[str]:
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags?page_size=100"
    tags = []
    headers = {}
    if token:
        headers = {
            "Authorization": f"Bearer {token}"
        }
    while url:
        time.sleep(0.5)
        response = requests.get(url,headers=headers)
        if response.status_code != 200:
            print(response.text)
            return tags
        response = response.json()

        for result in response["results"]:
            print(f"matching against {result['name']}")
            for pattern in patterns:
                matched = re.fullmatch(pattern, result['name'])
                if matched:
                    tags.append(result['name'])
                    break
            tag_date = datetime.fromisoformat(result['last_updated'])
            if tag_date < date_limit:
                return tags
        url = response.get("next")
    return tags


def calculate_date_limit(time_span:Optional[str])-> datetime:
    desired_date = datetime.now(timezone.utc) - timedelta(days=3)

    if time_span is None:
        pass
    elif 'm' in time_span:
        time_span = int(time_span.replace("m",""))
        desired_date = datetime.now(timezone.utc) - timedelta(days=30*time_span)
    elif 'd' in time_span:
        time_span = int(time_span.replace("d",""))
        desired_date = datetime.now(timezone.utc) - timedelta(days=time_span)
    return desired_date


def get_registry_token(registry:str,registry_auth_creds:dict):
    registry = list(filter(lambda i: i['name']==registry,registry_auth_creds['auths']))
    token = None
    if registry:
        if registry[0].get("api_auth",{}):
            token = registry['api_auth']['password']
        else:
            token = registry[0]['password']
    return token

def mirror_image(client,config:dict)->None:
    docker_images = config["images"]
    date_limit = calculate_date_limit(config['time_span'])
    
    for image_desc in docker_images:
        base_registry = image_desc['image'].split("/")[0]
        repo_name = "/".join(image_desc['image'].split("/")[1:])
        regex_tags = []
        tags = []
        token = get_registry_token(base_registry,registry_auth_creds)
        for t in image_desc['tags']:
            if is_regex(t):
                regex_tags.append(t)
            else:
                tags.append(t)
        
        if regex_tags:
            if base_registry == "docker.io":
                tags.extend(
                    list_dockerhub_tags(repo_name,token,regex_tags,date_limit)
                )
            elif base_registry == "ghcr.io":
                tags.extend(
                    list_ghcr_tags(repo_name,token,regex_tags,date_limit)
                )
            elif base_registry == "quay.io":
                tags.extend(
                    list_quay_tags(repo_name,token,regex_tags,date_limit)
                )
        for tag in tags:
            pull_url = f"{repo_name}:{tag}"
            try:
                image = client.images.pull(
                    image_desc["image"], tag=tag
                )
            except docker.errors.APIError as e:
                print(f"We couldn't find the following: {image_desc['image']}:{tag}")
                continue
            for target_registry in config['destination_registries']:
                if config['repo_prefix']:
                    destination_url = f"{target_registry}/{config['repo_prefix']}/{pull_url}"
                else:
                    destination_url = f"{target_registry}/{pull_url}"
                image.tag(destination_url,tag=tag)
                print(f"mirroring the image: {destination_url}")
                res = client.images.push(destination_url)
                print(res)

registry_auth(client,registry_auth_creds['auths'])
mirror_image(client,config)
