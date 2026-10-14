"""
Builds torch_route_geocoded.csv using a hardcoded coordinate lookup table
instead of a live geocoding service. This avoids the network hang/timeout
caused by the TAFE network blocking access to nominatim.openstreetmap.org.

Run this once from your project root:
    python build_torch_coordinates.py
"""

import pandas as pd

INPUT_CSV = "Paris_Olympics_dataset/torch_route.csv"
OUTPUT_CSV = "Paris_Olympics_dataset/torch_route_geocoded.csv"

# Approximate coordinates for every stop in the relay, including
# mainland France, Greece, and the overseas territories visited.
CITY_COORDS = {
    "Olympia": (37.6382, 21.6300),
    "Athens": (37.9838, 23.7275),
    "Marseille": (43.2965, 5.3698),
    "Toulon": (43.1242, 5.9280),
    "Manosque": (43.8288, 5.7838),
    "Arles": (43.6766, 4.6278),
    "Montpellier": (43.6108, 3.8767),
    "Bastia": (42.6979, 9.4501),
    "Perpignan": (42.6887, 2.8948),
    "Carcassonne": (43.2130, 2.3491),
    "Toulouse": (43.6047, 1.4442),
    "Auch": (43.6459, 0.5858),
    "Tarbes": (43.2326, 0.0783),
    "Pau": (43.2951, -0.3708),
    "Périgueux": (45.1848, 0.7210),
    "Bordeaux": (44.8378, -0.5792),
    "Angoulême": (45.6486, 0.1560),
    "Grand Poitiers Futuroscope": (46.5802, 0.3404),
    "Châteauroux": (46.8107, 1.6911),
    "Angers": (47.4784, -0.5632),
    "Laval": (48.0698, -0.7700),
    "Caen": (49.1829, -0.3707),
    "Le Mont-Saint-Michel": (48.6361, -1.5115),
    "Rennes": (48.1173, -1.6778),
    "Niort": (46.3239, -0.4585),
    "Les Sables-d'Olonne": (46.4967, -1.7833),
    "La Baule-Escoublac": (47.2860, -2.3925),
    "Vannes": (47.6582, -2.7608),
    "Brest": (48.3904, -4.4861),
    "Cayenne": (4.9333, -52.3333),
    "Nouméa": (-22.2758, 166.4581),
    "Saint-Denis": (-20.8789, 55.4481),
    "Pīra'e-Pape'ete": (-17.5334, -149.5667),
    "Baie-Mahault": (16.2411, -61.5809),
    "Fort-de-France": (14.6161, -61.0588),
    "Nice": (43.7102, 7.2620),
    "Avignon": (43.9493, 4.8055),
    "Valence": (44.9333, 4.8924),
    "Vichy": (46.1274, 3.4265),
    "Saint-Etienne": (45.4397, 4.3872),
    "Chamonix-Mont-Blanc": (45.9237, 6.8694),
    "Besançon": (47.2378, 6.0241),
    "Strasbourg": (48.5734, 7.7521),
    "Metz": (49.1193, 6.1757),
    "Saint-Dizier": (48.6373, 4.9502),
    "Verdun": (49.1593, 5.3844),
    "Reims": (49.2583, 4.0317),
    "Lille": (50.6292, 3.0573),
    "Lens-Liévin": (50.4327, 2.8319),
    "Amiens": (49.8942, 2.2957),
    "Le Havre": (49.4944, 0.1079),
    "Vernon": (49.0921, 1.4839),
    "Chartres": (48.4439, 1.4893),
    "Blois": (47.5861, 1.3359),
    "Orléans": (47.9029, 1.9093),
    "Auxerre": (47.7982, 3.5731),
    "Dijon": (47.3220, 5.0415),
    "Troyes": (48.2973, 4.0744),
    "Place de l’Hôtel de Ville": (48.8566, 2.3522),
    "Place de la République": (48.8674, 2.3632),
    "Saint-Quentin": (49.8494, 3.2870),
    "Beauvais": (49.4295, 2.0807),
    "Soisy-sous-Montmorency": (48.9926, 2.3212),
    "Meaux": (48.9600, 2.8786),
    "Créteil": (48.7904, 2.4556),
    "Evry-Courcouronnes": (48.6289, 2.4297),
    "Versailles": (48.8049, 2.1204),
    "Nanterre > L’Arche de la Défense": (48.8924, 2.2362),
    "Parc Georges-Valbon": (48.9349, 2.3903),
    "Paris": (48.8566, 2.3522),
}

torch_df = pd.read_csv(INPUT_CSV)
torch_df = torch_df.dropna(subset=["city"]).copy()
torch_df["date_start"] = pd.to_datetime(torch_df["date_start"])
torch_df = torch_df.sort_values("date_start").reset_index(drop=True)

torch_df["latitude"] = torch_df["city"].map(lambda c: CITY_COORDS.get(c, (None, None))[0])
torch_df["longitude"] = torch_df["city"].map(lambda c: CITY_COORDS.get(c, (None, None))[1])

missing = torch_df[torch_df["latitude"].isna()]["city"].unique()
if len(missing):
    print("Warning: no coordinates found for these cities (left blank):")
    for c in missing:
        print(f"  - {c}")

torch_df.to_csv(OUTPUT_CSV, index=False)
print(f"\nSaved {len(torch_df) - len(missing)} geocoded stops to {OUTPUT_CSV}")
