import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from streamlit_folium import st_folium
from google.cloud import bigquery
from datetime import datetime

st.set_page_config(page_title="Animal Shelter Dashboard", layout="wide")

client = bigquery.Client(project="san-jose-data-project")
query = """
SELECT * FROM `san-jose-data-project.DM.processed_animal_shelter`
LIMIT 1000
"""
data = client.query(query).to_dataframe()

data['IntakeDate'] = pd.to_datetime(data['IntakeDate'], errors='coerce')
data['OutcomeDate'] = pd.to_datetime(data['OutcomeDate'], errors='coerce')
data['LastUpdate'] = pd.to_datetime(data['LastUpdate'], errors='coerce')
data['DOB'] = pd.to_datetime(data['DOB'], errors='coerce')
data['IntakeMonth'] = data['IntakeDate'].dt.to_period('M').dt.to_timestamp()
data['DaysInShelter'] = (data['OutcomeDate'] - data['IntakeDate']).dt.days

remaining_count = data['OutcomeDate'].isna().sum()

st.title("Animal Shelter Dashboard")
st.subheader("Overall Statistics")

st.markdown("### Filters")
all_animal_types = sorted(data['AnimalType'].dropna().unique())
selected_animal_types = st.multiselect("Select Animal Types:", options=all_animal_types, default=all_animal_types)
all_sexes = sorted(data['Sex'].dropna().unique())
selected_sexes = st.multiselect("Select Sex:", options=all_sexes, default=all_sexes)
all_intake_conditions = sorted(data['IntakeCondition'].dropna().unique())
selected_intake_conditions = st.multiselect("Select Intake Conditions:", options=all_intake_conditions, default=all_intake_conditions)
min_intake_date = data['IntakeDate'].min().date() if pd.notnull(data['IntakeDate'].min()) else datetime.today().date()
max_intake_date = data['IntakeDate'].max().date() if pd.notnull(data['IntakeDate'].max()) else datetime.today().date()
selected_date_range = st.date_input("Select Intake Date Range:", value=(min_intake_date, max_intake_date))

filtered_data = data.copy()
if selected_animal_types:
    filtered_data = filtered_data[filtered_data['AnimalType'].isin(selected_animal_types)]
if selected_sexes:
    filtered_data = filtered_data[filtered_data['Sex'].isin(selected_sexes)]
if selected_intake_conditions:
    filtered_data = filtered_data[filtered_data['IntakeCondition'].isin(selected_intake_conditions)]
if selected_date_range and isinstance(selected_date_range, tuple):
    start_date, end_date = selected_date_range
    filtered_data = filtered_data[
        (filtered_data['IntakeDate'].dt.date >= start_date) &
        (filtered_data['IntakeDate'].dt.date <= end_date)
    ]
if filtered_data.empty:
    st.warning("No results found for these filter selections. Displaying default (all data) instead.")
    filtered_data = data.copy()

st.subheader("Monthly Intake Trend (Filtered Data)")
monthly_intake = filtered_data.groupby('IntakeMonth').size().reset_index(name='Count')
fig, ax = plt.subplots(figsize=(10, 5))
sns.lineplot(x='IntakeMonth', y='Count', data=monthly_intake, marker='o', ax=ax)
ax.set_title("Monthly Intake Trend")
ax.set_xlabel("Intake Month")
ax.set_ylabel("Number of Intakes")
plt.xticks(rotation=45)
st.pyplot(fig)

st.subheader("Animal Type Frequency (Filtered Data)")
animal_counts = filtered_data['AnimalType'].value_counts().reset_index()
animal_counts.columns = ['AnimalType', 'Count']
fig2, ax2 = plt.subplots(figsize=(8, 5))
sns.barplot(x='AnimalType', y='Count', data=animal_counts, palette="viridis", ax=ax2)
ax2.set_title("Frequency of Animal Types")
ax2.set_xlabel("Animal Type")
ax2.set_ylabel("Count")
plt.xticks(rotation=45)
st.pyplot(fig2)

st.subheader("Distribution of Days in Shelter (Filtered Data)")
if 'DaysInShelter' in filtered_data.columns and filtered_data['DaysInShelter'].dropna().shape[0] > 0:
    fig3, ax3 = plt.subplots(figsize=(10, 5))
    sns.histplot(filtered_data['DaysInShelter'].dropna(), bins=30, kde=True, ax=ax3)
    ax3.set_title("Days in Shelter Distribution")
    ax3.set_xlabel("Days in Shelter")
    ax3.set_ylabel("Frequency")
    st.pyplot(fig3)
else:
    st.write("No Days in Shelter data available.")

st.subheader("Shelter Intake Locations (Map)")
if 'Latitude' in filtered_data.columns and 'Longitude' in filtered_data.columns:
    center_lat = filtered_data['Latitude'].mean() if not filtered_data['Latitude'].isna().all() else 37.3382
    center_lon = filtered_data['Longitude'].mean() if not filtered_data['Longitude'].isna().all() else -121.8863
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
    for idx, row in filtered_data.dropna(subset=['Latitude', 'Longitude']).iterrows():
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=3,
            popup=f"Animal Type: {row['AnimalType']}",
            color='blue',
            fill=True,
            fill_color='blue'
        ).add_to(m)
    remaining_by_zip = filtered_data[filtered_data['OutcomeDate'].isna()].groupby('ZipCode', as_index=False).agg({
        'Latitude': 'first',
        'Longitude': 'first',
        'AnimalID': 'count'
    }).rename(columns={'AnimalID': 'remaining_count'})
    for idx, row in remaining_by_zip.iterrows():
        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=f"ZipCode: {row['ZipCode']} - Remaining animals: {row['remaining_count']}",
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
    st_folium(m, width=700)
else:
    st.write("Geolocation data not available.")
