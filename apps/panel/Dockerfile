FROM python:3.12-slim
WORKDIR /app
COPY apps/panel/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY apps/panel/app /app/app
COPY packages /app/packages
COPY sql /app/sql
ENV PYTHONPATH=/app:/app/packages
EXPOSE 8088
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]
