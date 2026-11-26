"""Server für playdate-claude-client.

Start:  PDC_TOKEN=geheim PDC_AGENT=echo uvicorn main:app --host 0.0.0.0 --port 8000
Konfiguration über Umgebungsvariablen, siehe .env.example.
"""
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import uuid
import wave
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request

TOKEN = os.environ.get("PDC_TOKEN", "change-me")
DATA = Path(os.environ.get("PDC_DATA", "./data")).resolve()
AGENT = os.environ.get("PDC_AGENT", "echo")  # echo | claude
AGENT_DIR = os.path.expanduser(os.environ.get("PDC_AGENT_DIR", "~"))
AGENT_PROMPT = os.environ.get("PDC_AGENT_PROMPT", str(Path(__file__).with_name("agent_prompt.example.md")))
STT = os.environ.get("PDC_STT", "faster-whisper")  # faster-whisper | whisper-cli | none
WHISPER_MODEL = os.environ.get("PDC_WHISPER_MODEL", "small")
WHISPER_CLI = os.environ.get("PDC_WHISPER_CLI", "whisper-cli")
LANG = os.environ.get("PDC_LANG", "de")
CHUNK_MAX = 64 * 1024

DATA.mkdir(parents=True, exist_ok=True)
(DATA / "rec").mkdir(exist_ok=True)
(DATA / "assets").mkdir(exist_ok=True)

db = sqlite3.connect(DATA / "pdc.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, kind TEXT, input TEXT, status TEXT, created REAL);
CREATE TABLE IF NOT EXISTS cards (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT, body TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT);
""")
lock = threading.Lock()
wakeup = threading.Event()
app = FastAPI(title="playdate-claude-client")


# ---------- Hilfsfunktionen ----------

def auth(token: str | None):
    if token != TOKEN:
        raise HTTPException(401, "bad token")


def safe_id(rec_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", rec_id):
        raise HTTPException(400, "bad id")
    return rec_id


def q(sql: str, args=()):
    with lock:
        cur = db.execute(sql, args)
        db.commit()
        return cur.fetchall()


def set_status(job: str, status: str):
    q("UPDATE jobs SET status=? WHERE id=?", (status, job))


def emit(job: str, card: dict):
    q("INSERT INTO cards (job, body, ts) VALUES (?,?,?)", (job, json.dumps(card, ensure_ascii=False), time.time()))


def status_card(title: str, line: str, kind: str = "status") -> dict:
    return {"v": 1, "title": title[:30], "kind": kind, "elements": [{"t": "text", "s": line[:120]}]}


def validate_card(c) -> dict | None:
    """Prüft eine Karte grob und kürzt zu lange Inhalte. None = unbrauchbar."""
    if not isinstance(c, dict) or not isinstance(c.get("elements"), list):
        return None
    c["v"] = 1
    c["title"] = str(c.get("title", "Antwort"))[:30]
    c["elements"] = [e for e in c["elements"] if isinstance(e, dict) and "t" in e][:12]
    if "choices" in c:
        c["choices"] = [ch for ch in c["choices"] if isinstance(ch, dict) and "label" in ch][:4]
    return c


def text_to_card(text: str) -> dict:
    lines = [l.strip()[:40] for l in text.strip().splitlines() if l.strip()][:6] or ["(leer)"]
    return {"v": 1, "title": "Antwort", "kind": "result", "elements": [{"t": "text", "s": l} for l in lines]}


# ---------- Transkription ----------

_whisper = None


def raw_to_wav(raw: Path, wav: Path, rate: int, signed: bool = False):
    """8 Bit mono (unsigned oder signed) -> 16 Bit signed WAV."""
    data = raw.read_bytes()
    out = bytearray()
    for b in data:
        v = ((b - 256 if b > 127 else b) if signed else (b - 128)) << 8
        out += v.to_bytes(2, "little", signed=True)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(out))


def transcribe(wav: Path) -> str:
    global _whisper
    if STT == "none":
        return ""
    if STT == "whisper-cli":
        r = subprocess.run([WHISPER_CLI, "-l", LANG, "-nt", "-f", str(wav)], capture_output=True, text=True)
        return r.stdout.strip()
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segments, _ = _whisper.transcribe(str(wav), language=LANG, vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()


# ---------- Agent ----------

def run_agent(prompt: str) -> list[dict]:
    if AGENT == "echo":
        return [{"v": 1, "title": "Echo", "kind": "result",
                 "elements": [{"t": "icon", "tile": 2}, {"t": "text", "s": "Du hast gesagt:"},
                              {"t": "text", "s": f"*{prompt[:80]}*"}],
                 "choices": [{"label": "Nochmal", "value": "again"}, {"label": "Fertig", "value": "done"}]}]

    system = Path(AGENT_PROMPT).read_text(encoding="utf-8") if Path(AGENT_PROMPT).exists() else ""
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if system:
        cmd += ["--append-system-prompt", system]
    session = q("SELECT v FROM state WHERE k='session'")
    if session:
        cmd += ["--resume", session[0]["v"]]
    r = subprocess.run(cmd, cwd=AGENT_DIR, capture_output=True, text=True, timeout=3600)
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        return [status_card("Agent-Fehler", (r.stderr or r.stdout or "keine Ausgabe")[-120:], "error")]
    if out.get("session_id"):
        q("INSERT OR REPLACE INTO state VALUES ('session', ?)", (out["session_id"],))
    text = out.get("result", "")
    cards = []
    for line in text.splitlines():
        if line.startswith("CARD:"):
            try:
                c = validate_card(json.loads(line[5:].strip()))
                if c:
                    cards.append(c)
            except json.JSONDecodeError:
                pass
    return cards or [text_to_card(text)]


def worker():
    q("UPDATE jobs SET status='queued' WHERE status='running'")  # nach Neustart fortsetzen
    while True:
        rows = q("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1")
        if not rows:
            wakeup.wait(5)
            wakeup.clear()
            continue
        job = rows[0]
        set_status(job["id"], "running")
        emit(job["id"], status_card("Arbeite daran", job["input"][:80]))
        try:
            for c in run_agent(job["input"]):
                emit(job["id"], c)
            set_status(job["id"], "done")
        except Exception as e:  # noqa: BLE001
            emit(job["id"], status_card("Fehler", str(e), "error"))
            set_status(job["id"], "error")


def enqueue(job_id: str, kind: str, text: str):
    q("INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?)", (job_id, kind, text, "queued", time.time()))
    wakeup.set()


def finish_recording(rec_id: str, rate: int, signed: bool = False):
    rdir = DATA / "rec" / rec_id
    chunks = sorted(rdir.glob("*.chunk"), key=lambda p: int(p.stem))
    raw = rdir / "audio.raw"
    with raw.open("wb") as f:
        for c in chunks:
            f.write(c.read_bytes())
    wav = rdir / "audio.wav"
    raw_to_wav(raw, wav, rate, signed)
    try:
        text = transcribe(wav)
    except Exception as e:  # noqa: BLE001
        emit(rec_id, status_card("Transkription", str(e), "error"))
        set_status(rec_id, "error")
        return
    if not text:
        emit(rec_id, status_card("Nichts verstanden", "Bitte nochmal sprechen.", "error"))
        set_status(rec_id, "error")
        return
    emit(rec_id, status_card("Verstanden", text))
    enqueue(rec_id, "voice", text)


threading.Thread(target=worker, daemon=True).start()


# ---------- API ----------

@app.get("/health")
def health():
    return {"ok": True, "agent": AGENT, "stt": STT}


@app.put("/rec/{rec_id}/chunk/{n}")
async def put_chunk(rec_id: str, n: int, req: Request, x_token: str | None = Header(None)):
    auth(x_token)
    rec_id = safe_id(rec_id)
    body = await req.body()
    if len(body) > CHUNK_MAX or n < 0 or n > 10000:
        raise HTTPException(413)
    rdir = DATA / "rec" / rec_id
    rdir.mkdir(exist_ok=True)
    (rdir / f"{n}.chunk").write_bytes(body)  # idempotent: gleicher Chunk überschreibt sich selbst
    q("INSERT OR IGNORE INTO jobs VALUES (?,?,?,?,?)", (rec_id, "voice", "", "uploading", time.time()))
    return {"ok": True, "n": n}


@app.get("/rec/{rec_id}")
def get_rec(rec_id: str, x_token: str | None = Header(None)):
    auth(x_token)
    rdir = DATA / "rec" / safe_id(rec_id)
    have = sorted(int(p.stem) for p in rdir.glob("*.chunk")) if rdir.exists() else []
    row = q("SELECT status FROM jobs WHERE id=?", (rec_id,))
    return {"have": have, "status": row[0]["status"] if row else None}


@app.post("/rec/{rec_id}/done")
async def rec_done(rec_id: str, req: Request, x_token: str | None = Header(None)):
    auth(x_token)
    rec_id = safe_id(rec_id)
    meta = json.loads((await req.body()) or b"{}")
    rate = int(meta.get("rate", 8820))
    expected = meta.get("chunks")
    have = len(list((DATA / "rec" / rec_id).glob("*.chunk")))
    if expected is not None and have != int(expected):
        raise HTTPException(409, f"have {have} of {expected}")
    row = q("SELECT status FROM jobs WHERE id=?", (rec_id,))
    if row and row[0]["status"] not in ("uploading", None):
        return {"ok": True, "already": row[0]["status"]}  # doppeltes done ignorieren
    set_status(rec_id, "transcribing")
    threading.Thread(target=finish_recording, args=(rec_id, rate, bool(meta.get("signed"))), daemon=True).start()
    return {"ok": True}


@app.post("/task-text")
async def task_text(req: Request, x_token: str | None = Header(None)):
    """Zum Testen ohne Audio."""
    auth(x_token)
    text = (await req.body()).decode("utf-8").strip()
    job = uuid.uuid4().hex[:12]
    enqueue(job, "text", text)
    return {"job": job}


@app.post("/interaction")
async def interaction(req: Request, x_token: str | None = Header(None)):
    auth(x_token)
    data = json.loads(await req.body())
    job = safe_id(str(data.get("id") or uuid.uuid4().hex[:12]))
    if q("SELECT 1 FROM jobs WHERE id=?", (job,)):
        return {"job": job, "already": True}
    card = data.get("card")
    text = f"Der Nutzer hat auf Karte {card} gewählt: {data.get('value', '')}" if card else \
        f"Der Nutzer hat gewählt: {data.get('value', '')}"
    enqueue(job, "interaction", text)
    return {"job": job}


@app.get("/inbox")
def inbox(since: int = 0, limit: int = 10, x_token: str | None = Header(None)):
    auth(x_token)
    rows = q("SELECT seq, job, body, ts FROM cards WHERE seq>? ORDER BY seq LIMIT ?", (since, min(limit, 20)))
    cards = []
    for r in rows:
        c = json.loads(r["body"])
        c.update({"id": r["seq"], "job": r["job"], "ts": int(r["ts"])})
        cards.append(c)
    return {"cards": cards, "next": rows[-1]["seq"] if rows else since}


@app.get("/assets/{name}")
def asset(name: str, x_token: str | None = Header(None)):
    from fastapi.responses import FileResponse
    auth(x_token)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}(\.[a-z]{2,4})?", name):
        raise HTTPException(400, "bad name")
    p = DATA / "assets" / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)
