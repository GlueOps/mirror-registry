FROM python:3.11@sha256:aeb7cf72ae3acee0a0af0a6e09023201a103d359cf64da9fcd06bdfdef98c24f

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT [ "python", "/usr/src/app/mirror-images.py"]
