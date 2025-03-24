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


def check_error_msg_exist(msg:str) -> bool:
    keywords = ["error", "permission_denied", "denied", "errorDetail", "fail", "unauthorized"]
    exist = any([key in msg for key in keywords])
    return exist

def registry_auth(client,registry_authentication:dict[str])->None:
    for auth in registry_authentication:
        res = client.login(
            username=auth["username"],
            password=auth["password"],
            registry=auth["name"],
        )
        if check_error_msg_exist(res):
            exit(1)


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


def list_ecr_tags(repo:str,patterns:list[str],date_limit:datetime) -> list[str]:
    url = f"https://api.us-east-1.gallery.ecr.aws/describeImageTags"
    tags = []
    headers = {}
    nextToken = None
    
    while True:
        time.sleep(0.5)
        request_data = {
            "registryAliasName": repo.split("/")[0],
            "repositoryName": "/".join(repo.split("/")[1:]),
            "maxResults": 100,
        }
        if nextToken:
            request_data.update({
                "nextToken": nextToken
            })
        response = requests.post(url,headers=headers,json=request_data)
        if response.status_code != 200:
            return tags
        response = response.json()
       
        for result in response["imageTagDetails"]:
            tag_date = datetime.fromisoformat(result['createdAt'])
            if tag_date < date_limit:
                continue
            for pattern in patterns:
                matched = re.fullmatch(pattern, result['imageTag'])
                if matched:
                    tags.append(result['imageTag'])
                    break
        nextToken = response.get("nextToken", None)
        if not nextToken:
            break
    return tags


def list_k8s_registry_tags(repo:str,patterns:list[str],date_limit:datetime) -> list[str]:
    url = f"https://registry.k8s.io/v2/{repo}/tags/list"
    tags = []
    response = requests.get(url)
    if response.status_code != 200:
        return tags
    response = response.json()
    for _,v in response["manifest"].items():
        if len(v['tag']) > 0:
            tag = v['tag'][0]
        else:
            continue
        tag_date = datetime.fromtimestamp(
            int(v['timeUploadedMs'])/1000,
            tz=timezone.utc
        )
        if tag_date < date_limit:
            continue
        for pattern in patterns:
            matched = re.fullmatch(pattern, tag)
            if matched:
                tags.append(tag)
                break
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
            elif base_registry == "public.ecr.aws":
                tags.extend(
                    list_ecr_tags(repo_name,regex_tags,date_limit)
                )
            elif base_registry == "registry.k8s.io":
                tags.extend(
                    list_k8s_registry_tags(repo_name,regex_tags,date_limit)
                )
        print(f'matched tags: {tags}')
        for tag in tags:
            pull_url = f"{repo_name}:{tag}"
            try:
                image = client.images.pull(
                    image_desc["image"], tag=tag
                )
            except docker.errors.APIError as e:
                print(f"We couldn't find the following: {image_desc['image']}:{tag}")
                exit(1)
            for target_registry in config['destination_registries']:
                if config['repo_prefix']:
                    destination_url = f"{target_registry}/{config['repo_prefix']}/{pull_url}"
                else:
                    destination_url = f"{target_registry}/{pull_url}"
                image.tag(destination_url,tag=tag)
                print(f"mirroring the image: {destination_url}")
                res = client.images.push(destination_url)
                print(res)
                if check_error_msg_exist(res):
                    exit(1)


registry_auth(client,registry_auth_creds['auths'])
mirror_image(client,config)
