FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ffmpeg normalise les enregistrements avant Azure Speech. ca-certificates est
# requis pour les appels HTTPS vers Azure et le stockage objet.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -c "import uvicorn; print('uvicorn', uvicorn.__version__)"

COPY backend/ /app/

# Railway injecte PORT à l'exécution. Aucun port de repli ni EXPOSE statique :
# l'image échoue clairement si la plateforme ne fournit pas la variable.
CMD ["sh", "-c", "test -n \"$PORT\" || { echo 'PORT environment variable is required' >&2; exit 1; }; exec uvicorn server:app --host 0.0.0.0 --port \"$PORT\""]
