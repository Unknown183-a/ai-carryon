from cricapi_client import cricapi_get


def find_match_with_moment():
    """
    Finds a live OR recently finished Indian match, and extracts the
    single best 'moment' (standout batting, bowling, milestone, or
    dramatic finish) to build a video around.
    Returns (match_summary_dict, moment_dict) or (None, None) if nothing found.
    """
    candidates = []
    for offset in (0, 25, 50, 75):
        current = cricapi_get("currentMatches", {"offset": offset})
        if not current or current.get("status") != "success":
            continue
        page = current.get("data", [])
        if not page:
            break
        for m in page:
            teams = m.get("teams", [])
            if not any("india" in t.lower() for t in teams):
                continue
            if m.get("matchType") not in ("t20", "odi", "test"):
                continue
            if m.get("matchStarted"):
                candidates.append(m)

    if not candidates:
        return None, None

    # Prefer live matches first, then most recently finished
    candidates.sort(key=lambda m: (not (m.get("matchStarted") and not m.get("matchEnded")), m.get("dateTimeGMT", "")))

    for match in candidates:
        scorecard = cricapi_get("match_scorecard", {"id": match["id"]})
        if not scorecard or scorecard.get("status") != "success":
            continue

        moment = extract_best_moment(scorecard["data"])
        if moment:
            return scorecard["data"], moment

    return None, None


def extract_best_moment(match_data):
    """
    Scans scorecard data and returns the single most compelling moment.
    Priority: century > 5-wicket haul > close finish > fifty > big wicket haul > highest score.
    """
    moments = []

    for inning in match_data.get("scorecard", []):
        for bat in inning.get("batting", []):
            r = bat.get("r", 0)
            name = bat.get("batsman", {}).get("name", "")
            dismissal_text = bat.get("dismissal-text", "")
            sr = bat.get("sr", 0)

            if r >= 100:
                moments.append({
                    "type": "century",
                    "priority": 5,
                    "player": name,
                    "detail": f"{name} scored a century ({r} runs off {bat.get('b')} balls, SR {sr})",
                })
            elif r >= 50:
                moments.append({
                    "type": "fifty",
                    "priority": 3,
                    "player": name,
                    "detail": f"{name} scored a fifty ({r} runs off {bat.get('b')} balls, SR {sr})",
                })

            if "retd hurt" in dismissal_text.lower():
                moments.append({
                    "type": "retired_hurt",
                    "priority": 4,
                    "player": name,
                    "detail": f"{name} retired hurt on {r} runs — dramatic injury moment",
                })
            if r == 0 and "run" not in dismissal_text.lower():
                moments.append({
                    "type": "duck",
                    "priority": 2,
                    "player": name,
                    "detail": f"{name} out for a duck ({dismissal_text})",
                })

        for bowl in inning.get("bowling", []):
            w = bowl.get("w", 0)
            name = bowl.get("bowler", {}).get("name", "")
            eco = bowl.get("eco", 0)

            if w >= 5:
                moments.append({
                    "type": "five_wicket_haul",
                    "priority": 5,
                    "player": name,
                    "detail": f"{name} took a 5-wicket haul ({w} wickets, economy {eco})",
                })
            elif w >= 3:
                moments.append({
                    "type": "three_wicket_haul",
                    "priority": 3,
                    "player": name,
                    "detail": f"{name} took {w} wickets at an economy of {eco}",
                })

    # Close finish check
    status = match_data.get("status", "")
    if any(x in status.lower() for x in ["1 run", "2 run", "1 wkt", "2 wkt", "last ball", "super over"]):
        moments.append({
            "type": "close_finish",
            "priority": 5,
            "player": None,
            "detail": f"Nail-biting finish: {status}",
        })

    if not moments:
        return None

    moments.sort(key=lambda x: x["priority"], reverse=True)
    return moments[0]



def find_top_matches(limit=5):
    """
    Returns a list of match dicts (id, name, status, moment) for the dashboard
    dropdown — searches live + finished Indian matches across pages, ranks by
    moment quality, and returns the top N.
    """
    candidates = []
    for offset in (0, 25, 50, 75):
        current = cricapi_get("currentMatches", {"offset": offset})
        if not current or current.get("status") != "success":
            continue
        page = current.get("data", [])
        if not page:
            break
        for m in page:
            teams = m.get("teams", [])
            if not any("india" in t.lower() for t in teams):
                continue
            if m.get("matchType") not in ("t20", "odi", "test"):
                continue
            if m.get("matchStarted"):
                candidates.append(m)

    results = []
    for match in candidates:
        scorecard = cricapi_get("match_scorecard", {"id": match["id"]})
        if not scorecard or scorecard.get("status") != "success":
            continue
        moment = extract_best_moment(scorecard["data"])
        is_live = match.get("matchStarted") and not match.get("matchEnded")
        results.append({
            "id": match["id"],
            "name": match.get("name", ""),
            "status": match.get("status", "") + (" 🔴 LIVE" if is_live else ""),
            "moment": moment,
            "moment_priority": moment["priority"] if moment else 0,
            "is_live": is_live,
        })

    # Rank: live matches first, then by moment priority
    results.sort(key=lambda r: (not r["is_live"], -r["moment_priority"]))
    return results[:limit]

if __name__ == "__main__":
    match, moment = find_match_with_moment()
    if moment:
        print("Match:", match.get("name"))
        print("Best moment:", moment["detail"])
    else:
        print("No suitable match/moment found right now.")
