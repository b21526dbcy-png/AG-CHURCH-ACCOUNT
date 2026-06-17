FROM python:3.14-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
ENV SECRET_KEY=change_me

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p static/uploads

ENV PORT 5000
EXPOSE 5000
CMD ["sh", "-lc", "waitress-serve --listen=0.0.0.0:${PORT} app:app"]
