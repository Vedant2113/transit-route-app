import streamlit as st
import networkx as nx
import pandas as pd
from datetime import datetime, timedelta, time
import calendar

# Load your Excel data
file_path = "merged_data.xlsx"
df = pd.read_excel(file_path)

# Use 'Depart Time' directly (already in datetime.time format)
df['Time'] = df['Depart Time']

# Streamlit UI
st.title("🚌 Bus Route Time Optimizer")

# Select operating day
days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
selected_day = st.selectbox("Select operating day", days_of_week, index=datetime.today().weekday())

# Filter data by selected day
df = df[df[selected_day] == 1]

# Add town to stop name for display
df['StopDisplay'] = df['Stop Location'] + " (" + df['Town'] + ")"
stop_display_map = dict(zip(df['StopDisplay'], df['Stop Location']))

# Limit time options to available departure times only
time_options = sorted(df['Time'].dropna().unique())
default_time = min(time_options) if time_options else time(6, 0)
user_time = st.selectbox("Select earliest available departure time", time_options, index=time_options.index(default_time) if default_time in time_options else 0)

# Initialize directed graph
G = nx.DiGraph()
valid_df = df[df['Time'].notnull()].sort_values(by=['Route', 'Time'])

for route in valid_df['Route'].unique():
    route_df = valid_df[valid_df['Route'] == route]
    stops = list(route_df[['Stop Location', 'Time', 'Town']].itertuples(index=False, name=None))

    for i in range(len(stops) - 1):
        stop_a, time_a, town_a = stops[i]
        stop_b, time_b, town_b = stops[i + 1]

        if not time_a or not time_b:
            continue

        if time_b > time_a:
            duration = datetime.combine(datetime.today(), time_b) - datetime.combine(datetime.today(), time_a)
        else:
            duration = (datetime.combine(datetime.today(), time_b) + timedelta(days=1)) - datetime.combine(datetime.today(), time_a)

        minutes = int(duration.total_seconds() / 60)
        G.add_edge(stop_a, stop_b, weight=minutes, route=route, depart=time_a, arrive=time_b, town=town_a)

# Function to find shortest path after a given start time
def find_shortest_path(start, end, start_time=None, round_trip=False):
    try:
        subgraph = G.copy()
        if start_time:
            edges_to_remove = [(u, v) for u, v, d in subgraph.edges(data=True) if d['depart'] < start_time]
            subgraph.remove_edges_from(edges_to_remove)

        path = nx.dijkstra_path(subgraph, start, end, weight='weight')
        total_time = sum(subgraph[path[i]][path[i + 1]]['weight'] for i in range(len(path) - 1))
        result = [(path[i], subgraph[path[i]][path[i+1]]['town'], subgraph[path[i]][path[i+1]]['route'], subgraph[path[i]][path[i+1]]['depart'].strftime("%I:%M %p")) for i in range(len(path)-1)]
        result.append((path[-1], '-', '-', '-'))

        if round_trip:
            return_path = nx.dijkstra_path(subgraph, end, start, weight='weight')
            return_time = sum(subgraph[return_path[i]][return_path[i + 1]]['weight'] for i in range(len(return_path) - 1))
            return_result = [(return_path[i], subgraph[return_path[i]][return_path[i+1]]['town'], subgraph[return_path[i]][return_path[i+1]]['route'], subgraph[return_path[i]][return_path[i+1]]['depart'].strftime("%I:%M %p")) for i in range(len(return_path)-1)]
            return_result.append((return_path[-1], '-', '-', '-'))
            return result, total_time, return_result, return_time
        else:
            return result, total_time
    except nx.NetworkXNoPath:
        return f"No path found between {start} and {end}"

# Select start and end
all_displays = sorted(df['StopDisplay'].dropna().unique())
start_display = st.selectbox("Select starting stop", all_displays, index=0)
end_display = st.selectbox("Select destination stop", all_displays, index=1)
start = stop_display_map[start_display]
end = stop_display_map[end_display]

trip_type = st.radio("Trip type", options=["One-way", "Round-trip"])

if st.button("Find Shortest Route"):
    if trip_type == "One-way":
        result = find_shortest_path(start, end, start_time=user_time, round_trip=False)
        if isinstance(result, str):
            st.error(result)
        else:
            route, duration = result
            st.success(f"Shortest one-way trip takes {duration} minutes")
            st.write("### Route Details:")
            for stop, town, route_num, depart in route:
                st.write(f"➡️ {stop} ({town}) via Route {route_num} at {depart}")
    else:
        result = find_shortest_path(start, end, start_time=user_time, round_trip=True)
        if isinstance(result, str):
            st.error(result)
        else:
            out_route, out_time, return_route, return_time = result
            st.success(f"Round-trip: {out_time} mins out, {return_time} mins back")
            st.write("### Outbound Route:")
            for stop, town, route_num, depart in out_route:
                st.write(f"➡️ {stop} ({town}) via Route {route_num} at {depart}")
            st.write("### Return Route:")
            for stop, town, route_num, depart in return_route:
                st.write(f"⬅️ {stop} ({town}) via Route {route_num} at {depart}")
