FROM python:3.11@sha256:ebfa8696e47a68cffebb31e370a93ce57c01bc753f246ceaaef72801d1661351

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT [ "python", "/usr/src/app/mirror-images.py"]
