FROM python:3.11@sha256:ec566492c6fa75c223d11a3bf7712cf2b11d7f4ae3caa2d96ff7cc2281bfc9ed

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT [ "python", "/usr/src/app/mirror-images.py"]
