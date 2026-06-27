FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY anomaly_detector.py /app/anomaly_detector.py
COPY unsw_nb15_pipeline.py /app/unsw_nb15_pipeline.py
COPY train_unsw_nb15.py /app/train_unsw_nb15.py
COPY config.yaml /app/config.yaml

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
