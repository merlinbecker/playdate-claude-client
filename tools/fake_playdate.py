#!/usr/bin/env python3
"""Simuliert den Playdate-Client vom Rechner aus (nur Standardbibliothek).

Beispiele:
  python3 tools/fake_playdate.py --text "Wie spät ist es?"
  python3 tools/fake_playdate.py --wav aufnahme.wav --drop-after 3
  python3 tools/fake_playdate.py --choose again
"""
import argparse
import json
import time
import urllib.request
import uuid
import wave

CHUNK = 8 * 1024


def call(base, token, method, path, data=None):
    req = urllib.request.Request(base + path, data=data, method=method, headers={"X-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def wav_to_raw8(path, step=5):
    """Beliebige WAV-Datei -> 8 Bit unsigned mono, jedes `step`-te Sample (wie der Playdate)."""
    with wave.open(path, "rb") as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        frames = w.readframes(w.getnframes())
    out = bytearray()
    frame = ch * width
    for i in range(0, len(frames) - frame + 1, frame * step):
        s = frames[i:i + width]
        if width == 1:
            out.append(s[0])
        else:
            v = int.from_bytes(s[-2:], "little", signed=True)
            out.append((v >> 8) + 128)
    return bytes(out), rate // step


def upload(base, token, raw, rate, drop_after=None):
    rec = uuid.uuid4().hex[:12]
    chunks = [raw[i:i + CHUNK] for i in range(0, len(raw), CHUNK)]
    print(f"Aufnahme {rec}: {len(raw)} Bytes, {len(chunks)} Chunks, {rate} Hz")
    for attempt in range(2):
        have = set(call(base, token, "GET", f"/rec/{rec}")["have"])
        for n, c in enumerate(chunks):
            if n in have:
                continue
            if drop_after is not None and attempt == 0 and n == drop_after:
                print(f"  Verbindung 'reißt ab' bei Chunk {n}, setze fort …")
                break
            call(base, token, "PUT", f"/rec/{rec}/chunk/{n}", c)
        else:
            break
    t0 = time.time()
    call(base, token, "POST", f"/rec/{rec}/done", json.dumps({"rate": rate, "chunks": len(chunks)}).encode())
    return t0


def poll(base, token, since, seconds):
    end = time.time() + seconds
    while time.time() < end:
        res = call(base, token, "GET", f"/inbox?since={since}")
        for c in res["cards"]:
            print(f"\n[{c['id']}] {c.get('title')} ({c.get('kind', '')})")
            for e in c.get("elements", []):
                print("   ", {k: v for k, v in e.items()})
            for ch in c.get("choices", []):
                print("    >", ch["label"], f"({ch['value']})")
            if c.get("kind") in ("result", "question", "error"):
                return res["next"]
        since = res["next"]
        time.sleep(1)
    return since


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--token", default="geheim")
    p.add_argument("--text")
    p.add_argument("--wav")
    p.add_argument("--choose")
    p.add_argument("--drop-after", type=int)
    p.add_argument("--wait", type=int, default=120)
    a = p.parse_args()

    since = call(a.base, a.token, "GET", "/inbox?since=0&limit=20")["next"]
    while True:  # bis zum Ende der Inbox vorspulen
        nxt = call(a.base, a.token, "GET", f"/inbox?since={since}&limit=20")["next"]
        if nxt == since:
            break
        since = nxt

    t0 = time.time()
    if a.text:
        call(a.base, a.token, "POST", "/task-text", a.text.encode())
    elif a.wav:
        raw, rate = wav_to_raw8(a.wav)
        t0 = upload(a.base, a.token, raw, rate, a.drop_after)
    elif a.choose:
        call(a.base, a.token, "POST", "/interaction",
             json.dumps({"id": uuid.uuid4().hex[:12], "value": a.choose}).encode())
    poll(a.base, a.token, since, a.wait)
    print(f"\nZeit bis Ergebnis: {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
