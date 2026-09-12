"""Browser panel for the BMS sim. Run with python -m sim.server."""

import json
import os
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from bms.state_machine import BmsStateMachine
from sim.interactive import TICK_MS, Bus, Panel

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
MAX_SESSIONS = 100

KEYS = [
    ("t", "TS button"),
    ("c", "Charger"),
    ("s", "Shutdown loop"),
    ("r", "Fault reset"),
    ("h", "Heat +5C"),
    ("k", "Cool -5C"),
    ("v", "Cell +50mV"),
    ("b", "Cell -50mV"),
    ("i", "Current +10A"),
    ("j", "Current -10A"),
    ("x", "Unplug sensor"),
    ("n", "Healthy pack"),
]


class Sim:
    def __init__(self):
        self.reset()

    def reset(self):
        self.bms = BmsStateMachine()
        self.bus = Bus()
        self.panel = Panel()
        self.now_ms = 0
        self.readings = None
        self._advance()

    def _advance(self):
        self.bus.update(self.bms.state, self.now_ms)
        self.readings = self.panel.readings(self.bus, self.now_ms)
        self.bms.step(self.readings, self.now_ms)

    def tick(self, count=1):
        for _ in range(count):
            self.now_ms += TICK_MS
            self._advance()

    def key(self, k):
        if not self.panel.apply(k):
            return False
        self.tick()
        return True

    def snapshot(self):
        r = self.readings
        bms = self.bms
        t_hi, t_i = r.max_cell_temp()
        v_hi, v_i = r.max_cell_voltage()
        v_lo, v_lo_i = r.min_cell_voltage()
        return {
            "time_ms": self.now_ms,
            "state": bms.state,
            "bus_voltage": round(r.ts_voltage, 1),
            "pack_voltage": round(r.accumulator_voltage, 1),
            "ratio": round(r.precharge_ratio(), 3),
            "current": round(r.pack_current, 1),
            "hot_temp": t_hi,
            "hot_index": t_i,
            "top_voltage": v_hi,
            "top_index": v_i,
            "low_voltage": v_lo,
            "low_index": v_lo_i,
            "derate": round(bms.discharge_current_limit(r), 1),
            "relays": bms.relay_outputs(),
            "bms_ok": bms.bms_ok(),
            "fault": repr(bms.fault) if bms.fault else None,
            "switches": {
                "ts_button": self.panel.ts_button,
                "charger": self.panel.charger,
                "shutdown_closed": self.panel.shutdown_closed,
            },
            "history": [
                {"time_ms": t, "from": f, "to": to, "note": note}
                for t, f, to, note in bms.history
            ],
        }


SESSIONS = {}
ORDER = []


def get_sim(sid):
    if sid not in SESSIONS:
        SESSIONS[sid] = Sim()
        ORDER.append(sid)
        while len(ORDER) > MAX_SESSIONS:
            SESSIONS.pop(ORDER.pop(0), None)
    return SESSIONS[sid]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def session_id(self):
        raw = self.headers.get("Cookie", "")
        sid = SimpleCookie(raw).get("sid")
        if sid and sid.value in SESSIONS:
            return sid.value, None
        fresh = secrets.token_hex(8)
        return fresh, f"sid={fresh}; Path=/; SameSite=Lax; Max-Age=86400"

    def _send(self, body, kind="application/json", cookie=None):
        raw = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(raw)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        sid, cookie = self.session_id()
        if path == "/":
            get_sim(sid)
            self._send(PAGE, "text/html; charset=utf-8", cookie)
        elif path == "/api/state":
            self._send(json.dumps(get_sim(sid).snapshot()), cookie=cookie)
        else:
            self.send_error(404)

    def do_POST(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        sid, cookie = self.session_id()
        sim = get_sim(sid)
        if url.path == "/api/tick":
            sim.tick(min(int(query.get("n", ["1"])[0]), 200))
        elif url.path == "/api/key":
            sim.key(query.get("k", [""])[0])
        elif url.path == "/api/reset":
            sim.reset()
        else:
            self.send_error(404)
            return
        self._send(json.dumps(sim.snapshot()), cookie=cookie)


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>BMS sim</title><style>
body { font: 14px/1.5 ui-monospace, Menlo, monospace; margin: 2rem;
       background: #111; color: #eee; }
h1 { font-size: 1rem; letter-spacing: .1em; text-transform: uppercase; }
#state { font-size: 2rem; margin: .2rem 0 1rem; }
.INIT, .IDLE { color: #9ad; }
.PRECHARGE { color: #fc6; }
.DRIVE, .CHARGING { color: #7d7; }
.DISCHARGE { color: #fa6; }
.FAULT { color: #f66; }
table { border-collapse: collapse; margin-bottom: 1rem; }
td { padding: .15rem .8rem .15rem 0; }
td.k { color: #888; }
button { font: inherit; background: #222; color: #eee; border: 1px solid #444;
         padding: .35rem .7rem; margin: 0 .3rem .4rem 0; cursor: pointer; }
button:hover { background: #333; }
button.on { background: #275; border-color: #3a7; }
.pill { display: inline-block; padding: .1rem .5rem; margin-right: .4rem;
        border: 1px solid #444; }
.pill.closed { background: #275; border-color: #3a7; }
#history { max-height: 14rem; overflow-y: auto; }
section { margin-bottom: 1.5rem; }
</style></head><body>
<h1>BMS state machine</h1>
<div id="state">-</div>

<section>
  <button onclick="tick(1)">tick 100 ms</button>
  <button onclick="tick(5)">tick 500 ms</button>
  <button onclick="tick(20)">tick 2 s</button>
  <button id="auto" onclick="toggleAuto()">auto off</button>
  <button onclick="post('/api/reset')">restart sim</button>
</section>

<section id="keys"></section>

<section>
  <div id="relays"></div>
</section>

<section>
  <table id="readouts"></table>
</section>

<section>
  <div id="fault"></div>
  <div id="history"></div>
</section>

<script>
const KEYS = __KEYS__;
let timer = null;

function post(url) {
  return fetch(url, {method: 'POST'}).then(r => r.json()).then(render);
}
function tick(n) { return post('/api/tick?n=' + n); }
function key(k) { return post('/api/key?k=' + k); }

function toggleAuto() {
  if (timer) { clearInterval(timer); timer = null; }
  else { timer = setInterval(() => tick(1), 200); }
  document.getElementById('auto').textContent = timer ? 'auto on' : 'auto off';
  document.getElementById('auto').className = timer ? 'on' : '';
}

function render(s) {
  const el = document.getElementById('state');
  el.textContent = s.state;
  el.className = s.state;

  document.getElementById('keys').innerHTML = KEYS.map(([k, label]) => {
    const active = (k === 't' && s.switches.ts_button)
                || (k === 'c' && s.switches.charger)
                || (k === 's' && s.switches.shutdown_closed);
    return `<button class="${active ? 'on' : ''}" onclick="key('${k}')">`
         + `${label} <span style="color:#888">${k}</span></button>`;
  }).join('');

  document.getElementById('relays').innerHTML =
    Object.entries(s.relays).map(([name, on]) =>
      `<span class="pill ${on ? 'closed' : ''}">${name}: `
      + `${on ? 'closed' : 'open'}</span>`).join('')
    + `<span class="pill ${s.bms_ok ? 'closed' : ''}">BMS contact: `
    + `${s.bms_ok ? 'closed' : 'open'}</span>`;

  const rows = [
    ['time', s.time_ms + ' ms'],
    ['bus voltage', s.bus_voltage + ' V  (ratio ' + s.ratio + ')'],
    ['pack voltage', s.pack_voltage + ' V'],
    ['pack current', s.current + ' A'],
    ['discharge limit', s.derate + ' A'],
    ['hottest cell', s.hot_temp + ' C at ' + s.hot_index],
    ['highest cell', s.top_voltage + ' V at ' + s.top_index],
    ['lowest cell', s.low_voltage + ' V at ' + s.low_index],
  ];
  document.getElementById('readouts').innerHTML = rows.map(
    ([k, v]) => `<tr><td class="k">${k}</td><td>${v}</td></tr>`).join('');

  document.getElementById('fault').innerHTML = s.fault
    ? `<div style="color:#f66">${s.fault}</div>` : '';

  document.getElementById('history').innerHTML = s.history.slice().reverse()
    .map(h => `<div>${h.time_ms} ms &nbsp; ${h.from} &rarr; ${h.to}`
            + ` &nbsp; <span style="color:#888">${h.note}</span></div>`)
    .join('');
}

fetch('/api/state').then(r => r.json()).then(render);
</script></body></html>
"""
PAGE = PAGE.replace("__KEYS__", json.dumps(KEYS))


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    shown = "127.0.0.1" if HOST in ("0.0.0.0", "") else HOST
    print(f"BMS sim on http://{shown}:{PORT}  (ctrl-c to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
