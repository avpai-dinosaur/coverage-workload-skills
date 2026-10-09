FROM python:3.12-slim
COPY collector.py /opt/collector/collector.py
# Reducers (log-based properties) go here. This setup leaves it empty.
COPY reducers/ /opt/reducers/
ENV PYTHONUNBUFFERED=1
CMD ["python3", "/opt/collector/collector.py"]
