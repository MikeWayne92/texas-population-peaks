import geopandas as gpd
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import requests
import zipfile
import io
import os
from plotly.subplots import make_subplots
import colorsys

# --- 1. Data Loading (reusing download logic) ---
shapefile_url = "https://www2.census.gov/geo/tiger/TIGER2024/BG/tl_2024_48_bg.zip"
extract_to_folder = "texas_bg_shapefile_2024"
shapefile_name = "tl_2024_48_bg.shp"
shapefile_path = os.path.join(extract_to_folder, shapefile_name)

if not os.path.exists(shapefile_path):
    print(f"Downloading shapefile from: {shapefile_url}")
    if not os.path.exists(extract_to_folder):
        os.makedirs(extract_to_folder)
    
    response = requests.get(shapefile_url, stream=True)
    response.raise_for_status()
    
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        z.extractall(extract_to_folder)
    print("Download complete.")

# --- 2. Load and Process Data ---
print("Processing data...")
gdf = gpd.read_file(shapefile_path)
if gdf.crs != "EPSG:4326":
    gdf = gdf.to_crs("EPSG:4326")

# Calculate centroids
gdf['centroid'] = gdf.geometry.centroid
gdf['lon'] = gdf.centroid.x
gdf['lat'] = gdf.centroid.y

# --- 3. Enhanced Data Processing ---
# Find population and area columns
pop_col = next((col for col in ['POP100', 'POP20', 'POP'] if col in gdf.columns), None)
area_col = next((col for col in ['ALAND'] if col in gdf.columns), None)

if pop_col and area_col:
    gdf['density'] = (pd.to_numeric(gdf[pop_col]) / (pd.to_numeric(gdf[area_col]) / 1_000_000)).fillna(0)
    gdf['density'] = gdf['density'].replace([np.inf, -np.inf], 0)
    value_col = 'density'
else:
    gdf['population'] = pd.to_numeric(gdf[pop_col] if pop_col else 0)
    value_col = 'population'

# --- 4. Creative Data Transformations ---
# Create more complex wave patterns
gdf['wave1'] = np.sin(gdf['lon'] * 3) * np.cos(gdf['lat'] * 3) * 0.15
gdf['wave2'] = np.sin(gdf['lat'] * 5) * np.cos(gdf['lon'] * 2) * 0.1
gdf['wave'] = gdf['wave1'] + gdf['wave2']

# Add randomized "terrain" noise with controlled distribution
np.random.seed(42)
gdf['terrain'] = np.random.beta(2, 5, size=len(gdf)) * 0.2

# Normalize main values with enhanced scaling
max_val = gdf[value_col].max()
gdf['height'] = (gdf[value_col] / max_val * 0.85) + gdf['wave'] + gdf['terrain']
gdf['height'] = (gdf['height'] - gdf['height'].min()) / (gdf['height'].max() - gdf['height'].min())

# Create dynamic color palette with enhanced gradients
def generate_colors(n_colors):
    colors = []
    for i in range(n_colors):
        if i < n_colors / 2:
            # Cool colors (blues to purples)
            hue = 0.7 - (i / (n_colors/2) * 0.15)
            sat = 0.7 + (i / (n_colors/2) * 0.3)
            val = 0.5 + (i / (n_colors/2) * 0.5)
        else:
            # Warm colors (purples to reds)
            hue = 0.55 - ((i - n_colors/2) / (n_colors/2) * 0.35)
            sat = 1.0
            val = 1.0
        rgb = colorsys.hsv_to_rgb(hue, sat, val)
        colors.append(f'rgb({int(rgb[0]*255)},{int(rgb[1]*255)},{int(rgb[2]*255)})')
    return colors

# --- 5. Create Enhanced 3D Visualization ---
print("Creating enhanced 3D visualization...")

# Create figure with enhanced subplot configuration
fig = make_subplots(
    rows=1, cols=1,
    specs=[[{'type': 'scene'}]],
    subplot_titles=[f'Texas Population Peaks - {value_col.title()} Visualization']
)

# Generate enhanced color scale
n_colors = 150  # Increased color resolution
colors = generate_colors(n_colors)

# Main scatter plot with enhanced styling
scatter = go.Scatter3d(
    x=gdf['lon'],
    y=gdf['lat'],
    z=gdf['height'],
    mode='markers',
    marker=dict(
        size=3.5,
        color=gdf['height'],
        colorscale=colors,
        opacity=0.85,
        symbol='circle',
        line=dict(
            color='rgba(255, 255, 255, 0.3)',
            width=0.5
        )
    ),
    text=[f"{value_col.title()}: {val:,.0f}<br>Location: ({lon:.2f}°, {lat:.2f}°)"
          for val, lon, lat in zip(gdf[value_col], gdf['lon'], gdf['lat'])],
    hoverinfo='text',
    name='Population Centers'
)

# Create enhanced terrain effect
lon_range = np.linspace(gdf['lon'].min(), gdf['lon'].max(), 75)  # Increased resolution
lat_range = np.linspace(gdf['lat'].min(), gdf['lat'].max(), 75)
lon_mesh, lat_mesh = np.meshgrid(lon_range, lat_range)

# Create more complex terrain surface
z_mesh = np.zeros(lon_mesh.shape)
for i in range(len(lon_range)):
    for j in range(len(lat_range)):
        z_mesh[i,j] = (
            np.sin(lon_mesh[i,j] * 4) * np.cos(lat_mesh[i,j] * 4) * 0.03 +
            np.sin(lat_mesh[i,j] * 6) * np.cos(lon_mesh[i,j] * 3) * 0.02
        )

surface = go.Surface(
    x=lon_mesh,
    y=lat_mesh,
    z=z_mesh,
    colorscale=[[0, 'rgb(240,240,240)'], [1, 'rgb(200,200,200)']],
    showscale=False,
    opacity=0.15,
    hoverinfo='skip'
)

# Add traces to figure
fig.add_trace(surface)
fig.add_trace(scatter)

# Update layout with enhanced styling
fig.update_layout(
    scene=dict(
        xaxis=dict(
            title='Longitude',
            showgrid=False,
            showspikes=False,
            showbackground=True,
            backgroundcolor='rgb(250, 250, 250)'
        ),
        yaxis=dict(
            title='Latitude',
            showgrid=False,
            showspikes=False,
            showbackground=True,
            backgroundcolor='rgb(250, 250, 250)'
        ),
        zaxis=dict(
            title=value_col.title(),
            showgrid=False,
            showspikes=False,
            showbackground=True,
            backgroundcolor='rgb(250, 250, 250)'
        ),
        camera=dict(
            up=dict(x=0, y=0, z=1),
            center=dict(x=0, y=0, z=-0.1),
            eye=dict(x=1.8, y=1.8, z=1.5)
        ),
        aspectratio=dict(x=1.5, y=1, z=0.7)
    ),
    title=dict(
        text=f'Texas Population Peaks - An Artistic Visualization of {value_col.title()}',
        y=0.95,
        x=0.5,
        xanchor='center',
        yanchor='top',
        font=dict(
            family='Arial Black',
            size=24,
            color='#1f77b4'
        )
    ),
    showlegend=False,
    paper_bgcolor='rgb(240,240,240)',
    margin=dict(l=0, r=0, t=30, b=0)
)

# --- 6. Save and Display ---
output_file = 'texas_population_peaks.html'
fig.write_html(output_file, include_plotlyjs=True, full_html=True)
print(f"Visualization saved as {output_file}")

# Add custom HTML wrapper with enhanced styling
with open(output_file, 'r') as file:
    content = file.read()

enhanced_html = f'''
<!DOCTYPE html>
<html>
<head>
    <title>Texas Population Peaks - Interactive 3D Visualization</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            font-family: 'Arial', sans-serif;
            color: #2c3e50;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .description {{
            margin: 20px 0;
            padding: 20px;
            background: #f8f9fa;
            border-left: 4px solid #1f77b4;
            border-radius: 4px;
        }}
        .description h2 {{
            color: #1f77b4;
            margin-top: 0;
        }}
        .description p {{
            line-height: 1.6;
        }}
        .description ul {{
            padding-left: 20px;
        }}
        .description li {{
            margin: 8px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="description">
            <h2>About This Visualization</h2>
            <p>This interactive 3D visualization transforms Texas {value_col} data into an artistic landscape of peaks and valleys. 
            Each point represents a block group, with height and color intensity corresponding to {value_col} values. 
            The underlying terrain adds depth and context to the visualization.</p>
            <p><strong>Interactive Features:</strong></p>
            <ul>
                <li>🔄 Click and drag to rotate the view</li>
                <li>🔍 Scroll to zoom in/out</li>
                <li>✋ Right-click and drag to pan</li>
                <li>👆 Double-click to reset the view</li>
                <li>ℹ️ Hover over points to see detailed information</li>
            </ul>
        </div>
        {content}
    </div>
</body>
</html>
'''

with open(output_file, 'w') as file:
    file.write(enhanced_html)

print("Enhanced visualization with custom styling has been saved.") 