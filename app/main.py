from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, text
import os, requests, time

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
OLLAMA_URL = os.getenv("OLLAMA_URL")

engine = create_engine(DATABASE_URL)

# ---------------------------------
# AUTO CREATE / UPDATE TABLES
# ---------------------------------
def migrate():

    sql = """

CREATE TABLE IF NOT EXISTS settings (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    value TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id SERIAL PRIMARY KEY,
    kb_id INT REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    title TEXT,
    content TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS allowed_domains (
    id SERIAL PRIMARY KEY,
    domain TEXT UNIQUE,
    kb_id INT REFERENCES knowledge_bases(id),
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    origin TEXT,
    ip TEXT,
    message TEXT,
    reply TEXT,
    time_taken FLOAT,
    prompt_tokens INT,
    output_tokens INT,
    kb_id INT
);
"""

    with engine.begin() as conn:
        conn.execute(text(sql))

        # Seed default KB
        conn.execute(text("""
        INSERT INTO knowledge_bases(name)
        SELECT 'Default KB'
        WHERE NOT EXISTS (
          SELECT 1 FROM knowledge_bases
        )
        """))

migrate()

# ---------------------------------
# AUTH
# ---------------------------------
def is_admin(request):
    return request.cookies.get("admin") == "1"


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        r = RedirectResponse("/admin", 302)
        r.set_cookie("admin", "1", httponly=True)
        return r
    return RedirectResponse("/", 302)


@app.get("/logout")
def logout():
    r = RedirectResponse("/", 302)
    r.delete_cookie("admin")
    return r


# ---------------------------------
# ADMIN
# ---------------------------------
@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    if not is_admin(request):
        return RedirectResponse("/")
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/admin/kb", response_class=HTMLResponse)
def kb_page(request: Request):
    if not is_admin(request):
        return RedirectResponse("/")

    with engine.begin() as conn:
        rows = conn.execute(text("""
        SELECT id,name FROM knowledge_bases ORDER BY id
        """)).fetchall()

    return templates.TemplateResponse("kb.html", {
        "request": request,
        "rows": rows
    })


@app.post("/admin/kb/add")
def add_kb(request: Request, name: str = Form(...)):
    if not is_admin(request):
        return RedirectResponse("/")

    with engine.begin() as conn:
        conn.execute(text("""
        INSERT INTO knowledge_bases(name)
        VALUES (:n)
        """), {"n": name})

    return RedirectResponse("/admin/kb", 302)


@app.get("/admin/domains", response_class=HTMLResponse)
def domains(request: Request):
    if not is_admin(request):
        return RedirectResponse("/")

    with engine.begin() as conn:
        rows = conn.execute(text("""
        SELECT d.id,d.domain,k.name
        FROM allowed_domains d
        LEFT JOIN knowledge_bases k ON d.kb_id=k.id
        ORDER BY d.id DESC
        """)).fetchall()

        kbs = conn.execute(text("""
        SELECT id,name FROM knowledge_bases
        """)).fetchall()

    return templates.TemplateResponse("domains.html", {
        "request": request,
        "rows": rows,
        "kbs": kbs
    })


@app.post("/admin/domains/add")
def add_domain(request: Request,
               domain: str = Form(...),
               kb_id: int = Form(...)):

    if not is_admin(request):
        return RedirectResponse("/")

    with engine.begin() as conn:
        conn.execute(text("""
        INSERT INTO allowed_domains(domain,kb_id)
        VALUES (:d,:k)
        ON CONFLICT(domain)
        DO UPDATE SET kb_id=:k
        """), {"d": domain, "k": kb_id})

    return RedirectResponse("/admin/domains", 302)


# ---------------------------------
# CHAT API
# ---------------------------------
@app.post("/chat")
async def chat(req: Request):

    body = await req.json()

    msg = body.get("message", "")
    origin = req.headers.get("origin", "")
    ip = req.headers.get("CF-Connecting-IP") or req.client.host

    with engine.begin() as conn:

        row = conn.execute(text("""
        SELECT kb_id
        FROM allowed_domains
        WHERE domain=:d
        AND active=TRUE
        """), {"d": origin}).fetchone()

        if not row:
            raise HTTPException(403, "Domain not allowed")

        kb_id = row[0]

        chunks = conn.execute(text("""
        SELECT title,content
        FROM kb_chunks
        WHERE kb_id=:k
        LIMIT 5
        """), {"k": kb_id}).fetchall()

    context = "\n".join(
        [f"{c[0]}: {c[1]}" for c in chunks]
    )

    prompt = f"""
Use only the knowledge below.

{context}

Question:
{msg}
"""

    start = time.time()

    r = requests.post(
        OLLAMA_URL,
        json={
            "model":"qwen2.5:3b-instruct",
            "prompt":prompt,
            "stream":False,
            "keep_alive":"30m"
        },
        timeout=180
    )

    end = time.time()

    data = r.json()

    reply = data.get("response","")

    duration = round(end-start,3)

    pt = data.get("prompt_eval_count",0)
    ot = data.get("eval_count",0)

    with engine.begin() as conn:
        conn.execute(text("""
        INSERT INTO chat_logs(
            origin,ip,message,reply,
            time_taken,prompt_tokens,
            output_tokens,kb_id
        )
        VALUES(
            :o,:i,:m,:r,:t,:p,:ot,:k
        )
        """), {
            "o": origin,
            "i": ip,
            "m": msg,
            "r": reply,
            "t": duration,
            "p": pt,
            "ot": ot,
            "k": kb_id
        })

    return JSONResponse({
        "reply": reply,
        "time_taken": duration,
        "prompt_tokens": pt,
        "output_tokens": ot,
        "context_used": context
    })