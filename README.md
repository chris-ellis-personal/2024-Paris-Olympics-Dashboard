# Paris 2024 Olympics Dashboard _(2024-Paris-Olympics-Dashboard)_

![Olympic rings banner](assets/olympic_flag.png)

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Dash](https://img.shields.io/badge/built%20with-Dash%203-informational.svg?style=flat-square)](https://dash.plotly.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg?style=flat-square)](LICENSE)

An interactive Dash dashboard for exploring Paris 2024 Olympic medals, the torch relay route and athlete profiles.

The dashboard is a multi-page [Dash](https://dash.plotly.com/) web app with three pages, all driven by CSV files you
supply locally:

- **Homepage** – a world medal map, a sortable medal leaderboard and a per-country list of medal winners.
- **Olympic Torch Path** – the torch relay route drawn on a world map, stop by stop.
- **Olympic Athlete Search** – a profile page for any athlete or team: biography, photo, medals and every event
  competed in.

The pages are linked together: choosing a country on the map highlights it in the leaderboard, and clicking a medal
winner opens their profile (or their team's profile for team events).

## Table of Contents

- [Security](#security)
- [Background](#background)
- [Install](#install)
  - [Dependencies](#dependencies)
  - [Updating](#updating)
- [Usage](#usage)
  - [CLI](#cli)
- [Features](#features)
- [Project Structure](#project-structure)
- [Data](#data)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [API](#api)
- [Thanks](#thanks)
- [Contributing](#contributing)
- [License](#license)

## Security

- **No credentials or secrets** are used or stored. The only outbound network calls are anonymous, read-only requests
  to the [Wikidata API](https://www.wikidata.org/w/api.php) (made from the server, to find athlete photos) and image
  loads from Wikimedia Commons (made by the visitor's browser).
- **Use the built-in development server for local use only.** `app.run(debug=True)` exposes Flask's interactive
  debugger, which allows arbitrary code execution; never enable it on a publicly reachable machine. For a real
  deployment, serve `app.server` with a production WSGI server such as [Gunicorn](https://gunicorn.org/) or
  [Waitress](https://docs.pylonsproject.org/projects/waitress/).
- **Dataset text is treated as untrusted.** Some free-text biography fields in `athletes.csv` contain raw HTML; the
  athlete page strips the markup before display rather than rendering it.
- The app writes one local file, `Paris_Olympics_dataset/athlete_photo_cache.json`. It contains only athlete IDs and
  public image URLs.
- Dependencies are pinned in `requirements.txt`. Review and update them periodically, for example with
  [`pip-audit`](https://pypi.org/project/pip-audit/).

## Background

This project was built as a coursework project for a _Building Data Dashboards_ unit. The aim was to turn the public
Paris 2024 results data into something a visitor can explore without writing any code, and to make the pieces of the
data (countries, athletes, teams, medals and events) navigable from one another.

**Abstract dependencies**

- [Dash](https://dash.plotly.com/) (with its _Pages_ feature) and
  [Dash Bootstrap Components](https://www.dash-bootstrap-components.com/) for the web app.
- [Plotly](https://plotly.com/python/) for the maps, [pandas](https://pandas.pydata.org/) for data handling.
- [Wikidata](https://www.wikidata.org/) and [Wikimedia Commons](https://commons.wikimedia.org/) for athlete photos,
  which the datasets do not contain.

**Design decisions worth knowing about**

- **Athletes, medals and results are joined on the athlete `code`, never on names.** The same person is written
  `TITMUS Ariarne` in one file and `Ariarne TITMUS` in another.
- **Team sports are recorded per team, not per player.** Team medals and results use a team code that no individual
  athlete shares, so the app resolves teams separately and links players to their team by country, discipline and
  event.
- **Torch-route coordinates are generated offline** from a hard-coded lookup table, because live geocoding was blocked
  on the network the project was developed on. See [`build_torch_coordinates.py`](build_torch_coordinates.py).
- **Only the URL of each athlete photo is cached**, never the image itself; the browser loads the image from
  Wikimedia each time.

For a file-by-file description of the code, see [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md).

## Install

```sh
git clone https://github.com/chris-ellis-personal/2024-Paris-Olympics-Dashboard.git
cd 2024-Paris-Olympics-Dashboard

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

### Dependencies

- **Python 3.11 or newer.** The pinned versions in `requirements.txt` (for example `numpy 2.3`) require it. On
  Python 3.10, install the packages the app actually imports instead:

  ```sh
  pip install dash dash-bootstrap-components plotly pandas requests
  ```

- **The dataset is not included and must be added manually.** Place the CSV files in a `Paris_Olympics_dataset/`
  folder in the project root, as described in [Data](#data). The official data is published as the
  [Paris 2024 Olympic Summer Games dataset on Kaggle](https://www.kaggle.com/datasets/piterfm/paris-2024-olympic-summer-games).
- **Image assets** (the header flags and the three sidebar tab icons) must be present in `assets/`; see
  [Project Structure](#project-structure).
- An internet connection is needed only for athlete photos. Everything else works offline.

`requirements.txt` also lists packages the app does not import (for example `torch`, `matplotlib`, `networkx` and
`dash_ag_grid`); they come from the course template and can be removed.

### Updating

```sh
git pull
pip install -r requirements.txt
python build_torch_coordinates.py   # only if torch_route.csv has changed
```

## Usage

Run both commands from the **project root** – every data path in the code is relative to it.

```sh
# 1. One-off: add coordinates to the torch route (needed by the Olympic Torch Path page)
python build_torch_coordinates.py

# 2. Start the dashboard
python app.py
```

Then open <http://127.0.0.1:8050> in a browser. The dashboard always opens on the homepage, including after a
refresh.

For development, enable Dash's hot reloading by changing the last line of `app.py` to `app.run(debug=True)`. See
[Security](#security) before doing this on anything other than your own machine.

### CLI

There are two entry points. Neither takes command-line arguments.

| Command | Purpose |
| --- | --- |
| `python app.py` | Starts the web app on port 8050. Stop it with `Ctrl+C`. |
| `python build_torch_coordinates.py` | Reads `torch_route.csv` and writes `torch_route_geocoded.csv`. Prints a warning listing any city that has no coordinates (that stop is then left off the map). |

## Features

**Navigation**

- A left-hand sidebar of icon tabs sits beneath the header. The tab for the current page is black; the others are grey.
- Loading or refreshing the browser always returns to the homepage.

**Homepage**

- A world choropleth map shaded by each country's total medals, with gold/silver/bronze/total on hover.
- A sortable, filterable, paginated medal leaderboard.
- Select a country by clicking its row, clicking it on the map, or searching in the dropdown. The selected country is
  outlined in red on the map and boxed in red in the leaderboard, and the leaderboard jumps to the page it is on.
- Click the selected country again to de-select it.
- A table of that country's individual medal winners. Click any row to open that athlete's profile, or the team's
  profile for team events.

**Olympic Torch Path**

- The relay route as a numbered sequence of stops joined by a line, with the city, stage title and date on hover.

**Olympic Athlete Search**

- Search more than 11,000 athletes and several hundred teams from one dropdown.
- **Athlete profile:** a synopsis (country, disciplines, birth details, height, weight, occupation, hobbies, coach,
  hero, philosophy – whichever exist), a photo from Wikimedia Commons (or an initials placeholder), any medals won, and
  every event and round competed in.
- **Team profile** (teams, pairs, relay squads): the team's medals, its match-by-match results, and a clickable list of
  team members that opens each member's own profile.
- For team-sport athletes, the profile falls back to their team's medals and results, with a note saying so.

## Project Structure

```text
.
├── app.py                        # Entry point: header, sidebar tabs, page container
├── build_torch_coordinates.py    # One-off script: geocodes the torch route
├── requirements.txt
├── PROJECT_STRUCTURE.md          # File-by-file code description
├── README.md
├── LICENSE                       # MIT License
├── assets/
│   ├── olympic_flag.png
│   ├── paris_2024_olympic_flag.png
│   ├── home_tab_image.png
│   ├── athlete_tab_image.png
│   └── olympic_torch_tab_image.png
├── pages/
│   ├── homepage.py               # /                 medal map, leaderboard, winners
│   ├── page1.py                  # /torch-path       torch relay map
│   └── page2.py                  # /athlete-search   athlete and team profiles
└── Paris_Olympics_dataset/       # You supply this folder (see Data)
    ├── athletes.csv
    ├── medals.csv
    ├── medals_total.csv
    ├── torch_route.csv
    ├── torch_route_geocoded.csv  # Generated by build_torch_coordinates.py
    ├── athlete_photo_cache.json  # Generated at runtime
    └── results/
        └── <Discipline>.csv      # One file per discipline
```

## Data

| File | Used by | Contents |
| --- | --- | --- |
| `athletes.csv` | Athlete Search | One row per athlete: `code`, `name`, `gender`, `country`, `disciplines`, `events`, birth and biography fields. |
| `medals.csv` | Homepage, Athlete Search | One row per medal: `code`, `name`, `country`, `discipline`, `event`, `medal_type`, `medal_date` (day first). |
| `medals_total.csv` | Homepage | One row per country: `country`, `country_code`, `Gold Medal`, `Silver Medal`, `Bronze Medal`, `Total`. |
| `torch_route.csv` | `build_torch_coordinates.py` | The relay route: `city`, `date_start`, `stage_number`, `title`. |
| `torch_route_geocoded.csv` | Olympic Torch Path | `torch_route.csv` plus `latitude` and `longitude`. **Generated** – do not edit by hand. |
| `results/*.csv` | Athlete Search | Event results; every file in the folder is loaded. Includes `participant_code`, `participant_type`, `discipline_name`, `event_name`, `event_stage` and result columns, which vary by discipline. |
| `athlete_photo_cache.json` | Athlete Search | **Generated** – maps athlete code to a photo URL, or `null` if none was found. Safe to delete. |

The `code` column is the key that ties `athletes.csv`, `medals.csv` and `results/*.csv` together. Individual athletes
have numeric codes (for example `1946150`); teams have text codes (for example `HOCMTEAM11--NED01`).

## Configuration

There are no environment variables or config files. Settings are constants in the code:

| Setting | File | Default | Effect |
| --- | --- | --- | --- |
| `LEADERS_PAGE_SIZE` | `pages/homepage.py` | `15` | Rows per page in the medal leaderboard. |
| `PAGE_ICONS` | `app.py` | per route | Maps each page's route to its tab icon in `assets/`. |
| `NAV_FONT_FAMILY` | `app.py` | Helvetica Neue, Arial | Font used by the header title and sidebar tabs. |
| `CITY_COORDS` | `build_torch_coordinates.py` | hard-coded | Latitude/longitude for each torch relay stop. Add an entry if the script warns about a missing city. |
| `PHOTO_CACHE_PATH` | `pages/page2.py` | `Paris_Olympics_dataset/athlete_photo_cache.json` | Where photo URLs are cached. |
| `app.run(...)` | `app.py` | defaults | Pass `debug=True`, `port=...` or `host=...` here. |

## Troubleshooting

**`Exception: modules ['__main__', 'pages.pageN'] have duplicate paths`**
A file in `pages/` was run directly (for example with an editor's "Run file" button) in the same console session, so
Dash registered it twice. Restart the kernel or console, then run only `app.py`.

**`FileNotFoundError` for a file in `Paris_Olympics_dataset/`**
Run the command from the project root, and check the file is present. For `torch_route_geocoded.csv`, run
`python build_torch_coordinates.py` first.

**A torch stop is missing from the map**
Its city has no entry in `CITY_COORDS`. The build script prints the names it could not find.

**Athlete photos never appear**
A failed lookup (for example, while offline) is cached as "no photo" and not retried. Delete
`Paris_Olympics_dataset/athlete_photo_cache.json` to try again.

**Refreshing the page sends me back to the homepage**
This is intentional: a full page load always starts on the homepage.

## Known Limitations

- **Team members are matched approximately.** Team-sport athletes are linked to their team by country, discipline and
  event. For relays this can include squad members who did not swim that particular heat or final, and where an
  event-level match is unavailable the roster falls back to the whole country and discipline (the page says when).
- **Mixed teams and doubles pairs are not shown on an individual athlete's own profile.** Their medals appear on the
  team's profile, but an athlete's page only recognises teams named after their country.
- **Athlete photos are a best-effort match** on name, country and discipline against Wikidata. Some athletes have no
  photo, and a common name could occasionally match the wrong person.
- **Results appear only for the disciplines whose files are in `results/`.**
- **No deep links survive a reload.** Profile links work when followed from inside the app, but opening one directly,
  or refreshing it, returns to the homepage.
- There is no automated test suite.

## API

The app has no public API. Its interface is a set of routes, one of which accepts a query parameter.

| Route | Page | Query parameters |
| --- | --- | --- |
| `/` | Homepage | – |
| `/torch-path` | Olympic Torch Path | – |
| `/athlete-search` | Olympic Athlete Search | `code` (optional) |

**`code`** pre-selects an athlete or a team on the athlete search page. It is the athlete's numeric `code` or a team's
text code, exactly as used in the data files. An unknown value is ignored.

```text
/athlete-search?code=1946150
/athlete-search?code=HOCMTEAM11--NED01
```

The homepage's medal winners table builds these links when a row is clicked. As noted under
[Known Limitations](#known-limitations), they only work when followed from within the running app.

## Thanks

- [Plotly Dash](https://dash.plotly.com/) and [Dash Bootstrap Components](https://www.dash-bootstrap-components.com/)
  (the SPACELAB theme is from [Bootswatch](https://bootswatch.com/)).
- The publishers of the
  [Paris 2024 Olympic Summer Games dataset](https://www.kaggle.com/datasets/piterfm/paris-2024-olympic-summer-games).
- [Wikidata](https://www.wikidata.org/) and the [Wikimedia Commons](https://commons.wikimedia.org/) photographers.
  Each photo carries its own licence; the athlete page links every photo back to its Commons source.
- [Standard Readme](https://github.com/RichardLitt/standard-readme) for the structure of this document.

This is an unofficial, educational project. It is not affiliated with or endorsed by the International Olympic
Committee or Paris 2024. Olympic names, emblems and images belong to their respective owners.

## Contributing

Questions, bug reports and suggestions are welcome – please [open an issue](https://github.com/chris-ellis-personal/2024-Paris-Olympics-Dashboard/issues).

Pull requests are welcome. Before opening one:

- Run the app from a clean environment and check the pages you changed.
- Make sure every changed file compiles: `python -m py_compile app.py pages/*.py build_torch_coordinates.py`.
- Follow [PEP 8](https://peps.python.org/pep-0008/) and the existing style, where comments explain _why_ rather than
  _what_.
- Update this README and [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) if you change behaviour, files or data
  requirements.
- Do not commit the dataset or `athlete_photo_cache.json`.

Please be respectful and follow the
[Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) code of conduct.

## License

[MIT](LICENSE) © 2026 Chris Ellis

The MIT License covers the source code in this repository only. The Paris 2024 dataset, the Olympic emblems and
images, and the athlete photos loaded from Wikimedia Commons are not part of this repository and remain subject to
their own owners' terms and licences (see [Thanks](#thanks)).
