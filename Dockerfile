# Imagen de la API + visor. Los datos y el modelo NO van dentro de la imagen:
# se montan desde la compu con volúmenes (ver docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Torch solo CPU (unos 200 MB en vez de varios GB con CUDA).
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.8.0
COPY requirements.txt ./
RUN pip install -r requirements.txt fastapi==0.120.0 uvicorn==0.38.0

COPY src ./src
COPY api ./api
COPY web ./web

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
