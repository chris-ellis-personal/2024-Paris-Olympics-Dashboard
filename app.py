"""
Paris 2024 Olympics Dashboard - application entry point (header, sidebar tabs, page container).

@author: Chris Ellis
"""

import dash
from dash import Dash, html, dcc, Input, Output, ALL
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    external_stylesheets=['game_style.css', dbc.themes.SPACELAB],
)

# Icon shown to the left of each tab's label, keyed by the page's route.
# These files are expected to live in /assets alongside the other images.
PAGE_ICONS = {
    "/": "home_tab_image.png",
    "/athlete-search": "athlete_tab_image.png",
    "/torch-path": "olympic_torch_tab_image.png",
}

NAV_FONT_FAMILY = "'Helvetica Neue', Arial, sans-serif"

TAB_INACTIVE_STYLE = {
    "display": "flex",
    "alignItems": "center",
    "gap": "10px",
    "padding": "12px 18px",
    "backgroundColor": "#d9d9d9",
    "color": "#444444",
    "fontFamily": NAV_FONT_FAMILY,
    "fontWeight": "500",
    "fontSize": "16px",
    "textDecoration": "none",
    "borderRadius": "6px",
    "marginBottom": "8px",
}

# The tab for whichever page is currently open turns solid black to stand
# out from the grey, inactive tabs.
TAB_ACTIVE_STYLE = {
    **TAB_INACTIVE_STYLE,
    "backgroundColor": "#000000",
    "color": "#ffffff",
    "fontWeight": "700",
}


# White backdrop behind each tab's icon. The icon artwork is dark-stroked,
# so it disappears against the active (black) tab without this — giving
# every tab the same badge (not just the active one) keeps icon sizing
# identical across states, so nothing shifts when a tab is selected.
ICON_BADGE_STYLE = {
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "center",
    "flexShrink": "0",
    "width": "28px",
    "height": "28px",
    "borderRadius": "50%",
    "backgroundColor": "#ffffff",
}


def build_nav_tabs():
    """One tab per registered page, icon on the left of the label. Each
    tab gets a pattern-matching id so the callback below can recolour all
    of them at once based on the current URL."""
    tabs = []
    for page in dash.page_registry.values():
        icon_file = PAGE_ICONS.get(page["path"])
        tab_children = []
        if icon_file:
            tab_children.append(
                html.Div(
                    html.Img(
                        src=f"assets/{icon_file}",
                        style={"height": "18px", "width": "18px"},
                    ),
                    style=ICON_BADGE_STYLE,
                )
            )
        tab_children.append(html.Span(page["name"]))

        tabs.append(
            dcc.Link(
                tab_children,
                href=page["path"],
                id={"type": "nav-tab", "index": page["path"]},
                style=dict(TAB_INACTIVE_STYLE),
            )
        )
    return tabs


sidebar_nav = html.Div(
    build_nav_tabs(),
    style={
        "display": "flex",
        "flexDirection": "column",
        "width": "220px",
        "flexShrink": "0",
        "padding": "20px 10px",
    },
)

# Layout goes here

app.layout = html.Div([
    # Memory storage is wiped on every full browser load/refresh but
    # persists across ordinary client-side tab navigation, so it doubles
    # as a "has this browser tab already initialised?" flag. See the
    # force_home_on_load callback below.
    dcc.Store(id="app-initialised", storage_type="memory", data=False),

    html.Div([
        html.Img(
            src="assets/olympic_flag.png",
            style={"height": "175px"}
        ),

        html.Div(
            html.H1(
                "Paris 2024 Olympics",
                style={
                    "margin": "0",
                    "color": "black",
                    "textAlign": "center",
                    "fontFamily": NAV_FONT_FAMILY,
                }
            ),
            style={
                "flex": "1",
                "height": "175px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "background": "linear-gradient(to right, #0055A4 33.33%, #FFFFFF 33.33%, #FFFFFF 66.66%, #EF4135 66.66%)"
            }
        ),

        html.Img(
            src="assets/paris_2024_olympic_flag.png",
            style={"height": "175px"}
        )
    ], style={
        "display": "flex",
        "alignItems": "center",
        "width": "100%",
    }),

    # Sidebar (left) + page content (right), sitting beneath the header.
    # minWidth: 0 stops a wide figure from forcing this flex item past its
    # allotted space, and overflowX: hidden is a safety net so any page
    # that (now or in future) tries a full-viewport-width layout trick gets
    # clipped to this container instead of sliding over the sidebar.
    html.Div([
        sidebar_nav,
        html.Div(
            dash.page_container,
            style={
                "flex": "1",
                "minWidth": "0",
                "padding": "20px",
                "overflowX": "hidden",
            },
        ),
    ], style={
        "display": "flex",
        "flexDirection": "row",
        "alignItems": "flex-start",
        "width": "100%",
    }),
])


@app.callback(
    Output("_pages_location", "pathname"),
    Output("app-initialised", "data"),
    Input("app-initialised", "data"),
    prevent_initial_call=False,
)
def force_home_on_load(initialised):
    """Runs once at the start of every browser session (first load or a
    hard refresh), since app-initialised resets to False whenever the page
    is reloaded from scratch. Redirects to the homepage, then flips the
    flag to True so ordinary tab clicks afterwards aren't affected — this
    callback only fires again on the next real page load.

    This targets Dash Pages' own internal Location component
    (id="_pages_location", already present inside dash.page_container)
    rather than a separate custom one — that component is set up with
    refresh="callback-nav", which is what actually lets a callback-driven
    URL change also swap the displayed page content. A second, independent
    dcc.Location doesn't share that wiring, which was why the tab
    highlight previously updated correctly on refresh but the page content
    didn't follow it."""
    if initialised:
        return dash.no_update, dash.no_update
    return "/", True


@app.callback(
    Output({"type": "nav-tab", "index": ALL}, "style"),
    Input("_pages_location", "pathname"),
)
def highlight_active_tab(pathname):
    """Recolour every tab whenever the route changes: black for the page
    currently being viewed, grey for everything else."""
    styles = []
    for page in dash.page_registry.values():
        if pathname == page["path"]:
            styles.append(dict(TAB_ACTIVE_STYLE))
        else:
            styles.append(dict(TAB_INACTIVE_STYLE))
    return styles


if __name__ == '__main__':
    app.run()
