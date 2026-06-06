FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace/apps/api

WORKDIR /workspace/apps/api

COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /tmp/requirements.txt

COPY apps/api /workspace/apps/api

RUN chmod +x /workspace/apps/api/scripts/start-render.sh

EXPOSE 8000

CMD ["/bin/sh", "./scripts/start-render.sh"]
