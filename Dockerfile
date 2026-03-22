FROM node:18-slim AS frontend
WORKDIR /app/sajt
COPY sajt/package.json sajt/package-lock.json ./
RUN npm ci
COPY sajt/ ./
ENV DISABLE_ESLINT_PLUGIN=true
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY servis/ ./servis/
COPY --from=frontend /app/sajt/build ./sajt/build
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "servis.app:app", "--host", "0.0.0.0", "--port", "8000"]
