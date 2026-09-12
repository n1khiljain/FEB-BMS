# Deploying the sim on Render

The server is standard library only, so there is nothing to install.

## One time

1. Push this repo to GitHub (`git push`).
2. On [render.com](https://render.com), New -> Web Service -> connect the repo.
3. Render reads `render.yaml` and fills in the settings. If you would rather
   set them by hand:
   - Runtime: Python
   - Build command: `true`
   - Start command: `python -m sim.server`
   - Instance type: Free
4. Deploy. The link looks like `https://feb-bms-sim.onrender.com`.

## Notes

- The server reads `PORT` from the environment, which is how Render tells it
  where to listen, and binds `0.0.0.0` so the platform can reach it.
- Each visitor gets their own state machine, keyed by a cookie. Two people
  clicking at the same time do not share a pack.
- The free tier sleeps after 15 minutes idle, so the first load after a quiet
  spell takes about 30 seconds.
- Locally nothing changes: `python -m sim.server` still serves
  http://127.0.0.1:8000.
