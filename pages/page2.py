# -*- coding: utf-8 -*-
"""
Created on Fri Sep 11 11:53:31 2026

@author: Chris Ellis
"""

import ast
import glob
import html as html_lib
import json
import os
import re
from urllib.parse import quote

import dash
from dash import Dash, html, dcc, dash_table, Input, Output, callback, no_update
import pandas as pd
import requests

dash.register_page(__name__, path='/athlete-search', name='Olympic Athlete Search')

# ---------------------------------------------------------------
# Load & prepare data
# ---------------------------------------------------------------
athletes_df = pd.read_csv("Paris_Olympics_dataset/athletes.csv")
athletes_df["code"] = athletes_df["code"].astype(str)

medals_df = pd.read_csv("Paris_Olympics_dataset/medals.csv")
medals_df["medal_date"] = pd.to_datetime(medals_df["medal_date"], dayfirst=True).dt.strftime("%d %b %Y")

# medals.csv carries a "code" column that is the same athlete ID used in
# athletes.csv and the results files (Ariarne Titmus is 1946150 in both).
# That's a far more reliable join key than the "name" column, whose word
# order differs between files ("Ariarne TITMUS" here vs "TITMUS Ariarne"
# in athletes.csv) — matching on code sidesteps that mismatch entirely.
medals_df["code"] = medals_df["code"].astype(str)



def _to_list(value):
    """athletes.csv stores disciplines/events as stringified Python lists."""
    if pd.isna(value):
        return []
    try:
        parsed = ast.literal_eval(value)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, SyntaxError):
        return []


athletes_df["_disciplines"] = athletes_df["disciplines"].apply(_to_list)
athletes_df["_events"] = athletes_df["events"].apply(_to_list)
athlete_codes = set(athletes_df["code"])

# ---------------------------------------------------------------
# Athlete photos — looked up on demand from Wikidata/Wikimedia Commons,
# not bundled in the dataset. Only the image URL is cached locally
# (never the image file itself); the browser loads the actual photo
# straight from Wikimedia every time it's displayed.
# ---------------------------------------------------------------
PHOTO_CACHE_PATH = os.path.join("Paris_Olympics_dataset", "athlete_photo_cache.json")
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_HEADERS = {
    # Wikimedia asks API clients to identify themselves with a descriptive
    # User-Agent — this is good API etiquette, not a login/credential.
    "User-Agent": "ParisOlympicsAthleteSearch/1.0 (student project; TAFE 20167561)"
}


def _load_photo_cache():
    if os.path.exists(PHOTO_CACHE_PATH):
        try:
            with open(PHOTO_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_photo_cache(cache):
    try:
        os.makedirs(os.path.dirname(PHOTO_CACHE_PATH), exist_ok=True)
        with open(PHOTO_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except OSError:
        pass  # worst case we just re-look-up next time; not fatal


_photo_cache = _load_photo_cache()


def _to_search_name(raw_name):
    """athletes.csv stores names as 'SURNAME Given' (surname in caps).
    Wikidata's own labels are almost always 'Given Surname', so flip the
    order before searching to get better hit rates."""
    tokens = str(raw_name).split()
    surname_tokens = [t for t in tokens if t.isupper()]
    given_tokens = [t for t in tokens if not t.isupper()]
    if surname_tokens and given_tokens:
        surname = " ".join(t.capitalize() for t in surname_tokens)
        given = " ".join(given_tokens)
        return f"{given} {surname}"
    return str(raw_name)


def _lookup_wikidata_photo_url(athlete):
    """Search Wikidata for this athlete and return a hotlinkable Wikimedia
    Commons image URL if a photo (property P18) is found, else None. Best
    effort only — never raises; any problem just means no photo."""
    search_name = _to_search_name(athlete.get("name", ""))
    hints = [
        str(athlete.get("country", "")).lower(),
        str(athlete.get("disciplines", "")).lower(),
    ]

    try:
        search_resp = requests.get(
            WIKIDATA_API,
            params={
                "action": "wbsearchentities", "search": search_name,
                "language": "en", "format": "json", "type": "item", "limit": 5,
            },
            headers=WIKIDATA_HEADERS, timeout=6,
        )
        search_resp.raise_for_status()
        candidates = search_resp.json().get("search", [])
        if not candidates:
            return None

        qids = [c["id"] for c in candidates]
        entities_resp = requests.get(
            WIKIDATA_API,
            params={
                "action": "wbgetentities", "ids": "|".join(qids),
                "format": "json", "props": "claims|descriptions",
            },
            headers=WIKIDATA_HEADERS, timeout=6,
        )
        entities_resp.raise_for_status()
        entities = entities_resp.json().get("entities", {})

        # Prefer whichever candidate (that has a photo) best matches this
        # athlete's country/discipline, to reduce mismatches on common names.
        scored = []
        for c in candidates:
            qid = c["id"]
            claims = entities.get(qid, {}).get("claims", {})
            if "P18" not in claims:
                continue
            desc = (
                entities.get(qid, {}).get("descriptions", {}).get("en", {}).get("value", "")
                or c.get("description", "")
            ).lower()
            score = sum(1 for h in hints if h and h in desc)
            scored.append((score, qid, claims))

        if not scored:
            return None
        scored.sort(key=lambda x: x[0], reverse=True)
        _, _, best_claims = scored[0]
        filename = best_claims["P18"][0]["mainsnak"]["datavalue"]["value"]
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}?width=300"

    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None


def get_athlete_photo_url(athlete):
    """Cache-first lookup. Only the URL string is cached (or None if no
    photo was found), never the image bytes — the browser fetches the
    actual picture from Wikimedia each time it's rendered."""
    code = str(athlete["code"])
    if code in _photo_cache:
        return _photo_cache[code]

    url = _lookup_wikidata_photo_url(athlete)
    _photo_cache[code] = url
    _save_photo_cache(_photo_cache)
    return url


def get_initials(name):
    letters = re.findall(r"[A-Za-z]+", str(name))
    return "".join(t[0].upper() for t in letters[:2]) or "?"


# ---------------------------------------------------------------
# Load every discipline results file from the "results" folder and
# combine them into one lookup table. Different disciplines have
# slightly different columns (rank vs result_WLT vs qualification_mark
# etc.), so we just concat with sort=False and let pandas fill the gaps
# with NaN, then pick out whichever columns are actually populated when
# we display a given athlete's events.
# ---------------------------------------------------------------
RESULTS_DIR = os.path.join("Paris_Olympics_dataset", "results")
_results_files = glob.glob(os.path.join(RESULTS_DIR, "*.csv"))

_frames = []
for _f in _results_files:
    try:
        _df = pd.read_csv(_f)
        _df["participant_code"] = _df["participant_code"].astype(str)
        _frames.append(_df)
    except Exception:
        # Skip any file that doesn't match the expected results format
        continue

if _frames:
    results_df = pd.concat(_frames, ignore_index=True, sort=False)
else:
    results_df = pd.DataFrame(columns=[
        "date", "discipline_name", "event_name", "event_stage", "stage",
        "venue", "participant_code", "participant_name", "rank", "result",
        "result_type", "result_WLT",
    ])

if "date" in results_df.columns:
    results_df["date"] = pd.to_datetime(results_df["date"], errors="coerce")

# Columns worth showing in the events table, in preferred order, if present
_EVENT_DISPLAY_COLS = [
    ("date", "Date"),
    ("discipline_name", "Discipline"),
    ("event_name", "Event"),
    ("event_stage", "Round"),
    ("venue", "Venue"),
    ("rank", "Rank"),
    ("result", "Result"),
    ("result_type", "Result Type"),
    ("result_WLT", "W/L/T"),
]

# athletes.csv spells gender out ("Male"/"Female"); the results files use
# single-letter codes ("M"/"W"). Needed to filter team results down to the
# correct gender's team when a country fields both (e.g. Hockey).
GENDER_TO_RESULTS_CODE = {"Male": "M", "Female": "W"}


# ---------------------------------------------------------------
# Team registry — teams, pairs and relay squads have no row in
# athletes.csv. They appear in medals.csv and the results files under
# their own participant code (e.g. "HOCMTEAM11--NED01"), which never
# equals an individual athlete's code. Anything with a code that isn't an
# athlete's is treated as a team, so it can be searched for, linked to
# from the homepage's medal winners table, and given its own profile.
# ---------------------------------------------------------------
def _txt(value):
    return "" if pd.isna(value) else str(value)


TEAM_REGISTRY = {}

if {"participant_type", "participant_code"} <= set(results_df.columns):
    _team_rows = results_df[
        (results_df["participant_type"] != "Person")
        & (~results_df["participant_code"].isin(athlete_codes))
    ].drop_duplicates("participant_code")
    for _, _r in _team_rows.iterrows():
        TEAM_REGISTRY[_r["participant_code"]] = {
            "name": _txt(_r.get("participant_name")),
            "country": _txt(_r.get("participant_country")),
            "country_code": _txt(_r.get("participant_country_code")),
            "discipline": _txt(_r.get("discipline_name")),
            "event": _txt(_r.get("event_name")),
            "gender": _txt(_r.get("gender")),
        }

# Medal rows are authoritative for medal-winning teams (they also carry
# names like "China 1" or "WANG/SUN"), so they take precedence.
for _, _r in medals_df[~medals_df["code"].isin(athlete_codes)].iterrows():
    TEAM_REGISTRY[_r["code"]] = {
        "name": _txt(_r.get("name")),
        "country": _txt(_r.get("country")),
        "country_code": _txt(_r.get("country_code")),
        "discipline": _txt(_r.get("discipline")),
        "event": _txt(_r.get("event")),
        "gender": _txt(_r.get("gender")),
    }


def _team_label(info):
    detail = ": ".join(p for p in (info["discipline"], info["event"]) if p)
    return f"{info['name'] or info['country']} — {detail} (Team)" if detail else f"{info['name']} (Team)"


# One dropdown holds athletes and teams; the value is always the code.
ATHLETE_SEARCH_OPTIONS = sorted(
    [
        {"label": n, "value": c}
        for n, c in zip(athletes_df["name"], athletes_df["code"])
        if pd.notna(n)
    ]
    + [{"label": _team_label(i), "value": c} for c, i in TEAM_REGISTRY.items()],
    key=lambda o: o["label"].casefold(),
)
VALID_SEARCH_CODES = {o["value"] for o in ATHLETE_SEARCH_OPTIONS}


def find_team_results(athlete):
    """Team-sport results in this dataset are recorded per team, not per
    player — e.g. Hockey.csv has one row per country's match result, not
    one row per athlete on that team — so a team-sport athlete's own
    participant code never appears in results_df. We can still link them
    to their team's actual results using what we do know about them:
    country, discipline(s), and gender."""
    country = athlete.get("country")
    if not country or "participant_type" not in results_df.columns:
        return pd.DataFrame()

    try:
        disciplines = ast.literal_eval(athlete.get("disciplines", "[]"))
    except (ValueError, SyntaxError):
        disciplines = []
    if not disciplines:
        return pd.DataFrame()

    mask = (
        (results_df["participant_type"] == "Team")
        & (results_df["participant_country"] == country)
        & (results_df["discipline_name"].isin(disciplines))
    )

    gender_code = GENDER_TO_RESULTS_CODE.get(athlete.get("gender"))
    if gender_code and "gender" in results_df.columns:
        mask &= (results_df["gender"] == gender_code)

    return results_df[mask].copy()


def find_team_medals(athlete):
    """Team-event medals in medals.csv are recorded once per team (e.g. one
    'Netherlands' row for Men's Hockey gold) under the team's own
    participant code — never an individual player's code — so a team-sport
    medallist's personal `code` won't match these rows directly. A
    team-level row is reliably identifiable because its `name` field is
    just the country's own name (e.g. name='Netherlands',
    country='Netherlands') rather than a person's name; from there we can
    match on country + discipline + gender, same as find_team_results."""
    country = athlete.get("country")
    if not country:
        return pd.DataFrame()

    try:
        disciplines = ast.literal_eval(athlete.get("disciplines", "[]"))
    except (ValueError, SyntaxError):
        disciplines = []
    if not disciplines:
        return pd.DataFrame()

    mask = (
        (medals_df["name"] == medals_df["country"])
        & (medals_df["country"] == country)
        & (medals_df["discipline"].isin(disciplines))
    )

    gender_code = GENDER_TO_RESULTS_CODE.get(athlete.get("gender"))
    if gender_code and "gender" in medals_df.columns:
        mask &= (medals_df["gender"] == gender_code)

    return medals_df[mask].copy()


def clean_bio_text(value):
    """Several free-text bio fields (hero, philosophy, coach, etc.) contain
    raw HTML — paragraph tags like </p><p> and escaped entities like &amp;
    — instead of plain text. Strip the markup and unescape the entities so
    it reads as normal English."""
    if pd.isna(value) or value == "":
        return ""
    text = str(value)
    # Turn paragraph/line breaks into a clear separator before stripping tags
    text = re.sub(r"</p>\s*<p>", "  |  ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "  |  ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)  # drop any remaining tags
    text = html_lib.unescape(text)  # &amp; -> &, &#39; -> ', etc.
    return text.strip()


def parse_list_field(value):
    """athletes.csv stores disciplines/events as stringified Python lists."""
    if pd.isna(value):
        return ""
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return ", ".join(str(v) for v in parsed)
    except (ValueError, SyntaxError):
        pass
    return str(value)


def build_summary_rows(athlete):
    """A short list of (label, value) pairs for the synopsis card."""
    rows = []

    country = athlete.get("country", "")
    gender = athlete.get("gender", "")
    if country or gender:
        rows.append(("Country", country))
        rows.append(("Gender", gender))

    disciplines = parse_list_field(athlete.get("disciplines"))
    if disciplines:
        rows.append(("Discipline(s)", disciplines))

    events = parse_list_field(athlete.get("events"))
    if events:
        rows.append(("Event(s) Entered", events))

    birth_date = athlete.get("birth_date")
    if pd.notna(birth_date) and birth_date:
        try:
            age = 2024 - int(str(birth_date)[:4])
            rows.append(("Born", f"{birth_date} (age {age} at the Games)"))
        except ValueError:
            rows.append(("Born", str(birth_date)))

    birth_place = athlete.get("birth_place")
    birth_country = athlete.get("birth_country")
    if pd.notna(birth_place) and birth_place:
        place = birth_place
        if pd.notna(birth_country) and birth_country and birth_country != country:
            place = f"{birth_place}, {birth_country}"
        rows.append(("Birthplace", place))

    height = athlete.get("height")
    weight = athlete.get("weight")
    if height and float(height) > 0:
        rows.append(("Height", f"{height:.0f} cm"))
    if weight and float(weight) > 0:
        rows.append(("Weight", f"{weight:.0f} kg"))

    occupation = clean_bio_text(athlete.get("occupation"))
    if occupation:
        rows.append(("Occupation", occupation))

    nickname = clean_bio_text(athlete.get("nickname"))
    if nickname:
        rows.append(("Nickname", nickname))

    hobbies = clean_bio_text(athlete.get("hobbies"))
    if hobbies:
        rows.append(("Hobbies", hobbies))

    coach = clean_bio_text(athlete.get("coach"))
    if coach:
        rows.append(("Coach", coach))

    hero = clean_bio_text(athlete.get("hero"))
    if hero:
        rows.append(("Hero", hero))

    philosophy = clean_bio_text(athlete.get("philosophy"))
    if philosophy:
        rows.append(("Philosophy", philosophy))

    return rows


# ---------------------------------------------------------------
# Shared rendering helpers (used by both the athlete and team views)
# ---------------------------------------------------------------
_HEADER_STYLE = {"backgroundColor": "#0055A4", "color": "white", "fontWeight": "bold"}


def _note(text):
    return html.P(
        text,
        style={
            "textAlign": "center", "color": "#555", "fontStyle": "italic",
            "marginBottom": "12px",
        },
    )


def _medals_table(medal_rows):
    return dash_table.DataTable(
        columns=[
            {"name": "Discipline", "id": "discipline"},
            {"name": "Event", "id": "event"},
            {"name": "Medal", "id": "medal_type"},
            {"name": "Date", "id": "medal_date"},
        ],
        data=medal_rows[["discipline", "event", "medal_type", "medal_date"]]
            .sort_values("medal_date").to_dict("records"),
        style_table={"overflowX": "auto", "width": "90%", "margin": "0 auto"},
        style_cell={"textAlign": "center", "padding": "6px"},
        style_header=_HEADER_STYLE,
        style_data_conditional=[
            {"if": {"filter_query": '{medal_type} = "Gold Medal"'}, "backgroundColor": "#FFF3CD"},
            {"if": {"filter_query": '{medal_type} = "Silver Medal"'}, "backgroundColor": "#F1F1F1"},
            {"if": {"filter_query": '{medal_type} = "Bronze Medal"'}, "backgroundColor": "#FBE4D5"},
        ],
    )


def _events_table(event_rows):
    event_rows = event_rows.copy()
    available_cols = [
        (col, label) for col, label in _EVENT_DISPLAY_COLS
        if col in event_rows.columns and event_rows[col].notna().any()
    ]
    if "date" in event_rows.columns:
        event_rows = event_rows.sort_values("date")
    display_df = event_rows[[c for c, _ in available_cols]].copy()
    if "date" in display_df.columns:
        display_df["date"] = display_df["date"].dt.strftime("%d %b %Y")

    return dash_table.DataTable(
        columns=[{"name": label, "id": col} for col, label in available_cols],
        data=display_df.to_dict("records"),
        style_table={"overflowX": "auto", "width": "95%", "margin": "0 auto"},
        style_cell={"textAlign": "center", "padding": "6px"},
        style_header=_HEADER_STYLE,
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f5f5f5"},
        ],
    )


def _summary_card(title, rows, side_element):
    """Title + label/value table on the left, photo or badge on the right.
    CSS Grid (not flex) keeps the right-hand column fixed however long the
    text gets."""
    info_column = html.Div(
        [
            html.H3(title, style={"textAlign": "left", "marginBottom": "15px"}),
            html.Table(
                [
                    html.Tr([
                        html.Td(label, style={
                            "fontWeight": "bold", "padding": "6px 12px 6px 0",
                            "verticalAlign": "top", "whiteSpace": "nowrap",
                            "textAlign": "left", "color": "#0055A4",
                        }),
                        html.Td(str(value), style={
                            "padding": "6px 12px", "textAlign": "left",
                            "wordBreak": "break-word",
                        }),
                    ])
                    for label, value in rows
                ],
                style={"margin": "0", "width": "100%", "tableLayout": "fixed"},
            ),
        ],
        style={"minWidth": "0"},
    )
    return html.Div(
        [info_column, side_element],
        style={
            "display": "grid", "gridTemplateColumns": "1fr 220px",
            "alignItems": "center", "gap": "30px",
            "border": "1px solid #ddd", "borderRadius": "8px",
            "padding": "20px", "backgroundColor": "#f9f9f9",
        },
    )


def find_team_roster(info):
    """Athletes who belong to a team: same country and discipline, narrowed
    to those registered for the team's exact event when athletes.csv lists
    it (which is precise for team sports and relays). Returns the roster
    and whether that event-level match was used."""
    pool = athletes_df[
        (athletes_df["country"] == info["country"])
        & athletes_df["_disciplines"].apply(lambda d: info["discipline"] in d)
    ]
    by_event = pool[pool["_events"].apply(lambda e: info["event"] in e)]
    if not by_event.empty:
        return by_event, True

    gender_label = {"M": "Male", "W": "Female"}.get(info.get("gender"))
    if gender_label:
        pool = pool[pool["gender"] == gender_label]
    return pool, False


def build_team_profile(code):
    """Summary, medals, results and roster for a team/pair/relay squad."""
    info = TEAM_REGISTRY[code]
    name = info["name"] or info["country"]
    roster_df, event_level = find_team_roster(info)

    badge = html.Div(
        [
            html.Div(
                info["country_code"] or get_initials(name),
                style={"fontSize": "56px", "fontWeight": "bold", "lineHeight": "1"},
            ),
            html.Div("TEAM", style={"fontSize": "14px", "letterSpacing": "4px", "marginTop": "10px"}),
        ],
        style={
            "width": "220px", "height": "260px", "borderRadius": "8px",
            "backgroundColor": "#0055A4", "color": "white", "display": "flex",
            "flexDirection": "column", "alignItems": "center",
            "justifyContent": "center",
        },
    )
    rows = [
        ("Type", "Team"),
        ("Country", info["country"]),
        ("Discipline", info["discipline"]),
        ("Event", info["event"]),
        ("Registered athletes", len(roster_df)),
    ]
    summary_card = _summary_card(name, [(l, v) for l, v in rows if v != ""], badge)

    team_medals = medals_df[medals_df["code"] == code]
    if team_medals.empty:
        medals_content = html.P(
            f"{name} did not win a medal at the Paris 2024 Olympics.",
            style={"textAlign": "center", "color": "#555"},
        )
    else:
        medals_content = _medals_table(team_medals)

    team_events = results_df[results_df["participant_code"] == code]
    if team_events.empty:
        events_content = html.P(
            "No event-by-event results were found for this team in the results data.",
            style={"textAlign": "center", "color": "#555"},
        )
    else:
        events_content = _events_table(team_events)

    if roster_df.empty:
        roster_content = html.Div([
            html.H3("Team Members", style={"textAlign": "center"}),
            html.P(
                "No registered athletes could be matched to this team.",
                style={"textAlign": "center", "color": "#555"},
            ),
        ])
    else:
        intro = (
            "Athletes registered for this event. "
            if event_level else
            "Athletes registered in this discipline — an event-level roster isn't "
            "available for this team, so this may include athletes who didn't "
            "compete in this event. "
        )
        roster_records = [
            {
                "id": r["code"], "name": r["name"], "gender": r["gender"],
                "events": ", ".join(r["_events"]),
            }
            for _, r in roster_df.sort_values("name").iterrows()
        ]
        roster_content = html.Div([
            html.H3(f"Team Members ({len(roster_records)})", style={"textAlign": "center"}),
            _note(intro + "Click a team member to open their profile."),
            dash_table.DataTable(
                id="team-roster-table",
                columns=[
                    {"name": "Name", "id": "name"},
                    {"name": "Gender", "id": "gender"},
                    {"name": "Events Entered", "id": "events"},
                ],
                data=roster_records,
                page_size=15,
                style_table={"overflowX": "auto", "width": "95%", "margin": "0 auto"},
                style_cell={"textAlign": "center", "padding": "6px"},
                style_header=_HEADER_STYLE,
                style_data={"cursor": "pointer"},
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#f5f5f5"},
                ],
            ),
        ])

    return summary_card, medals_content, events_content, roster_content


# ---------------------------------------------------------------
# Page layout — a function so Dash Pages can hand it the URL's query
# string. Clicking a row in the homepage's medal winners table navigates
# here as /athlete-search?code=<athlete or team code>, which pre-selects
# that entry in the dropdown; the callback below then fills in the page.
# ---------------------------------------------------------------
def layout(code=None, **other_query_strings):
    initial_value = str(code) if code is not None and str(code) in VALID_SEARCH_CODES else None

    return html.Div(
        [
            html.H2("Olympic Athlete Search", style={"textAlign": "center"}),
            html.P(
                "Search for an athlete or team to see a brief synopsis, whether "
                "they won a medal at the Paris 2024 Olympics, and every event "
                "they competed in during the Games.",
                style={"textAlign": "center", "color": "#555", "fontStyle": "italic"},
            ),

            html.Div(
                dcc.Dropdown(
                    id="athlete-search-dropdown",
                    options=ATHLETE_SEARCH_OPTIONS,
                    value=initial_value,
                    placeholder="Search for an athlete or team...",
                    searchable=True,
                    clearable=True,
                ),
                style={"width": "450px", "margin": "0 auto 30px auto"},
            ),

            html.Div(id="athlete-summary-card"),

            html.Div(
                [
                    html.H3("Medals at Paris 2024", style={"textAlign": "center"}),
                    html.Div(id="athlete-medals-content"),
                ],
                style={"marginTop": "20px", "marginBottom": "30px"},
            ),

            html.Div(
                [
                    html.H3("Events Competed In", style={"textAlign": "center"}),
                    html.Div(id="athlete-events-content"),
                ],
                style={"marginBottom": "30px"},
            ),

            # Only filled in for teams (heading and table are built in the callback)
            html.Div(id="team-roster-content", style={"marginBottom": "30px"}),
        ],
        style={"maxWidth": "1000px", "margin": "0 auto", "padding": "0 20px"},
    )


# ---------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------
@callback(
    Output("athlete-summary-card", "children"),
    Output("athlete-medals-content", "children"),
    Output("athlete-events-content", "children"),
    Output("team-roster-content", "children"),
    Input("athlete-search-dropdown", "value"),
)
def update_athlete_details(selected_code):
    if not selected_code:
        placeholder = html.P(
            "Select an athlete or team above to get started.",
            style={"textAlign": "center", "color": "#999"},
        )
        return placeholder, "", "", ""

    selected_code = str(selected_code)

    # A code that isn't an athlete's but is a known team/pair/relay squad
    if selected_code in TEAM_REGISTRY and selected_code not in athlete_codes:
        return build_team_profile(selected_code)

    athlete_rows = athletes_df[athletes_df["code"] == selected_code]
    if athlete_rows.empty:
        return html.P("Athlete not found.", style={"textAlign": "center"}), "", "", ""
    athlete = athlete_rows.iloc[0]
    selected_name = athlete["name"]

    # ---- Synopsis card ----
    photo_url = get_athlete_photo_url(athlete)
    if photo_url:
        photo_el = html.Div(
            [
                html.Img(
                    src=photo_url,
                    style={
                        "width": "220px", "height": "260px", "objectFit": "cover",
                        "objectPosition": "center 15%",
                        "borderRadius": "8px", "border": "3px solid #0055A4",
                        "display": "block",
                    },
                ),
                html.A(
                    "Photo via Wikimedia Commons", href=photo_url, target="_blank",
                    style={"display": "block", "textAlign": "center", "fontSize": "11px",
                           "color": "#999", "marginTop": "6px"},
                ),
            ],
            style={},
        )
    else:
        photo_el = html.Div(
            get_initials(selected_name),
            style={
                "width": "220px", "height": "260px", "borderRadius": "8px",
                "backgroundColor": "#0055A4", "color": "white", "fontSize": "48px",
                "fontWeight": "bold", "display": "flex", "alignItems": "center",
                "justifyContent": "center",
            },
        )

    summary_card = _summary_card(selected_name, build_summary_rows(athlete), photo_el)

    # ---- Medals ----
    athlete_medals = medals_df[medals_df["code"] == athlete["code"]]

    # No individual-code match — typical for team sports, where medals are
    # recorded once per team rather than once per player. Fall back to the
    # athlete's own team's medal(s) instead of showing "no medal" outright.
    showing_team_medals = False
    if athlete_medals.empty:
        athlete_medals = find_team_medals(athlete)
        showing_team_medals = not athlete_medals.empty

    if athlete_medals.empty:
        medals_content = html.P(
            f"{selected_name} did not win a medal at the Paris 2024 Olympics.",
            style={"textAlign": "center", "color": "#555"},
        )
    elif showing_team_medals:
        medals_content = html.Div([
            _note(
                f"{selected_name} isn't listed individually for team medals in "
                f"this dataset — showing {athlete['country']}'s own medal(s) in "
                f"this discipline instead."
            ),
            _medals_table(athlete_medals),
        ])
    else:
        medals_content = _medals_table(athlete_medals)

    # ---- Events competed in ----
    athlete_events = results_df[results_df["participant_code"] == str(athlete["code"])].copy()

    # No individual rows found — typical for team sports, where results are
    # only recorded at the team level. Fall back to the athlete's team's
    # own results instead of showing nothing.
    showing_team_results = False
    if athlete_events.empty:
        athlete_events = find_team_results(athlete)
        showing_team_results = not athlete_events.empty

    if athlete_events.empty:
        events_content = html.P(
            "No event-by-event results were found for this athlete in the "
            "results data.",
            style={"textAlign": "center", "color": "#555"},
        )
    elif showing_team_results:
        events_content = html.Div([
            _note(
                f"{selected_name} doesn't have individual-level results in this "
                f"dataset — {parse_list_field(athlete.get('disciplines'))} results "
                f"are only tracked at the team level here. Showing "
                f"{athlete['country']}'s own results in this discipline instead."
            ),
            _events_table(athlete_events),
        ])
    else:
        events_content = _events_table(athlete_events)

    return summary_card, medals_content, events_content, ""


# Clicking a row in a team's roster opens that athlete's own profile by
# pointing the dropdown at their code, which re-runs the callback above.
@callback(
    Output("athlete-search-dropdown", "value"),
    Input("team-roster-table", "active_cell"),
    prevent_initial_call=True,
)
def open_team_member_profile(active_cell):
    if not active_cell or active_cell.get("row_id") is None:
        return no_update
    return str(active_cell["row_id"])
