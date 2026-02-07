FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY model/ model/
COPY database/ database/

CMD ["python", "model/train_model.py"]
