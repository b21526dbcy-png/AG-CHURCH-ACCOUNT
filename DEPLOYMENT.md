# Deployment Instructions

## Docker

Build and run locally:

```bash
docker build -t account-web .
docker run -p 5000:5000 -e SECRET_KEY="your-secret-key" account-web
```

Then open `http://127.0.0.1:5000`.

## Heroku / Cloud

The `Procfile` is configured for Heroku-style deployment:

```bash
heroku create
git push heroku main
heroku config:set SECRET_KEY="your-secret-key"
```

## Environment Variables

- `SECRET_KEY` - required for Flask session signing.
- `FLASK_DEBUG` - should be `0` or omitted in production.

## GitHub + Docker Hub Deployment

If you push this project to GitHub, you can use the GitHub Actions workflow in `.github/workflows/docker-publish.yml`.

1. Create a GitHub repository and push your project.
2. Add repository secrets:
   - `DOCKERHUB_USERNAME`
   - `DOCKERHUB_TOKEN`
3. Push to `main` and GitHub Actions will build and publish the Docker image to Docker Hub.

## Vercel Deployment

This repo is now ready for Vercel Docker deployment.

1. Install the Vercel CLI if you want:
   - `npm install -g vercel`
2. Log in to Vercel:
   - `vercel login`
3. Deploy from the project root:
   - `vercel --prod`

Vercel will use `vercel.json` and the `Dockerfile` to build your app.

## Notes

- The app uses `waitress` as the production WSGI server.
- The Flask development server is not suitable for production.
- Ensure `database.db` is stored persistently or replaced with a managed database for production use.
