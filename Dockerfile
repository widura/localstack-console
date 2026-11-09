FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py resources.py workflows.py advanced.py snapshots.py ./
COPY static ./static
ENV BIND_HOST=0.0.0.0
USER 65534:65534
EXPOSE 8080
CMD ["python", "app.py"]

