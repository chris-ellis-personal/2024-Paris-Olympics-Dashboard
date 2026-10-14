import dash
from dash import html, dcc, dash_table, Input, Output, State, callback, no_update, ctx, Patch
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from urllib.parse import quote

dash.register_page(__name__, path='/', name='Paris 2024 Olympics Homepage')

# ---------------------------------------------------------------
# Load & prepare data
# ---------------------------------------------------------------
medals_df = pd.read_csv("Paris_Olympics_dataset/medals_total.csv")
winners_df = pd.read_csv("Paris_Olympics_dataset/medals.csv")
winners_df["medal_date"] = pd.to_datetime(winners_df["medal_date"]).dt.strftime("%d %b %Y")
# Athlete IDs are numeric but team IDs are text (e.g. "HOCMTEAM11--NED01"); keep
# them all as strings so they can be passed to the athlete search page.
winners_df["code"] = winners_df["code"].astype(str)

leaders_df = (
    medals_df
    .sort_values("Total", ascending=False)
    .reset_index(drop=True)
)
leaders_df.insert(0, "Rank", leaders_df.index + 1)

leaders_df = leaders_df[
    ["Rank", "country", "Gold Medal", "Silver Medal", "Bronze Medal", "Total"]
]

country_options = sorted(winners_df["country"].dropna().unique())

# Lookup used to resolve a clicked map location (ISO-3 code) back to the
# full country name, since the choropleth's clickData only reliably
# provides the country_code used for `locations`.
country_code_to_name = dict(zip(medals_df["country_code"], medals_df["country"]))
# ...and the reverse, used to target the selection-highlight trace below by
# country_code once a country's been selected by name (table row/dropdown).
country_name_to_code = {name: code for code, name in country_code_to_name.items()}

# ---------------------------------------------------------------
# Choropleth map component
# ---------------------------------------------------------------
medals_map_fig = px.choropleth(
    medals_df,
    locations="country_code",       # ISO-3 country codes
    color="Total",                  # column used for color scale
    hover_name="country",           # tooltip title
    hover_data={
        "country_code": False,
        "Gold Medal": True,
        "Silver Medal": True,
        "Bronze Medal": True,
        "Total": True,
    },
    color_continuous_scale=px.colors.sequential.Plasma,
    range_color=(0, medals_df["Total"].max()),
    labels={"Total": "Total Medals"},
    title="Total Medals Won by Country",
)

medals_map_fig.update_layout(
    geo=dict(
        showframe=False,
        showcoastlines=False,
        projection_type="natural earth",
    ),
    margin=dict(l=0, r=0, t=50, b=0),
    coloraxis_colorbar=dict(title="Total<br>Medals"),
)

# Selection-highlight overlay: a second choropleth trace, drawn on the same
# map, with a fully transparent fill and a thick red border. It starts with
# no locations (nothing selected) and is updated in-place — via a Patch()
# in highlight_selected_country_on_map below — to outline whichever single
# country is currently selected, or cleared back to nothing on de-select.
medals_map_fig.add_trace(go.Choropleth(
    locations=[],
    z=[],
    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
    showscale=False,
    marker_line_color="#FF0000",
    marker_line_width=4,
    hoverinfo="skip",
))

medals_choropleth_layout = html.Div(
    [
        html.H2("Olympic Medals — World Map", className="page-title"),
        dcc.Graph(id="medals-choropleth", figure=medals_map_fig, className="graph"),
    ]
)

# ---------------------------------------------------------------
# Medal leaders table component
# ---------------------------------------------------------------
# Base row styling for the leaders table (zebra striping only). The
# "currently selected country" highlight is no longer done via DataTable's
# built-in {"state": "active"} rule — that's tied to active_cell, which is a
# transient click-focus prop that doesn't reliably clear when the selection
# changes via a different route (e.g. clicking the map, or a different
# table row), leaving a stale red cell behind. Instead,
# highlight_selected_country_in_table (below) rebuilds this list from the
# actual selected country every time it changes, so the highlight can never
# drift out of sync with the real selection.
LEADERS_TABLE_BASE_STYLE = [
    {"if": {"row_index": "odd"}, "backgroundColor": "#f5f5f5"},
]

# Shared between the table definition and the callback that works out which
# page a selected country sits on, so the two can never disagree.
LEADERS_PAGE_SIZE = 15

medal_leaders_table = html.Div(
    [
        html.H2("Medal Leaders", className="page-title page-title--spaced"),
        html.P(
            "Click a country row below, click a country on the map above, "
            "or use the search box further down, to see its individual "
            "medal winners.",
            className="note",
        ),
        html.Div(dash_table.DataTable(
            id="medal-leaders-table",
            columns=[{"name": col, "id": col} for col in leaders_df.columns],
            # "id" is not a displayed column; it lets active_cell report which
            # country was clicked even after the table has been sorted or
            # filtered (a plain row index is "affected by sorting").
            data=[{**row, "id": row["country"]} for row in leaders_df.to_dict("records")],
            sort_action="native",
            filter_action="native",
            page_action="native",
            page_current=0,
            page_size=LEADERS_PAGE_SIZE,
            # Width, header colours, cell padding and alignment come from
            # assets/olympics_theme.css (.table-wrap). Only the data-driven
            # row rules below stay in Python.
            style_data_conditional=list(LEADERS_TABLE_BASE_STYLE),
            # active_cell is used purely as an input signal — to detect
            # which row was clicked (see select_country_from_table_or_map)
            # — not for any visual purpose. Earlier attempts to override
            # DataTable's own built-in "active cell" styling (its internal
            # focus overlay) via custom CSS kept fighting the component's
            # own specificity in ways that caused more visual breakage than
            # they fixed (a hidden value, then a broken border). The actual
            # selection is shown entirely by the red row border below,
            # driven by the real selection state rather than active_cell,
            # so DataTable's own default active-cell affordance is left
            # alone here rather than fought.
        ), className="table-wrap table-wrap--clickable"),
    ],
    className="section",
)

# ---------------------------------------------------------------
# Country search + individual medal winners table
# ---------------------------------------------------------------
country_winners_section = html.Div(
    [
        html.H2("Medal Winners by Country", className="page-title page-title--spaced"),

        html.Div(
            dcc.Dropdown(
                id="country-search-dropdown",
                options=[{"label": c, "value": c} for c in country_options],
                value="Australia",
                placeholder="Search for a country...",
                searchable=True,
                clearable=True,
            ),
            className="dropdown-wrap",
        ),

        html.H3(
            id="country-winners-title",
            children="Select a country to view its medal winners",
            className="section-subtitle section-subtitle--muted",
        ),
        html.P(
            "Click any row to open that athlete's profile (or the team's profile "
            "for team events) on the Olympic Athlete Search page.",
            className="note",
        ),

        html.Div(dash_table.DataTable(
            id="country-winners-table",
            columns=[
                {"name": "Name", "id": "name"},
                {"name": "Gender", "id": "gender"},
                {"name": "Discipline", "id": "discipline"},
                {"name": "Event", "id": "event"},
                {"name": "Medal", "id": "medal_type"},
                {"name": "Medal Date", "id": "medal_date"},
            ],
            data=[],
            sort_action="native",
            filter_action="native",
            page_size=15,
            # Width, header, padding, alignment and the pointer cursor come
            # from assets/olympics_theme.css (.table-wrap--clickable).
            style_data_conditional=[
                {
                    "if": {"row_index": "odd"},
                    "backgroundColor": "#f5f5f5",
                }
            ],
        ), className="table-wrap table-wrap--clickable"),
    ],
    className="section",
)

# ---------------------------------------------------------------
# Page layout: map + leaders table + country winners lookup
# (global header lives in app.py)
# ---------------------------------------------------------------
layout = html.Div([
    medals_choropleth_layout,
    medal_leaders_table,
    country_winners_section,
])


# ---------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------

# Clicking a country row in the medal leaders table, OR clicking a country
# on the choropleth map, selects it in the search dropdown (which in turn
# drives the winners table below). Clicking the *already-selected* country
# again — via either the table or the map — de-selects it instead, which
# clears the search dropdown and (via update_country_winners_table below)
# resets the winners table back to its "select a country" placeholder.
@callback(
    Output("country-search-dropdown", "value"),
    Output("medal-leaders-table", "active_cell"),
    Input("medal-leaders-table", "active_cell"),
    Input("medals-choropleth", "clickData"),
    State("medal-leaders-table", "data"),
    State("country-search-dropdown", "value"),
    prevent_initial_call=True,
)
def select_country_from_table_or_map(active_cell, click_data, table_data, current_country):
    triggered_id = ctx.triggered_id

    if triggered_id == "medal-leaders-table":
        if active_cell is None:
            return no_update, no_update
        clicked_country = active_cell.get("row_id") or table_data[active_cell["row"]]["country"]
        new_value = None if clicked_country == current_country else clicked_country
        # Clear active_cell after reading it so clicking the same row again
        # is always registered as a fresh click (DataTable won't otherwise
        # fire a callback for a click that leaves active_cell unchanged).
        return new_value, None

    if triggered_id == "medals-choropleth":
        if not click_data:
            return no_update, no_update
        clicked_point = click_data["points"][0]
        country_code = clicked_point.get("location")
        clicked_country = country_code_to_name.get(country_code)
        if clicked_country is None:
            return no_update, no_update
        new_value = None if clicked_country == current_country else clicked_country
        return new_value, no_update

    return no_update, no_update


# Selecting/searching a country (via dropdown, or via the table click above)
# populates the individual medal winners table.
@callback(
    Output("country-winners-table", "data"),
    Output("country-winners-title", "children"),
    Input("country-search-dropdown", "value"),
)
def update_country_winners_table(selected_country):
    if not selected_country:
        return [], "Select a country to view its medal winners"

    country_winners = (
        winners_df[winners_df["country"] == selected_country]
        [["name", "gender", "discipline", "event", "medal_type", "medal_date", "code"]]
        .sort_values("medal_date")
    )
    # "id" (the row's position in winners_df) and "code" aren't displayed
    # columns — they let a click on any row be traced back to its athlete
    # or team, whatever sorting/filtering the user has applied.
    records = country_winners.assign(id=country_winners.index).to_dict("records")

    return (
        records,
        f"Medal Winners — {selected_country} ({len(country_winners)} total)",
    )


# Clicking any part of a row in the medal winners table opens the matching
# profile on the Olympic Athlete Search page: an athlete for individual
# medals, or the team's profile for team/pair/relay medals (those rows carry
# the team's own code instead of an athlete's). The code travels in the URL
# query string (/athlete-search?code=...), which that page's layout reads.
# _pages_location is Dash Pages' own routing component (already written to
# by app.py), so its pathname output needs allow_duplicate.
@callback(
    Output("_pages_location", "pathname", allow_duplicate=True),
    Output("_pages_location", "search"),
    Input("country-winners-table", "active_cell"),
    prevent_initial_call=True,
)
def open_profile_from_winners_row(active_cell):
    if not active_cell or active_cell.get("row_id") is None:
        return no_update, no_update

    code = winners_df.loc[int(active_cell["row_id"]), "code"]
    return "/athlete-search", f"?code={quote(str(code))}"


# Outlines the selected country on the map in red — whether it was selected
# via the table, the map itself, or the search dropdown — and clears the
# outline again on de-select. Uses Patch() to update just the highlight
# trace's data in place, rather than re-sending the whole figure.
@callback(
    Output("medals-choropleth", "figure"),
    Input("country-search-dropdown", "value"),
)
def highlight_selected_country_on_map(selected_country):
    patched_fig = Patch()
    country_code = country_name_to_code.get(selected_country) if selected_country else None

    if country_code:
        patched_fig["data"][1]["locations"] = [country_code]
        patched_fig["data"][1]["z"] = [1]
    else:
        patched_fig["data"][1]["locations"] = []
        patched_fig["data"][1]["z"] = []

    return patched_fig



# Highlights the selected country's row in the leaders table with a red
# border outline (rather than a solid fill), and reverts it back to the
# default (zebra-striped) style whenever the selection changes to a
# different country or is cleared — whether that change came from clicking
# a different table row, a different country on the map, or the search
# dropdown.
#
# The row is matched on its unique "Rank" value via filter_query, rather
# than on a row position. Rank travels with the row itself, so the right
# row stays highlighted however the user has sorted or filtered the table.
#
# A border, rather than a solid background fill, sidesteps DataTable's
# built-in "active cell" overlay issue entirely: that overlay sits on the
# row's own background colour, so on a solid red fill it stood out as an
# obvious blank white box; against the table's normal white/grey rows it
# simply blends in and is no longer visually distracting.
SELECTED_ROW_BORDER = "3px solid #EF4135"


@callback(
    Output("medal-leaders-table", "style_data_conditional"),
    Input("country-search-dropdown", "value"),
)
def highlight_selected_country_in_table(selected_country):
    styles = list(LEADERS_TABLE_BASE_STYLE)

    if selected_country:
        matching = leaders_df[leaders_df["country"] == selected_country]
        if not matching.empty:
            rank_query = f"{{Rank}} = {int(matching.iloc[0]['Rank'])}"
            first_col = leaders_df.columns[0]
            last_col = leaders_df.columns[-1]
            styles.extend([
                # Top/bottom border applies to every cell in the row, which
                # draws a continuous line across the full row width.
                {
                    "if": {"filter_query": rank_query},
                    "borderTop": SELECTED_ROW_BORDER,
                    "borderBottom": SELECTED_ROW_BORDER,
                },
                # Left/right borders only need to apply to the first/last
                # column to close off the rectangle at each end.
                {
                    "if": {"filter_query": rank_query, "column_id": first_col},
                    "borderLeft": SELECTED_ROW_BORDER,
                },
                {
                    "if": {"filter_query": rank_query, "column_id": last_col},
                    "borderRight": SELECTED_ROW_BORDER,
                },
            ])

    return styles


# Moves the leaders table to whichever page the selected country sits on.
# Without this, selecting a country ranked below the first page (16th or
# lower) from the map or the dropdown highlights its row correctly, but
# on a page the user isn't looking at — so nothing appears to happen.
#
# derived_virtual_indices lists the original row positions in the order
# they're currently displayed (after any sorting/filtering), so the page is
# worked out from where the country actually appears on screen rather than
# from its rank. If the country has been filtered out of the table there's
# no page to show it on, so the page is left alone. De-selecting also
# leaves the page where it is.
@callback(
    Output("medal-leaders-table", "page_current"),
    Input("country-search-dropdown", "value"),
    State("medal-leaders-table", "derived_virtual_indices"),
    prevent_initial_call=True,
)
def go_to_selected_country_page(selected_country, displayed_indices):
    if not selected_country:
        return no_update

    matching_rows = leaders_df.index[leaders_df["country"] == selected_country].tolist()
    if not matching_rows:
        return no_update

    if displayed_indices is None:
        displayed_indices = list(range(len(leaders_df)))

    original_idx = matching_rows[0]
    if original_idx not in displayed_indices:
        return no_update

    position = displayed_indices.index(original_idx)
    return position // LEADERS_PAGE_SIZE
