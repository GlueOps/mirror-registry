FROM python:3.12@sha256:11e5de79af775dc79e765116bfd2cd574e3ba0bc0aa87c29bb3ef7b8d03194bb

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT [ "python", "/usr/src/app/mirror-images.py"]
