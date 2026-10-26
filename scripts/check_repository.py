"""Falla si Git contiene secretos evidentes, rasters/pesos o archivos > 5 MiB."""

from pathlib import Path
import subprocess


def main() -> None:
    """Inspecciona sólo archivos versionados; no analiza el contenido de secretos."""
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    forbidden = {".tif", ".tiff", ".jp2", ".pt", ".pth", ".onnx", ".ckpt", ".npz"}
    problems = []
    for name in filter(None, names):
        path = Path(name)
        is_secret = path.name.startswith(".env") and path.name != ".env.example"
        if is_secret or path.suffix.lower() in forbidden or path.stat().st_size > 5*1024**2:
            problems.append(name)
    if problems:
        raise SystemExit("Archivos no permitidos: " + ", ".join(problems))
    print("OK: sin rasters/pesos, .env ni archivos mayores a 5 MiB versionados.")


if __name__ == "__main__":
    main()
