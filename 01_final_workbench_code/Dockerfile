FROM python:3.11-slim

WORKDIR /kom

COPY app ./app
COPY tools ./tools
COPY PACKAGE_MANIFEST.json README_START_HERE.md README_GITHUB_AND_WEB_DEPLOY.md package_integrity.py ./

ENV KOM_PUBLIC_DEMO=1
ENV KOM_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

EXPOSE 8027

CMD ["python", "app/backend/server.py"]
