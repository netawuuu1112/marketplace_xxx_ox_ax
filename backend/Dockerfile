FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY integrations/ru-marketplace-mcp/packages /app/integrations/ru-marketplace-mcp/packages
RUN pip install --no-cache-dir -e /app/integrations/ru-marketplace-mcp/packages/*
COPY backend /app/backend
ENV PYTHONPATH=/app/backend
WORKDIR /app/backend
CMD ["python", "web.py"]
