FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace/apps/api

WORKDIR /workspace/apps/api

# Optional Scrapling provider — off by default. Enable with:
#   docker build --build-arg INSTALL_SCRAPLING=true [--build-arg INSTALL_SCRAPLING_BROWSERS=true]
ARG INSTALL_SCRAPLING=false
ARG INSTALL_SCRAPLING_BROWSERS=false

COPY apps/api/requirements.txt /tmp/requirements.txt
COPY apps/api/requirements-scrapling.txt /tmp/requirements-scrapling.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /tmp/requirements.txt \
 && if [ "$INSTALL_SCRAPLING" = "true" ]; then \
        pip install --no-cache-dir -r /tmp/requirements-scrapling.txt \
        && if [ "$INSTALL_SCRAPLING_BROWSERS" = "true" ]; then scrapling install; fi; \
    fi

COPY apps/api /workspace/apps/api

RUN chmod +x /workspace/apps/api/scripts/start-render.sh

EXPOSE 8000

CMD ["/bin/sh", "./scripts/start-render.sh"]
