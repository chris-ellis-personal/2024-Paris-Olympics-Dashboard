import dash
from dash import Dash, html, dcc, Input, Output, ALL
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd

# All visual styling lives in assets/olympics_theme.css. Dash loads every
# .css file in the /assets folder automatically (after the stylesheets
# listed here), so it doesn't need to be referenced explicitly.
#
# Dash finds the assets/ and pages/ folders relative to this file (not the
# folder the app is launched from), and app.get_asset_url() below builds
# image URLs, so nothing here depends on where the project is stored.
app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.SPACELAB],
)

# Icon shown to the left of each tab's label, keyed by the page's route.
# These files are expected to live in /assets alongside the other images.
PAGE_ICONS = {
    "/": "home_tab_image.png",
    "/athlete-search": "athlete_tab_image.png",
    "/torch-path": "olympic_torch_tab_image.png",
}

# CSS class names (defined in assets/olympics_theme.css). The tab for
# whichever page is currently open gets the extra "--active" class, which
# turns it solid black.
TAB_CLASS = "nav-tab"
TAB_ACTIVE_CLASS = "nav-tab nav-tab--active"


def build_nav_tabs():
    """One tab per registered page, icon on the left of the label. Each
    tab gets a pattern-matching id so the callback below can restyle all
    of them at once based on the current URL."""
    tabs = []
    for page in dash.page_registry.values():
        icon_file = PAGE_ICONS.get(page["path"])
        tab_children = []
        if icon_file:
            tab_children.append(
                html.Div(
                    html.Img(src=app.get_asset_url(icon_file), className="nav-tab__icon"),
                    className="nav-tab__badge",
                )
            )
        tab_children.append(html.Span(page["name"]))

        tabs.append(
            dcc.Link(
                tab_children,
                href=page["path"],
                id={"type": "nav-tab", "index": page["path"]},
                className=TAB_CLASS,
            )
        )
    return tabs


sidebar_nav = html.Div(build_nav_tabs(), className="app-sidebar")

# Layout goes here

app.layout = html.Div([
    # Memory storage is wiped on every full browser load/refresh but
    # persists across ordinary client-side tab navigation, so it doubles
    # as a "has this browser tab already initialised?" flag. See the
    # force_home_on_load callback below.
    dcc.Store(id="app-initialised", storage_type="memory", data=False),

    html.Div([
        html.Img(src=app.get_asset_url("olympic_flag.png"), className="app-header__flag"),

        html.Div(
            html.H1("Paris 2024 Olympics", className="app-header__title"),
            className="app-header__banner",
        ),

        html.Img(src=app.get_asset_url("paris_2024_olympic_flag.png"), className="app-header__flag"),
    ], className="app-header"),

    # Sidebar (left) + page content (right), sitting beneath the header.
    html.Div([
        sidebar_nav,
        html.Div(dash.page_container, className="app-content"),
    ], className="app-body"),
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
    Output({"type": "nav-tab", "index": ALL}, "className"),
    Input("_pages_location", "pathname"),
)
def highlight_active_tab(pathname):
    """Swap every tab's CSS class whenever the route changes: the page
    currently being viewed gets the active (black) class, everything else
    the plain (grey) one."""
    classes = []
    for page in dash.page_registry.values():
        if pathname == page["path"]:
            classes.append(TAB_ACTIVE_CLASS)
        else:
            classes.append(TAB_CLASS)
    return classes


if __name__ == '__main__':
    app.run()
