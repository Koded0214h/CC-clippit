# Clippit frontend

The creative, static landing page and all of its visual assets live in this folder.

## Run locally

```powershell
python frontend/serve.py
```

Open [http://localhost:5174](http://localhost:5174). The server always serves this
folder, so the command also works when run from the repository root.

## Verify

With the local server running:

```powershell
python -X utf8 -u frontend/scripts/verify.py
```

The verification script checks interactions, mobile layout, motion preferences, and
the major entrance sequences. Screenshots are written to `frontend/tmp/qa/` and are
ignored by Git.

See [DESIGN-NOTES.md](DESIGN-NOTES.md) for the visual direction and implementation
notes.
