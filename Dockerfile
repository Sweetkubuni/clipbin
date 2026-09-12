# Container image for the clipbin SERVER only.
# (The clipsync watcher writes to the host OS clipboard, so it must run
#  natively on each machine - it is not part of this image.)
FROM python:3.12-slim

WORKDIR /app
COPY clipbin.py .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=2).status==200 else 1)"

# Bind all interfaces so the LAN can reach it; persist bins to the /data volume.
CMD ["python", "clipbin.py", "8000", "--host", "0.0.0.0", "--save", "/data/bins.json"]
