# Docker (extra)

Empaqueta la API y el visor en una imagen. Así cualquiera los levanta con un solo
comando, sin crear `.venv` ni instalar Python.

Los datos y el modelo **no** van dentro de la imagen (pesan mucho y no están en Git):
se montan en modo solo lectura desde las carpetas `data/` y `models/` del repo.

## Requisitos

- Docker Desktop instalado y abierto (Windows: https://www.docker.com/products/docker-desktop/).
- En el repo: `data/interim/historical-inputs-v1`, `data/interim/labels-mapbiomas-v1`,
  `data/processed/dataset-v1` y `models/unet-v1.pt`.

## Uso

```powershell
cd "C:\ruta\al\Monitoreo-Satelital"
docker compose up --build
```

La primera vez tarda unos minutos (descarga Python y PyTorch). Después es inmediato.
Abrir <http://127.0.0.1:8000/>. Para apagar: `Ctrl + C`, o `docker compose down`.

Comprobar que encontró los datos: <http://127.0.0.1:8000/health> debe decir
`"status": "ok"`. Si dice `"incompleto"`, falta alguna carpeta de las de arriba.

## Qué hay en cada archivo

| Archivo | Qué hace |
|---|---|
| `Dockerfile` | Receta de la imagen: Python 3.12, PyTorch CPU, dependencias, código de `src/`, `api/` y `web/` |
| `.dockerignore` | Deja afuera `.venv`, datos, modelos y Git para que la imagen sea liviana |
| `docker-compose.yml` | Publica el puerto 8000 y monta `data/` y `models/` en solo lectura |

CI construye la imagen y verifica que la API y el visor respondan en cada push.
