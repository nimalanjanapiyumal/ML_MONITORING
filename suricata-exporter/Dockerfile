FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter.py .

# Default EVE-JSON path (mounted from Suricata container volume)
ENV EVE_JSON_PATH=/var/log/suricata/eve.json
ENV EXPORTER_PORT=9517
ENV ROLLING_WINDOW_SECONDS=3600

EXPOSE 9517

CMD ["python", "exporter.py"]
