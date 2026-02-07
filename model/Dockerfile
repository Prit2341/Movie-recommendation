FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# This ensures Python looks in /app for the 'database' folder
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire root context so 'database/' and 'model/' are available
COPY . .

# Run the script from the root workdir
CMD ["python", "model/train_model.py"]