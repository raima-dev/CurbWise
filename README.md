# CurbWise

Accessible walking routes that know what's blocked right now. Built at Hack Dearborn 5.

## The problem

Maps tell you the shortest way to walk. They don't tell you a ramp is blocked, a sidewalk is broken, or a crossing is icy. For someone in a wheelchair or pushing a stroller, that can mean getting stuck.

## What it does

- Pick who is travelling: manual wheelchair, power wheelchair, or stroller.
- Tap a start and a destination. The app shows an accessible route (blue) next to the standard walking route (purple dashed).
- Report a hazard: tap its place on the map and take a photo. Gemini turns the photo into a small record (type, severity, short note). Reports of severity 3 or higher make the route avoid that spot until the report expires.
- Directions come out as large text, vibration, and voice.

## How it works

- **Routing:** openrouteservice wheelchair profile on OpenStreetMap data, with slope and kerb limits set per traveller type.
- **Hazards:** Gemini reads each photo. The photo is never stored, only the record, which expires automatically (12 hours for ice or a blocked ramp, up to 30 days for a broken surface).
- **Voice:** ElevenLabs reads directions and hazard warnings aloud.
- **If something fails:** if ElevenLabs is unavailable, browser speech takes over. If the server can't be reached, the last route is reused. Space bar repeats the last instruction.

## Data check

Within 1.5 km of the UM-Dearborn campus, OpenStreetMap has 262 sidewalk segments, 207 tactile paving points, and 56 kerb points. The sidewalk network is mapped, but curb ramp detail is thin. Photo reports are meant to fill that gap.

## Run it (Windows PowerShell)

1. Install the packages:
```
   pip install fastapi uvicorn httpx google-genai python-multipart
```
2. Get free API keys from openrouteservice.org, aistudio.google.com, and elevenlabs.io. Never put keys in the code.
3. Set them in your terminal:
```
   $env:ORS_API_KEY="..."
   $env:GEMINI_API_KEY="..."
   $env:GEMINI_MODEL="gemini-3.8-flash"
   $env:ELEVENLABS_API_KEY="..."
   $env:ELEVENLABS_VOICE_ID="..."
```
   Gemini model names change, so use one your key can access. On a free ElevenLabs account, use a voice saved in your own account, not a library voice.
4. Start the server and open http://127.0.0.1:8000:
```
   uvicorn server:app --reload
```

## Known limits

- Only tested by us, not by wheelchair users or stroller parents.
- Route quality depends on OpenStreetMap coverage and the openrouteservice wheelchair settings.
- A hazard is placed where the user taps, not read from the photo.
- No accounts and little abuse protection beyond a photo size limit.

## Not built yet

Voice commands, sensory-aware routing, confidence labels on each stretch, multilingual voice, exporting confirmed hazards to OpenStreetMap.

## Built with

Python, FastAPI, SQLite, MapLibre GL JS, OpenStreetMap, openrouteservice, Gemini API, ElevenLabs

## License

MIT
