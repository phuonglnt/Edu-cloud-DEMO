FROM python:3.12-slim

ARG http_proxy
ARG https_proxy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sync.py .

CMD ["python", "sync.py"]
