


import streamlit as st
import geopandas as gpd
import ee
import json
import os  # افزودن این خط
import tempfile
import geemap.foliumap as geemap
from io import BytesIO

st.title('Aseman Borj Karun',anchor=None)
st.subheader('designed by: iman e.bakhshipour')



# مقداردهی اولیه GEE
service_account = "iman.e.bakhshipoor@gmail.com"
credentials = ee.ServiceAccountCredentials(service_account, "IMAN_GEE.json")
ee.Initialize(credentials)

# آپلود فایل ZIP شامل Shapefile
uploaded_file = st.file_uploader("Upload a zipped Shapefile (.zip)", type=["zip"])

if uploaded_file:
    try:
        gdf = gpd.read_file(BytesIO(uploaded_file.getvalue()))

        # بررسی و تبدیل CRS به WGS 84 (EPSG:4326)
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        st.write("Shapefile CRS (Converted):", gdf.crs)
        st.write("Shapefile Geometry:", gdf.geometry)

        # تبدیل به GeoJSON و FeatureCollection
        geojson = json.loads(gdf.to_json())
        features = [ee.Feature(feature) for feature in geojson["features"]]

        region = ee.FeatureCollection(features)

        # انتخاب آخرین تصویر Sentinel-2
        image = ee.ImageCollection("COPERNICUS/S2") \
            .filterBounds(region) \
            .filterDate("2024-01-01", "2024-02-15") \
            .sort("system:time_start", False) \
            .first()

        if image is None:
            st.error("No Sentinel-2 images found for this region and time range.")
        else:
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            ndvi_clipped = ndvi.clip(region)

            # نمایش نقشه
            Map = geemap.Map(center=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom=8)
            Map.add_basemap("OpenStreetMap")
            Map.add_basemap("HYBRID")
            Map.addLayer(ndvi_clipped, {'min': -0.02, 'max': 0.7, 'palette': ['#f7fcf5', '#aedea7', '#37a055', '#00441b']}, "NDVI")
            Map.addLayer(region, {}, "Shapefile Boundary")
            Map.to_streamlit(height=600)

            # دکمه دانلود GeoTIFF
            if st.button("Download NDVI as GeoTIFF"):
                with st.spinner("Generating GeoTIFF... ⏳"):
                    temp_dir = tempfile.gettempdir()
                    temp_tiff_path = os.path.join(temp_dir, "ndvi_image.tif")

                    geemap.ee_export_image(ndvi_clipped, filename=temp_tiff_path, scale=10, region=region.geometry())

                    with open(temp_tiff_path, "rb") as f:
                        tiff_bytes = BytesIO(f.read())

                    st.download_button(label="Download TIFF", data=tiff_bytes, file_name="ndvi_image.tif", mime="image/tiff")

    except Exception as e:
        st.error(f"Error processing shapefile or NDVI calculation: {str(e)}")
