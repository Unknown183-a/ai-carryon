# agents/run_state.py
"""
Resumable pipeline runs, stored in the database (not on local disk).

Why the database: GitHub Actions and Cloud Run Jobs start with an empty disk
on every run, so file checkpoints disappear. The DB `meta` table (get_meta /
set_meta, which every pipeline already has) survives between runs.

How a pipeline uses it:

    state = RunState.open("hindi", db.get_meta, db.set_meta)
    if state.resumed:
        topic = state.ctx["topic"]            # same topic as the stopped run
    else:
        topic = pick_topic()
        state.begin({"topic": topic})         # remember choices that are random

    research = state.step("research", lambda: research(topic))
    voice    = state.step("voice", lambda: generate_voice(script),
                          validate=os.path.exists, after=["images"])
    ...
    state.clear()                              # only after full success

Rules:
  * step() returns the saved value if the step finished in an earlier run,
    otherwise runs it, saves the result straight away, and returns it.
  * A step that makes a FILE passes validate=... so a wiped disk makes it run
    again instead of returning a path that no longer exists.
  * after=[...] : if any listed step had to run again in this run, this step
    runs again too (e.g. voice file is new, so captions and video must be new).
  * A state older than ttl_hours, or resumed more than max_resumes times, is
    thrown away so one bad topic can never block the channel forever.
  * Values that cannot be saved as JSON are still returned, just not saved.
"""
import json
import time
import uuid

DEFAULT_TTL_HOURS = 12
DEFAULT_MAX_RESUMES = 3


class RunState:
    def __init__(self, channel, meta_get, meta_set, data=None, resumed=False,
                 ttl_hours=DEFAULT_TTL_HOURS, max_resumes=DEFAULT_MAX_RESUMES, log=print):
        self.channel = channel
        self._get, self._set = meta_get, meta_set
        self.key = f"run_state:{channel}"
        self.ttl_hours, self.max_resumes, self._log = ttl_hours, max_resumes, log
        self.data = data or {}
        self.resumed = resumed
        self._recomputed = set()

    # ── open / begin / clear ─────────────────────────────────────────────
    @classmethod
    def open(cls, channel, meta_get, meta_set, ttl_hours=DEFAULT_TTL_HOURS,
             max_resumes=DEFAULT_MAX_RESUMES, log=print):
        self = cls(channel, meta_get, meta_set, ttl_hours=ttl_hours,
                   max_resumes=max_resumes, log=log)
        try:
            raw = meta_get(self.key)
            data = json.loads(raw) if raw else None
        except Exception as e:
            log(f"[run_state:{channel}] could not read saved state ({e}) — starting fresh")
            data = None
        if not isinstance(data, dict) or "ctx" not in data:
            return self
        age_h = (time.time() - data.get("updated", 0)) / 3600.0
        if age_h > ttl_hours:
            log(f"[run_state:{channel}] saved run is {age_h:.1f}h old (limit {ttl_hours}h) — discarding it")
            self.clear()
            return self
        if data.get("resumes", 0) >= max_resumes:
            log(f"[run_state:{channel}] saved run already resumed {data['resumes']}x without finishing — discarding it")
            self.clear()
            return self
        data["resumes"] = data.get("resumes", 0) + 1
        self.data, self.resumed = data, True
        self._save()
        done = ", ".join(self.data.get("steps", {})) or "nothing yet"
        log(f"[run_state:{channel}] RESUMING run {data.get('id')} (attempt {data['resumes'] + 1}) — finished steps: {done}")
        return self

    def begin(self, ctx):
        """Start a new run and remember the random choices (topic, category, clip id...)."""
        self.data = {"id": uuid.uuid4().hex[:8], "started": time.time(), "updated": time.time(),
                     "resumes": 0, "ctx": dict(ctx or {}), "steps": {}}
        self.resumed = False
        self._save()

    @property
    def ctx(self):
        return self.data.get("ctx", {})

    def update_ctx(self, **kw):
        self.data.setdefault("ctx", {}).update(kw)
        self._save()

    def clear(self):
        self.data, self.resumed = {}, False
        try:
            self._set(self.key, "")
        except Exception as e:
            self._log(f"[run_state:{self.channel}] could not clear saved state: {e}")

    # ── steps ────────────────────────────────────────────────────────────
    def has(self, name):
        return name in self.data.get("steps", {})

    def get(self, name, default=None):
        return self.data.get("steps", {}).get(name, default)

    def set(self, name, value):
        """Save a value without running anything (for state you built yourself)."""
        if not self.data:
            return value
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            self._log(f"[run_state:{self.channel}] step '{name}' is not JSON-saveable — kept in memory only")
            return value
        self.data.setdefault("steps", {})[name] = value
        self._save()
        return value

    def step(self, name, fn, validate=None, after=()):
        if not self.data:                      # begin() was never called: just run
            return fn()
        stale = any(a in self._recomputed for a in after)
        if self.has(name) and not stale:
            value = self.get(name)
            ok = True
            if validate is not None:
                try:
                    ok = bool(validate(value))
                except Exception:
                    ok = False
            if ok:
                self._log(f"[run_state:{self.channel}] step '{name}' already done — skipping")
                return value
            self._log(f"[run_state:{self.channel}] step '{name}' output is gone (files wiped?) — running it again")
        value = fn()
        self._recomputed.add(name)
        self.data.get("steps", {}).pop(name, None)
        self.set(name, value)
        return value

    def forget(self, *names):
        for n in names:
            self.data.get("steps", {}).pop(n, None)
        self._save()

    def _save(self):
        if not self.data:
            return
        self.data["updated"] = time.time()
        try:
            self._set(self.key, json.dumps(self.data))
        except Exception as e:
            self._log(f"[run_state:{self.channel}] could not save state: {e}")
