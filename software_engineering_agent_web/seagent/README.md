# Software Engineering Agent

Upload a project ZIP, pick a task (plan, explain, review, patch, tests) and get suggestions from a Groq-hosted model. Suggestions only: nothing is executed or edited.

## Run locally
```
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env    # add your GROQ_API_KEY
python app.py           # http://localhost:8501
```

## Deploy on Render (free, public link)
1. Push this folder to a GitHub repo (`.env` is git-ignored).
2. On render.com choose **New > Blueprint** (or **Web Service**) and select the repo. `render.yaml` sets the build and start commands.
3. Add the environment variable `GROQ_API_KEY`.
4. Deploy. Render gives you a public `https://<name>.onrender.com` link.

The API key stays on the server. Requests are rate limited per IP (`RATE_LIMIT_PER_MINUTE`).
