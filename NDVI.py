import streamlit as st
import geopandas as gpd
import ee
import json
import os
import tempfile
import geemap.foliumap as geemap
from io import BytesIO
from datetime import datetime

from PIL import Image

import streamlit as st
from PIL import Image

# بارگذاری تصویر
image = Image.open("ABK.jpg")  # مسیر تصویر محلی خود را وارد کنید

# استفاده از Sidebar برای نمایش تصویر در بالای آن
# with st.sidebar:
#     st.image(image, use_container_width=True)  # استفاده از عرض کانتینر برای تنظیم اندازه تصویر
#     st.title("عنوان سایدبار")
#     st.write("متن یا هر محتوای دیگری می‌توانید در زیر تصویر قرار دهید.")

# استفاده از Sidebar برای نمایش تصویر در بالای آن
with st.sidebar:
    st.image(image, use_container_width=True)  # استفاده از عرض کانتینر برای تنظیم اندازه تصویر

    # تغییر رنگ عنوان سایدبار
    st.markdown('<h2 style="color: green;">شرکت مهندسین مشاور آسمان برج کارون</h2>', unsafe_allow_html=True)

    # تغییر رنگ متن
    # st.markdown('<p style="color: blue;">designed by iman e.bakhshipour</p>',
    #             unsafe_allow_html=True)


# مقداردهی اولیه GEE
service_account = "iman.e.bakhshipoor@gmail.com"
credentials = ee.ServiceAccountCredentials(service_account, "IMAN_GEE.json")
ee.Initialize(credentials)

# آپلود فایل ZIP شامل Shapefile
uploaded_file = st.file_uploader("آپلود یک شیپ فایل فشرده ‌شده (.zip)", type=["zip"])

# استفاده از Sidebar برای انتخاب تاریخ و مقیاس
with st.sidebar:
    start_date = st.date_input(
        "تاریخ شروع",
        value=datetime(2024, 1, 1),  # تاریخ پیش‌فرض
        min_value=datetime(2000, 1, 1),  # حداقل تاریخ مجاز
        max_value=datetime.today()  # حداکثر تاریخ مجاز

    )

    end_date = st.date_input(
        "تاریخ پایان",
        value=datetime(2024, 2, 15),  # تاریخ پیش‌فرض
        min_value=datetime(2000, 1, 1),  # حداقل تاریخ مجاز
        max_value=datetime.today()  # حداکثر تاریخ مجاز
    )

    # دریافت مقیاس (scale) از کاربر
    scale = st.number_input(
        "مقیاس (Scale)",
        min_value=10,  # حداقل مقدار مجاز
        max_value=100,  # حداکثر مقدار مجاز
        value=10,  # مقدار پیش‌فرض
        step=10  # گام تغییر مقدار
    )

if uploaded_file:
    try:
        gdf = gpd.read_file(BytesIO(uploaded_file.getvalue()))

        # بررسی و تبدیل CRS به WGS 84 (EPSG:4326)
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        st.write("CRS Shapefile (تبدیل‌شده):", gdf.crs)
        st.write("هندسه Shapefile:", gdf.geometry)

        # تبدیل به GeoJSON و FeatureCollection
        geojson = json.loads(gdf.to_json())
        features = [ee.Feature(feature) for feature in geojson["features"]]

        region = ee.FeatureCollection(features)

        # تبدیل تاریخ‌ها به اشیاء ee.Date
        start_date_ee = ee.Date.fromYMD(start_date.year, start_date.month, start_date.day)
        end_date_ee = ee.Date.fromYMD(end_date.year, end_date.month, end_date.day)

        # انتخاب آخرین تصویر Sentinel-2 بر اساس تاریخ‌های انتخاب‌شده
        image = ee.ImageCollection("COPERNICUS/S2") \
            .filterBounds(region) \
            .filterDate(start_date_ee, end_date_ee) \
            .sort("system:time_start", False) \
            .median()

        if image is None:
            st.error("هیچ تصویری از Sentinel-2 برای این منطقه و بازه زمانی یافت نشد.")
        else:
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            ndvi_clipped = ndvi.clip(region)

            # نمایش نقشه در بخش اصلی
            Map = geemap.Map(center=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom=8)
            Map.add_basemap("OpenStreetMap")
            Map.add_basemap("HYBRID")
            Map.addLayer(ndvi_clipped, {'min': -0.02, 'max': 0.7, 'palette': ['#f7fcf5', '#aedea7', '#37a055', '#00441b']}, "NDVI")
            Map.addLayer(region, {}, "مرز Shapefile")
            Map.to_streamlit(height=600)

            # دکمه دانلود GeoTIFF
            if st.button("دانلود NDVI به‌عنوان GeoTIFF"):
                with st.spinner("در حال تولید GeoTIFF... ⏳"):
                    temp_dir = tempfile.gettempdir()
                    temp_tiff_path = os.path.join(temp_dir, "ndvi_image.tif")

                    geemap.ee_export_image(ndvi_clipped, filename=temp_tiff_path, scale=scale, region=region.geometry())

                    with open(temp_tiff_path, "rb") as f:
                        tiff_bytes = BytesIO(f.read())

                    st.download_button(label="دانلود TIFF", data=tiff_bytes, file_name="ndvi_image.tif", mime="image/tiff")

    except Exception as e:
        st.error(f"خطا در پردازش Shapefile یا محاسبه NDVI: {str(e)}")
