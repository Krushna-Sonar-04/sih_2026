# DRISHTI — 3-minute SIH demo script

Problem statement: **SIH 2026 · PS 26152 — Social media narrative intelligence.**
Everything below runs locally in Demo Mode with **no** X, Telegram or LLM
credentials and no internet connection.

## Before you start

```powershell
docker compose up -d db
cd backend; alembic upgrade head; uvicorn app.main:app --reload --port 8000
cd ..; npm run dev
```

Open `http://localhost:8080`. The header must show `DEMO MODE` and
`Backend connected`.

## 0:00 — What DRISHTI is (20 s)

"DRISHTI is a narrative intelligence workspace. It ingests public social media
activity from X and Telegram, stores it with timestamps, and replays how a
narrative actually moved — through one shared clock."

Point at the Dashboard: the tracked Watch **AI Regulation India**, 01–14 Sep 2026,
labelled `DEMO DATASET · SIMULATED SOCIAL ACTIVITY`.

## 0:20 — The Narrative Time-Machine (40 s)

Open **Narrative Time-Machine**. Show the `ONE SHARED CLOCK` strip: sentiment,
rising narrative, influence network, evidence and the aggregate audience profile
are all driven by the single selected timestamp.

Drag the timeline from 01 Sep to 06 Sep: activity rises, sentiment is still
mostly neutral, the network is small.

## 1:00 — Key event (40 s)

Click **Key event** → the clock jumps to **08 Sep 2026 · 14:30**, the narrative
ignition point.

Call out, in order:
- Sentiment shift detected — negative share moves sharply.
- Rising narrative — *Data Privacy* with its velocity figure.
- Influence network expands; a **KOL candidate** appears with the reasons for
  the score (centrality, connectivity, engagement, cross-community reach).
- `At this moment` panel summarises the state in one column.

## 1:40 — Evidence traceability (30 s)

Open any supporting evidence item: platform, account, timestamp, original text,
sentiment, engagement and source reference, plus *why this evidence is relevant*.
"Every number on this screen traces back to a stored record."

## 2:10 — Ask DRISHTI (35 s)

Ask: **"Why did sentiment shift here?"** → a structured answer (Finding,
Evidence, Interpretation, Limitation) with citations that are validated outside
the model against the retrieved records.

Then ask something outside the data, e.g. **"What is the price of gold in Tokyo?"**
→ *"Insufficient evidence in the selected data to answer this question."*
"The assistant cites or refuses — it never improvises."

## 2:45 — Narrative movement and briefing (15 s)

Move the clock forward to 12 Sep: cross-platform movement is described as an
**observed sequence / temporal association**, never as proven causation.

Click **Export briefing** → the DRISHTI Narrative Intelligence Brief, printable
to PDF from the browser, with the Demo/Live mode stated on the page.

## Closing line

"Real FastAPI backend, PostgreSQL storage, NetworkX graph analytics, retrieval
grounded assistant — with honest labelling: connectors show *Not configured*
until real credentials are present, and simulated data is never presented as
live."
