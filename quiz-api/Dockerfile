FROM python:3.12-slim

ENV http_proxy=http://cache.univ-pau.fr:3128
ENV https_proxy=http://cache.univ-pau.fr:3128

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
