import dash
from dash import Dash, html, dcc
import plotly.graph_objects as go
import pandas as pd

dash.register_page(__name__, path='/torch-path', name='Olympic Torch Path')

# ---------------------------------------------------------------
# Load pre-geocoded data
#
# NOTE: run build_torch_coordinates.py once beforehand to generate
# torch_route_geocoded.csv. This uses a static, offline coordinate
# table rather than a live geocoding service, avoiding the network
# hang caused by this network blocking Nominatim.
# ---------------------------------------------------------------
torch_df = pd.read_csv("Paris_Olympics_dataset/torch_route_geocoded.csv")
torch_df["date_start"] = pd.to_datetime(torch_df["date_start"])
torch_df = torch_df.dropna(subset=["latitude", "longitude"])

# stage_number gives the official relay order (1-68). The handful of early
# ceremonial legs (lighting, handover, Mediterranean crossing, prologue)
# precede stage 1 and have no stage_number, so date_start places them
# correctly at the very start of the route.
torch_df["sort_key"] = torch_df["stage_number"].fillna(0)
torch_df = torch_df.sort_values(["sort_key", "date_start"]).reset_index(drop=True)

# Sequential stop number for every location visited, in order (1, 2, 3, ...)
torch_df["stop_number"] = torch_df.index + 1

# ---------------------------------------------------------------
# Build the torch relay route map
# ---------------------------------------------------------------
torch_map_fig = go.Figure()

# Thin connecting line beneath everything, showing the overall path
torch_map_fig.add_trace(go.Scattergeo(
    lat=torch_df["latitude"],
    lon=torch_df["longitude"],
    mode="lines",
    line=dict(width=1, color="rgba(239, 65, 53, 0.4)"),
    hoverinfo="skip",
    showlegend=False,
))

# Numbered circle markers, one per stop, in visiting order
torch_map_fig.add_trace(go.Scattergeo(
    lat=torch_df["latitude"],
    lon=torch_df["longitude"],
    mode="markers+text",
    marker=dict(
        size=20,
        color="#0055A4",
        line=dict(color="white", width=1),
    ),
    text=torch_df["stop_number"].astype(str),
    textfont=dict(color="white", size=9, family="Arial Black"),
    textposition="middle center",
    hovertext=(
        torch_df["stop_number"].astype(str) + ". " + torch_df["city"] + " — "
        + torch_df["title"] + "<br>" + torch_df["date_start"].dt.strftime("%d %b %Y")
    ),
    hoverinfo="text",
    showlegend=False,
))

torch_map_fig.update_layout(
    title="Paris 2024 Olympic Torch Relay Route",
    geo=dict(
        scope="world",
        projection_type="equirectangular",
        resolution=110,          # coarsest (fastest) coastline detail
        showframe=False,
        showcoastlines=True,
        landcolor="#f0f0f0",
        countrycolor="#cccccc",
    ),
    margin=dict(l=0, r=0, t=50, b=0),
    autosize=True,
    dragmode="pan",
    # Keeps the user's current zoom/pan if Dash ever re-sends the figure.
    uirevision="torch-route",
)

# Sizing lives in assets/olympics_theme.css (.graph / .graph--tall = 85% of
# the window height). The map fills the content area rather than the browser
# viewport, so it never slides underneath the sidebar from app.py.
torch_route_layout = html.Div(
    [
        html.H2("Olympic Torch Relay Path", className="page-title"),
        dcc.Graph(
            id="torch-route-map",
            figure=torch_map_fig,
            className="graph graph--tall",
            config={"responsive": True, "scrollZoom": True, "displaylogo": False},
        ),
    ],
    className="torch-page",
)

# ---------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------
layout = html.Div([
    torch_route_layout,
])
