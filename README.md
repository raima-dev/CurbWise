# CurbWise

Accessible walking routes with live hazard reports. Open source (MIT).

Stack: OpenStreetMap + openrouteservice (routing), MapLibre (map), Gemini (photo analysis), ElevenLabs (voice), FastAPI + SQLite.

## Run it

```
pip install fastapi uvicorn httpx google-genai python-multipart
export ORS_API_KEY=...          # openrouteservice.org (free)
export GEMINI_API_KEY=...       # aistudio.google.com
export ELEVENLABS_API_KEY=...   # elevenlabs.io
uvicorn server:app --reload
```

Open http://localhost:8000. Photo capture and the camera need HTTPS on a phone, so use a tunnel or your deployed host for phone testing.

## How it works

1. Tap the map for a start and a destination, pick who is travelling, press Find route.
2. The blue route uses the wheelchair profile with slope and kerb limits and avoids active hazards. The purple dashed route is the standard walking route.
3. Report a hazard: tap its place on the map and take a photo. Gemini turns it into a small record with an expiry time. The photo itself is never stored.
4. Guidance goes out as large text, vibration, and voice. If ElevenLabs fails, browser speech takes over. If the server is down, the last route is reused.

## Not built yet

Voice commands, sensory-aware routing, confidence labels, multilingual voice, OpenStreetMap export.
