"""Software Engineering Agent: Flask backend. Serves the UI and proxies requests to Groq.
The API key stays on the server and is never sent to the browser."""
import os, time
from collections import defaultdict, deque
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 1_000_000

API_KEY = os.getenv("GROQ_API_KEY", "").strip()
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
MAX_CONTEXT = 120_000
MAX_BRIEF = 4_000

SYSTEM = ("You are a careful software engineering assistant. Analyze only the supplied project context. "
          "Do not claim to execute code or tests, or to have edited files. Flag assumptions, security risks "
          "and missing context. Be specific, cite file paths, and keep answers readable with Markdown headings and fenced code.")
TASKS = {
    "plan": ("Plan", "Produce an implementation plan. Sections: Understanding, Plan (ordered steps with the files each touches), Risks, Open questions."),
    "arch": ("Explain", "Explain the architecture. Sections: Overview, Components (file by file), Data and control flow, Weak spots."),
    "review": ("Review", "Review the code. For each finding give: severity (high/medium/low), file, what is wrong, a suggested fix, and a test to catch it. End with a short summary."),
    "patch": ("Patch", "Propose code changes. For each file show the change as a fenced diff or the full replacement function. Mark all code as a suggestion. List the commands the user should run to verify."),
    "tests": ("Tests", "Write tests. Give a short test plan, then runnable test code in fenced blocks using the project's own language and a common test framework. Cover edge cases and failures."),
}
_hits = defaultdict(deque)
_client = None


def client():
    global _client
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=API_KEY)
    return _client


def limited(ip):
    now, q = time.time(), _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/health")
def health():
    return jsonify(configured=bool(API_KEY), model=MODEL)


@app.post("/api/run")
def run():
    if not API_KEY:
        return jsonify(error="GROQ_API_KEY is not set on the server."), 503
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "?").split(",")[0].strip()
    if limited(ip):
        return jsonify(error="Too many requests. Wait a minute and try again."), 429
    data = request.get_json(silent=True) or {}
    task = data.get("task")
    brief = str(data.get("brief", "")).strip()[:MAX_BRIEF]
    context = str(data.get("context", ""))[:MAX_CONTEXT]
    if task not in TASKS or not brief:
        return jsonify(error="Choose a task and describe what you want done."), 400
    name, instructions = TASKS[task]
    if context:
        body = ("PROJECT FILES (may be incomplete):\n" + context +
                "\n\nRespond with: (1) concise understanding, (2) plan or analysis, (3) proposed file-by-file changes "
                "where relevant, (4) tests to run, (5) assumptions and risks. Clearly mark generated code as a suggestion.")
    else:
        body = "No project files were supplied. Work from the request alone and state your assumptions."
    prompt = f"TASK TYPE: {name}\n{instructions}\n\nUSER REQUEST: {brief}\n\n{body}"
    try:
        r = client().chat.completions.create(
            model=MODEL, temperature=0.2,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
        return jsonify(text=r.choices[0].message.content or "No response returned.")
    except Exception as e:  # surface a short, safe message
        app.logger.exception("LLM request failed")
        return jsonify(error="The model request failed. Check the API key and model name. (" + type(e).__name__ + ")"), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8501")), debug=False)
