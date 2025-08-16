# Dockerfile
FROM python:3.11-slim

# install minimal system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    procps \
    && rm -rf /var/lib/apt/lists/*

ENV APP_DIR=/app
WORKDIR $APP_DIR

# create non-root user
RUN groupadd -r app && useradd --no-log-init -r -g app app \
    && mkdir -p $APP_DIR && chown app:app $APP_DIR

# copy only requirements first for layer caching
COPY requirements.txt $APP_DIR/requirements.txt
RUN pip install --no-cache-dir -r $APP_DIR/requirements.txt

# copy all project files
COPY . $APP_DIR
RUN chown -R app:app $APP_DIR

# entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER app
ENV DB_PATH=/app/data/faq.db
ENV PYTHONPATH=/app
ENV QA_CACHE_TTL=30


HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
  CMD pgrep -f "src/bot.py" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-u", "src/bot.py"]
