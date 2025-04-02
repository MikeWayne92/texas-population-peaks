import geopandas as gpd
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import requests
import zipfile
import io
import os

# --- 1. Download & Extract Data ---
shapefile_url = "https://www2.census.gov/geo/tiger/TIGER2024/BG/tl_2024_48_bg.zip"
extract_to_folder = "texas_bg_shapefile_2024"
shapefile_name = "tl_2024_48_bg.shp"
shapefile_path = os.path.join(extract_to_folder, shapefile_name)

print(f"Attempting to download shapefile from: {shapefile_url}")

try:
    # Create folder if it doesn't exist
    if not os.path.exists(extract_to_folder):
        os.makedirs(extract_to_folder)
        print(f"Created directory: {extract_to_folder}")

    # Download only if the shapefile doesn't already exist
    if not os.path.exists(shapefile_path):
        response = requests.get(shapefile_url, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Use BytesIO to handle the zip file in memory before extracting
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            print(f"Extracting files to: {extract_to_folder}")
            z.extractall(extract_to_folder)
        print("Download and extraction complete.")
    else:
        print(f"Shapefile '{shapefile_name}' already exists in '{extract_to_folder}'. Skipping download.")

except requests.exceptions.RequestException as e:
    print(f"Error downloading file: {e}")
    exit()
except zipfile.BadZipFile:
    print("Error: Downloaded file is not a valid ZIP archive.")
    exit()
except Exception as e:
    print(f"An unexpected error occurred during download/extraction: {e}")
    exit()

# --- 2. Load Shapefile ---
print(f"Loading shapefile: {shapefile_path}")
try:
    gdf = gpd.read_file(shapefile_path)
    print("Shapefile loaded successfully.")
    print(f"Original CRS: {gdf.crs}")
except Exception as e:
    print(f"Error loading shapefile: {e}")
    exit()

# --- 3. Data Preparation ---

# Ensure Geographic CRS (WGS84) for Plotly compatibility if needed
if gdf.crs != "EPSG:4326":
    print("Reprojecting to EPSG:4326 (WGS 84)...")
    gdf = gdf.to_crs("EPSG:4326")
    print(f"New CRS: {gdf.crs}")

# Calculate Centroids
# Suppress warning about calculating centroids in geographic CRS
import warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS.*", category=UserWarning)
    gdf['centroid'] = gdf.geometry.centroid
    gdf['lon'] = gdf.centroid.x
    gdf['lat'] = gdf.centroid.y

# --- Density Calculation ---
print("\nAvailable columns:", gdf.columns.tolist())

population_col = None
area_col = None

# Try to find standard population and land area columns
potential_pop_cols = ['POP', 'POP100', 'POP20']
potential_area_cols = ['ALAND']

for col in potential_pop_cols:
    if col in gdf.columns:
        population_col = col
        print(f"Using '{population_col}' for population.")
        break

for col in potential_area_cols:
    if col in gdf.columns and pd.api.types.is_numeric_dtype(gdf[col]) and gdf[col].sum() > 0:
        area_col = col
        print(f"Using '{area_col}' for land area.")
        break

if population_col and area_col:
    print("Calculating density (Population / Land Area)...")
    gdf[area_col] = pd.to_numeric(gdf[area_col], errors='coerce')
    gdf['density'] = (gdf[population_col] / (gdf[area_col] / 1_000_000)).fillna(0)
    gdf['density'].replace([np.inf, -np.inf], 0, inplace=True)
    height_col = 'density'
    color_col = 'density'
    hover_text_col = 'density'
elif population_col:
    print(f"WARNING: Area column not found or invalid. Using raw population '{population_col}' for height and color.")
    height_col = population_col
    color_col = population_col
    hover_text_col = population_col
    gdf[height_col] = pd.to_numeric(gdf[height_col], errors='coerce').fillna(0)
else:
    print("WARNING: Population column not found. Simulating height with random data for demonstration.")
    np.random.seed(42)
    gdf['simulated_height'] = np.random.rand(len(gdf)) * 1000
    height_col = 'simulated_height'
    color_col = 'simulated_height'
    hover_text_col = 'simulated_height'

# Normalize height for visualization
min_h = gdf[height_col].min()
max_h = gdf[height_col].max()
if max_h > min_h:
    gdf['z_height'] = ((gdf[height_col] - min_h) / (max_h - min_h)) ** 1.5 * 100
else:
    gdf['z_height'] = 50

# Prepare hover text
gdf['hover_info'] = gdf.apply(lambda row: f"GEOID: {row.get('GEOID', 'N/A')}<br>Lon: {row.lon:.4f}<br>Lat: {row.lat:.4f}<br>{hover_text_col.capitalize()}: {row[height_col]:,.2f}<br>Scaled Z: {row.z_height:.2f}", axis=1)

# --- 4. Create 3D Plot (Plotly) ---
print("Creating 3D scatter plot...")

scatter_trace = go.Scatter3d(
    x=gdf['lon'],
    y=gdf['lat'],
    z=gdf['z_height'],
    mode='markers',
    marker=dict(
        size=3,
        color=gdf[color_col],
        colorscale='Viridis',
        colorbar=dict(title=color_col.replace('_',' ').capitalize()),
        opacity=0.8,
    ),
    text=gdf['hover_info'],
    hoverinfo='text',
    name='Block Groups'
)

# Add Texas Boundary
print("Adding state boundary for context...")
texas_boundary = gdf.unary_union
boundary_trace = None

if texas_boundary.geom_type == 'Polygon':
    boundary_x, boundary_y = texas_boundary.exterior.xy
    boundary_trace = go.Scatter3d(
        x=list(boundary_x),
        y=list(boundary_y),
        z=np.zeros(len(boundary_x)),
        mode='lines',
        line=dict(color='black', width=2),
        hoverinfo='none',
        name='Texas Outline'
    )
elif texas_boundary.geom_type == 'MultiPolygon':
    all_x = []
    all_y = []
    for poly in texas_boundary.geoms:
        bx, by = poly.exterior.xy
        all_x.extend(list(bx) + [None])
        all_y.extend(list(by) + [None])
    boundary_trace = go.Scatter3d(
        x=all_x,
        y=all_y,
        z=np.zeros(len(all_x)),
        mode='lines',
        line=dict(color='black', width=2),
        hoverinfo='none',
        name='Texas Outline'
    )

# Configure Layout
layout = go.Layout(
    title=f'3D Visualization of Texas Block Group {height_col.capitalize()} (2024 TIGER/Line)',
    scene=dict(
        xaxis=dict(title='Longitude'),
        yaxis=dict(title='Latitude'),
        zaxis=dict(title=f'Scaled {height_col.capitalize()}'),
        aspectratio=dict(x=1, y=1, z=0.3),
        camera=dict(
            eye=dict(x=1.5, y=-1.5, z=1.0)
        ),
    ),
    margin=dict(l=0, r=0, b=0, t=40)
)

# Combine traces and layout
fig_data = [scatter_trace]
if boundary_trace:
    fig_data.append(boundary_trace)

fig = go.Figure(data=fig_data, layout=layout)

# Generate HTML
output_html_file = 'texas_block_group_density_3d.html'
print(f"Saving interactive plot to: {output_html_file}")
fig.write_html(output_html_file)
print("Done. Open the HTML file in a web browser.")