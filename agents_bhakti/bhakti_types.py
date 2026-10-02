# agents_bhakti/bhakti_types.py
"""Structured objects passed between Bhakti pipeline stages (spec section 25)."""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Scene:
    scene_id: int
    purpose: str                      # hook | setup | conflict | divine | resolution | ending
    narration: str
    visual_description: str = ""
    pexels_queries: list = field(default_factory=list)
    camera: str = "slow_zoom_in"
    mood: str = "calm"
    music: str = "soft devotional"
    sfx: list = field(default_factory=list)
    needs_ai: bool = False            # mythological moment with no sensible stock footage
    start: float = 0.0                # filled after voice timing is known
    end: float = 0.0
    emphasis: list = field(default_factory=list)
    clip_path: Optional[str] = None
    clip_id: Optional[str] = None

    @property
    def duration(self):
        return max(self.end - self.start, 0.0)


@dataclass
class VideoJob:
    topic: str = ""
    research: dict = field(default_factory=dict)
    script: str = ""
    retention: dict = field(default_factory=dict)
    scenes: list = field(default_factory=list)       # list[Scene]
    voice_path: Optional[str] = None
    voice_segments: list = field(default_factory=list)  # [{scene_id,start,end,path}]
    music: Optional[dict] = None
    sfx: list = field(default_factory=list)          # [{name,path,at,gain_db}]
    captions_path: Optional[str] = None
    audio_path: Optional[str] = None
    final_video: Optional[str] = None
    qa: dict = field(default_factory=dict)

    def save(self, path="output/bhakti_job.json"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2, default=str)
        return path
