import json
import os
import time

from agents import checkpoint
from agents.run_state import RunState


class FakeMeta:
    def __init__(self):
        self.d = {}

    def get_meta(self, k):
        return self.d.get(k)

    def set_meta(self, k, v):
        self.d[k] = v


def _open(m, **kw):
    return RunState.open("t", m.get_meta, m.set_meta, log=lambda *_: None, **kw)


def test_fresh_run_then_resume_skips_finished_steps():
    m = FakeMeta()
    s = _open(m)
    assert not s.resumed
    s.begin({"topic": "x"})
    calls = []
    s.step("research", lambda: calls.append("r") or {"a": 1})
    try:
        s.step("script", lambda: (_ for _ in ()).throw(RuntimeError("429")))
    except RuntimeError:
        pass
    s2 = _open(m)
    assert s2.resumed and s2.ctx["topic"] == "x"
    assert s2.step("research", lambda: calls.append("r2")) == {"a": 1}
    assert s2.step("script", lambda: "ok") == "ok"
    assert calls == ["r"]                      # research ran exactly once


def test_file_step_reruns_when_file_is_gone_and_chain_follows(tmp_path):
    m = FakeMeta()
    s = _open(m)
    s.begin({})
    f1, f2 = tmp_path / "voice.mp3", tmp_path / "video.mp4"
    f1.write_text("a"); f2.write_text("b")
    s.step("voice", lambda: str(f1), validate=os.path.exists)
    s.step("video", lambda: str(f2), validate=os.path.exists, after=["voice"])
    f1.unlink()                                # disk wiped: voice gone, video still there
    s2 = _open(m)
    ran = []
    s2.step("voice", lambda: ran.append("voice") or (f1.write_text("a2") and str(f1)) or str(f1),
            validate=os.path.exists)
    s2.step("video", lambda: ran.append("video") or str(f2), validate=os.path.exists, after=["voice"])
    assert ran == ["voice", "video"]           # video redone because voice was redone


def test_upload_step_never_repeats():
    m = FakeMeta()
    s = _open(m)
    s.begin({})
    n = []
    s.step("upload", lambda: n.append(1) or ["vid", "url"])
    s2 = _open(m)
    vid, url = s2.step("upload", lambda: n.append(2) or ["other", "other"])
    assert (vid, url) == ("vid", "url") and n == [1]


def test_old_state_and_too_many_resumes_are_discarded():
    m = FakeMeta()
    s = _open(m)
    s.begin({"topic": "x"})
    data = json.loads(m.d["run_state:t"])
    data["updated"] = time.time() - 13 * 3600
    m.d["run_state:t"] = json.dumps(data)
    assert not _open(m).resumed                # older than 12h

    s = _open(m)
    s.begin({"topic": "y"})
    for _ in range(3):
        assert _open(m).resumed
    assert not _open(m).resumed                # 4th try: poison run dropped


def test_clear_and_unsaveable_value():
    m = FakeMeta()
    s = _open(m)
    s.begin({})
    assert s.step("obj", lambda: object()) is not None   # returned, just not saved
    assert not s.has("obj")
    s.clear()
    assert not _open(m).resumed


def test_checkpoint_survives_in_db(monkeypatch):
    m = FakeMeta()
    monkeypatch.setattr(checkpoint, "_db", lambda: m)
    checkpoint.save_checkpoint("Topic A", "research", {"x": 1})
    checkpoint.save_checkpoint("Topic A", "script", "text")
    cps = checkpoint.list_checkpoints()
    assert len(cps) == 1 and cps[0]["last_stage"] == "script"
    assert checkpoint.get_stage_data("Topic A", "research") == {"x": 1}
    for _ in range(3):
        checkpoint.note_resume("Topic A")
    assert checkpoint.list_checkpoints() == []           # resumed 3x -> dropped
    checkpoint.save_checkpoint("Topic B", "research", 1)
    checkpoint.clear_checkpoint("Topic B")
    assert checkpoint.list_checkpoints() == []
