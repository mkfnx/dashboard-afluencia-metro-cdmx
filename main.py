import streamlit as st
import pandas as pd
import unidecode
import geopandas as gpd
from datetime import datetime, date
from bs4 import BeautifulSoup

# Function to extract NOMBRE and LINEA from HTML
def extract_info_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    nombre = soup.find('td', text='NOMBRE').find_next_sibling('td').text.strip()
    linea = soup.find('td', text='LINEA').find_next_sibling('td').text.strip()
    return nombre, linea

def clean_station_name(name):
    cleaned = unidecode.unidecode(name.lower().strip())
    # Handle common replacements
    replacements = {
        'terminal aerea': 'terminal area',
        'lazaro cardenas': 'l. cardenas',
        'ninos heroes/poder judicial cdmx': 'ninos heroes',
        'uam azcapotzalco': 'uam-azcapotzalco',
        'mixhiuca': 'mixiuhca'
        # Add more replacements as needed
    }
    for old, new in replacements.items():
        if old in cleaned:
            cleaned = cleaned.replace(old, new)
    return cleaned

def load_and_preprocess_data():
    df_stc = pd.read_csv('afluenciastc_simple_02_2024.csv')
    df_stc['fecha'] = pd.to_datetime(df_stc['fecha'])
    df_stc['year_month'] = df_stc['fecha'].dt.strftime('%Y-%m')
    df_stc['estacion_clean'] = df_stc['estacion'].apply(clean_station_name)
    df_stc['linea_clean'] = df_stc['linea'].apply(lambda x: unidecode.unidecode(x.lower().strip()))
    return df_stc

def load_and_process_kml_data():
    gdf = gpd.read_file('stc.kml', driver='KML')
    stations_info = gdf[['Name', 'geometry', 'Description']].copy()
    stations_info['lat'] = stations_info['geometry'].y
    stations_info['lon'] = stations_info['geometry'].x
    stations_info[['estacion', 'linea']] = stations_info['Description'].apply(lambda x: pd.Series(extract_info_from_html(x)))
    stations_info['estacion_clean'] = stations_info['estacion'].apply(clean_station_name)
    stations_info['linea_clean'] = stations_info['linea'].apply(lambda x: 'linea ' + x.lstrip('0').lower())
    return stations_info.drop(columns=['Name', 'geometry', 'Description'])

def filter_data(df, linea, start_date, end_date):
    start_date_str = start_date.strftime("%Y-%m")
    end_date_str = end_date.strftime("%Y-%m")
    return df[
        (df['linea_clean'] == linea.lower()) &
        (df['year_month'] >= start_date_str) &
        (df['year_month'] <= end_date_str)
    ].reset_index()

def create_line_chart(filtered_df_stations):
    total_afluencia_per_station = filtered_df_stations.groupby('estacion_clean')['afluencia'].sum().sort_values(ascending=False)
    top_5_stations = total_afluencia_per_station.head(5).index.tolist()
    pivoted_df = filtered_df_stations.pivot(index='year_month', columns='estacion_clean', values='afluencia')
    pivoted_df_top_5 = pivoted_df[top_5_stations]
    pivoted_df_top_5['Total'] = pivoted_df.sum(axis=1)
    st.line_chart(pivoted_df_top_5)

def display_map_and_table(filtered_df_stations, linea_stc):
    stations_aggregate = filtered_df_stations.groupby('estacion_clean').agg({
        'afluencia': 'sum',
        'lat': 'first',
        'lon': 'first'
    }).reset_index()
    stations_aggregate['size'] = stations_aggregate['afluencia'] / stations_aggregate['afluencia'].max() * 1000
    st.write(stations_aggregate)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Estaciones de la {linea_stc}")
        st.map(stations_aggregate, latitude='lat', longitude='lon', size='size', zoom=11)
    
    with col2:
        st.subheader(f"Afluencia por Estación - {linea_stc}")
        station_afluencia_table = stations_aggregate[['estacion_clean', 'afluencia']].sort_values('afluencia', ascending=False)
        station_afluencia_table['afluencia'] = station_afluencia_table['afluencia'].apply(lambda x: f"{int(x):,}" if pd.notnull(x) else x)
        station_afluencia_table.columns = ['Estación', 'Afluencia']
        st.table(station_afluencia_table.set_index('Estación'))

def main():
    st.title('Afluencia Metro CDMX')

    df_stc = load_and_preprocess_data()
    stations_info = load_and_process_kml_data()

    lineas_stc = df_stc['linea_clean'].unique()
    selected_linea_stc = st.selectbox('Línea', lineas_stc)

    df_filtered_by_line = df_stc[(df_stc['linea_clean'] == unidecode.unidecode(selected_linea_stc.lower().strip())) & (df_stc['afluencia'] > 0)]
    min_date = df_filtered_by_line['fecha'].min()
    max_date = df_filtered_by_line['fecha'].max()

    start_date_stc = st.date_input("Fecha de inicio", min_value=min_date, max_value=max_date, value=min_date, key='start_date_stc')
    end_date_stc = st.date_input("Fecha de fin", min_value=min_date, max_value=max_date, value=max_date, key='end_date_stc')

    df_month_estacion_stc = df_stc.groupby(['year_month', 'linea_clean', 'estacion_clean'])['afluencia'].sum().reset_index()
    df_month_estacion_stc = df_month_estacion_stc.merge(stations_info[['estacion_clean', 'linea_clean', 'lat', 'lon']], on=['estacion_clean', 'linea_clean'], how='left')

    filtered_df_stations_stc = filter_data(df_month_estacion_stc, selected_linea_stc, start_date_stc, end_date_stc)

    create_line_chart(filtered_df_stations_stc)
    display_map_and_table(filtered_df_stations_stc, selected_linea_stc)

if __name__ == "__main__":
    main()
