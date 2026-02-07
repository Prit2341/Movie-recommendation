FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy backend, api, database, model loader (pkls mounted later)
COPY backend backend
COPY api api
COPY database database
COPY model model

EXPOSE 5000

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "5000"]
