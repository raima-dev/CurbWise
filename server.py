import os, json, time, math, sqlite3
import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from google.genai import types

ORS_KEY = os.getenv("ORS_API_KEY")
EL_KEY = os.getenv("ELEVENLABS_API_KEY")
EL_VOICE = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
gem = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()
db = sqlite3.connect("hazards.db", check_same_thread=False)
db.execute("create table if not exists hazards(id integer primary key, type text, severity int, lat real, lon real, note text, expires real)")

# hours a report stays active, by type
HOURS = {"blocked_ramp": 12, "missing_ramp": 720, "construction": 168, "ice_snow": 12,
         "flooding": 24, "broken_surface": 720, "other": 24}

# profile -> ORS wheelchair restrictions
PROFILES = {
    "manual_wheelchair": {"maximum_incline": 6, "maximum_sloped_kerb": 0.03, "smoothness_type": "good"},
    "power_wheelchair": {"maximum_incline": 8, "maximum_sloped_kerb": 0.06, "smoothness_type": "good"},
    "stroller": {"maximum_incline": 8, "maximum_sloped_kerb": 0.06, "smoothness_type": "good"},
}

PROMPT = f"""You review a street-level photo for a mobility route app.
Return JSON only: {{"is_hazard": bool, "type": one of {list(HOURS)}, "severity": 1-5, "note": "one plain sentence"}}.
If the photo does not show a hazard on a walking path, set is_hazard to false."""


def active_hazards():
    rows = db.execute("select id,type,severity,lat,lon,note from hazards where expires > ?", (time.time(),)).fetchall()
    return [dict(id=r[0], type=r[1], severity=r[2], lat=r[3], lon=r[4], note=r[5]) for r in rows]


@app.post("/hazard")
async def add_hazard(photo: UploadFile = File(...), lat: float = Form(...), lon: float = Form(...)):
    data = await photo.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "Photo is over 5 MB. Try a smaller one.")
    resp = gem.models.generate_content(
        model=GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=data, mime_type=photo.content_type or "image/jpeg"), PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    try:
        r = json.loads(resp.text)
    except Exception:
        raise HTTPException(502, "Could not read the photo analysis. Try again.")
    if not r.get("is_hazard") or r.get("type") not in HOURS:
        raise HTTPException(422, "No path hazard found in this photo.")
    # the photo is never stored; only this small record is
    expires = time.time() + HOURS[r["type"]] * 3600
    db.execute("insert into hazards(type,severity,lat,lon,note,expires) values(?,?,?,?,?,?)",
               (r["type"], int(r["severity"]), lat, lon, r["note"], expires))
    db.commit()
    return r


@app.get("/hazards")
def hazards():
    return active_hazards()


class RouteReq(BaseModel):
    start: list[float]  # [lon, lat]
    end: list[float]
    profile: str = "manual_wheelchair"


def ors(profile, body):
    r = httpx.post(f"https://api.openrouteservice.org/v2/directions/{profile}/geojson",
                   headers={"Authorization": ORS_KEY}, json=body, timeout=30)
    if r.status_code != 200:
        return None
    f = r.json()["features"][0]
    return {"line": f["geometry"], "summary": f["properties"]["summary"]}


def near_line(h, line, meters=30):
    """True if hazard h is within `meters` of the route line (list of [lon, lat])."""
    k = 111320  # meters per degree of latitude
    cx = math.cos(math.radians(h["lat"])) * k
    px, py = h["lon"] * cx, h["lat"] * k
    best = 1e9
    for a, b in zip(line, line[1:]):
        ax, ay, bx, by = a[0] * cx, a[1] * k, b[0] * cx, b[1] * k
        dx, dy = bx - ax, by - ay
        t = 0 if (dx == 0 and dy == 0) else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best <= meters


@app.post("/route")
def route(q: RouteReq):
    coords = {"coordinates": [q.start, q.end]}
    restr = {"profile_params": {"restrictions": PROFILES.get(q.profile, PROFILES["manual_wheelchair"])}}
    normal = ors("foot-walking", coords)
    access = ors("wheelchair", {**coords, "options": restr})
    if not access:
        raise HTTPException(404, "No accessible route found between these points.")

    # only hazards within 30 m of the route we would otherwise take
    hits = [h for h in active_hazards()
            if h["severity"] >= 3 and near_line(h, access["line"]["coordinates"])]
    avoided = False
    if hits:
        d = 0.0001  # about 10 m box around each hazard
        polys = [[[[h["lon"] - d, h["lat"] - d], [h["lon"] + d, h["lat"] - d], [h["lon"] + d, h["lat"] + d],
                   [h["lon"] - d, h["lat"] + d], [h["lon"] - d, h["lat"] - d]]] for h in hits]
        rerouted = ors("wheelchair", {**coords, "options": {**restr, "avoid_polygons": {"type": "MultiPolygon", "coordinates": polys}}})
        if rerouted:
            access, avoided = rerouted, True

    mins = round(access["summary"]["duration"] / 60)
    text = f"Route found. {round(access['summary']['distance'])} meters, about {mins} minutes."
    notes = "; ".join(h["note"] for h in hits[:3])
    if hits and avoided:
        text += f" Avoiding {len(hits)} reported hazard{'s' if len(hits) > 1 else ''} on the usual route: {notes}"
    elif hits:
        text += f" Warning: this route passes near a reported hazard and no way around was found: {notes}"
    return {"accessible": access, "normal": normal, "speech": text, "hazards": active_hazards()}


class TTSReq(BaseModel):
    text: str


@app.post("/tts")
def tts(q: TTSReq):
    try:
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE}",
                       headers={"xi-api-key": EL_KEY or ""},
                       json={"text": q.text[:500], "model_id": "eleven_multilingual_v2"}, timeout=20)
    except Exception as e:
        print("ELEVENLABS ERROR:", e)
        raise HTTPException(502, "Voice unavailable")
    if r.status_code != 200:
        print("ELEVENLABS ERROR:", r.status_code, r.text)
        raise HTTPException(502, "Voice unavailable")  # the page falls back to browser speech
    return Response(r.content, media_type="audio/mpeg")


app.mount("/", StaticFiles(directory="static", html=True), name="static")