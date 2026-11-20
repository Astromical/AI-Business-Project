FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# De app zoekt de database relatief (data/rooster.db), schema.sql en config.toml naast de code.
# Door vanuit /srv te draaien komt de database in /srv/data (een volume) en blijft de code in /app.
RUN useradd --create-home app && mkdir -p /srv/data && chown -R app:app /srv
USER app
WORKDIR /srv

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "/app/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
