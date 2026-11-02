FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY config ./config
COPY wsgi.py README.md ./
RUN useradd --system --uid 10001 --create-home gestortech \
    && mkdir -p /app/instance \
    && chown -R gestortech:gestortech /app
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "python -m flask --app wsgi:app init-db && python -m flask --app wsgi:app run --host=0.0.0.0 --port=8000"]
