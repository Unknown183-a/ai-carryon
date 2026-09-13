# Phase 00 — Repo & Skeleton

**Status:** Complete
**Depends on:** None

## Goal

Set up the repository shape so any phase can be picked up with zero setup: source layout, config-driven experiments, docs scaffold.

## Tasks

- [x] `src/` package layout (data, models, federated, unlearning, baselines, evaluation, utils)
- [x] `configs/*.yaml` for experiment parameters
- [x] `requirements.txt`
- [x] `.gitignore`
- [x] `tests/` scaffold
- [x] `docs/` scaffold (architecture, decisions, diagrams, api, deployment)

## Definition of done

Repo clones and `pip install -r requirements.txt` succeeds; all modules import without error.

## Handoff notes

Structure mirrors the ai-carryon-saas phased layout: BUILD_GUIDE.md as the single living plan, STATUS.md as source of truth, one PHASE.md per phase, work-reports/ for session logs.
