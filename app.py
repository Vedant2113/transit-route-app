import streamlit as st
import networkx as nx
import pandas as pd
from datetime import datetime, timedelta

# Load your Excel data
file_path = r"C:\Users\patel\Downloads\IA_560_Project\merged_data.xlsx"
df = pd.read_excel(file_path)

# Use 'Depart Time' directly (already in datetime.time format)
df['Time'] = df['Depart Time']

# Initialize directed graph
G = nx.DiGraph()

# Filter and sort valid data
valid_df = df[df['Time'].notnull()].sort_values(by=['Route', 'Time'])

# Build the graph: edges represent trips between sequential stops
for route in valid_df['Route'].unique():
    route_df = valid_df[valid_df['Route'] == route]
    stops = list(route_df[['Stop Location', 'Time']].itertuples(index=False, name=None))

    for i in range(len(stops) - 1):
        stop_a, time_a = stops[i]
        stop_b, time_b = stops[i + 1]

        if not time_a or not time_b:
            continue

        # Calculate travel time in minutes
        if time_b > time_a:
            duration = datetime.combine(datetime.today(), time_b) - datetime.combine(datetime.today(), time_a)
        else:
            duration = (datetime.combine(datetime.today(), time_b) + timedelta(days=1)) - datetime.combine(datetime.today(), time_a)

        minutes = int(duration.total_seconds() / 60)
        G.add_edge(stop_a, stop_b, weight=minutes, route=route, depart=time_a, arrive=time_b)

# Function to find shortest path
def find_shortest_path(start, end, round_trip=False):
    try:
        path = nx.dijkstra_path(G, start, end, weight='weight')
        total_time = sum(G[path[i]][path[i + 1]]['weight'] for i in range(len(path) - 1))
        result = [(path[i], G[path[i]][path[i+1]]['route'], G[path[i]][path[i+1]]['depart'].strftime("%I:%M %p")) for i in range(len(path)-1)]
        result.append((path[-1], '-', '-'))

        if round_trip:
            return_path = nx.dijkstra_path(G, end, start, weight='weight')
            return_time = sum(G[return_path[i]][return_path[i + 1]]['weight'] for i in range(len(return_path) - 1))
            return_result = [(return_path[i], G[return_path[i]][return_path[i+1]]['route'], G[return_path[i]][return_path[i+1]]['depart'].strftime("%I:%M %p")) for i in range(len(return_path)-1)]
            return_result.append((return_path[-1], '-', '-'))
            return result, total_time, return_result, return_time
        else:
            return result, total_time
    except nx.NetworkXNoPath:
        return f"No path found between {start} and {end}"

# Streamlit UI
def transit_app():
    st.title("🚌 Bus Route Time Optimizer")

    all_stops = sorted(df['Stop Location'].dropna().unique())
    start = st.selectbox("Select starting stop", all_stops, index=0)
    end = st.selectbox("Select destination stop", all_stops, index=1)
    trip_type = st.radio("Trip type", options=["One-way", "Round-trip"])

    if st.button("Find Shortest Route"):
        if trip_type == "One-way":
            result = find_shortest_path(start, end, round_trip=False)
            if isinstance(result, str):
                st.error(result)
            else:
                route, duration = result
                st.success(f"Shortest one-way trip takes {duration} minutes")
                st.write("### Route Details:")
                for stop, route_num, depart in route:
                    st.write(f"➡️ {stop} via Route {route_num} at {depart}")
        else:
            result = find_shortest_path(start, end, round_trip=True)
            if isinstance(result, str):
                st.error(result)
            else:
                out_route, out_time, return_route, return_time = result
                st.success(f"Round-trip: {out_time} mins out, {return_time} mins back")
                st.write("### Outbound Route:")
                for stop, route_num, depart in out_route:
                    st.write(f"➡️ {stop} via Route {route_num} at {depart}")
                st.write("### Return Route:")
                for stop, route_num, depart in return_route:
                    st.write(f"⬅️ {stop} via Route {route_num} at {depart}")

# Run the app
transit_app()
