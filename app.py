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
df['StopDisplay'] = df['Stop Location'].str.replace(r'\s*\(Loop\)', '', regex=True) + " (" + df['Town'] + ")"
stop_display_map = dict(zip(df['StopDisplay'], df['Stop Location']))

# Limit time options to available departure times only
time_options = sorted(df['Time'].dropna().unique())
default_time = min(time_options) if time_options else time(6, 0)
user_time = st.time_input("Select earliest available departure time", value=default_time)

# Build a time-expanded graph (stop, time) nodes
G = nx.DiGraph()
df = df[df['Time'].notnull()].sort_values(by=['Stop Location', 'Time'])

# Add edges for travel along the same route
for route in df['Route'].unique():
    route_df = df[(df['Route'] == route)].copy()
    if route == '68':
        hospital_times = df[(df['Route'] == '68') & (df['Stop Location'] == 'Canton-Potsdam Hospital')]['Time']
        if hospital_times.empty:
            route_df = route_df[route_df['Stop Location'] != 'Canton-Potsdam Hospital']
        route_df = route_df.sort_values(by='Time')
    grouped = route_df.groupby('Route')
    for _, group in grouped:
        for i in range(len(group) - 1):
            row_a = group.iloc[i]
            row_b = group.iloc[i + 1]
            time_a = row_a['Time']
            time_b = row_b['Time']
            duration = (datetime.combine(datetime.today(), time_b) - datetime.combine(datetime.today(), time_a)).seconds / 60.0
            if duration >= 0:
                G.add_edge(
                    (row_a['Stop Location'], time_a),
                    (row_b['Stop Location'], time_b),
                    weight=duration,
                    route=route,
                    town=row_a['Town']
                )

# Add transfer edges at the same stop (wait time for next bus)
for stop, group in df.groupby('Stop Location'):
    times = sorted(group['Time'].unique())
    for i in range(len(times) - 1):
        t1 = times[i]
        t2 = times[i + 1]
        wait = (datetime.combine(datetime.today(), t2) - datetime.combine(datetime.today(), t1)).seconds / 60.0
        if wait > 0:
            G.add_edge(
                (stop, t1),
                (stop, t2),
                weight=wait,
                route='Transfer',
                town=group.iloc[0]['Town']
            )

# Find shortest path with transfers allowed
def find_transfer_path(start, end, start_time):
    candidates = [(s, t) for s, t in G.nodes if s == start and t >= start_time]
    targets = [(s, t) for s, t in G.nodes if s == end]

    shortest_path = None
    shortest_cost = float('inf')

    for start_node in candidates:
        for end_node in targets:
            try:
                path = nx.dijkstra_path(G, start_node, end_node, weight='weight')
                cost = sum(G[path[i]][path[i + 1]]['weight'] for i in range(len(path) - 1))
                if cost < shortest_cost:
                    shortest_cost = cost
                    shortest_path = path
            except nx.NetworkXNoPath:
                continue

    if not shortest_path:
        return "No path found"

    result = []
    for i in range(len(shortest_path) - 1):
        stop, t = shortest_path[i]
        next_stop, t2 = shortest_path[i + 1]
        edge = G[shortest_path[i]][shortest_path[i + 1]]
        result.append({
            'stop': stop,
            'town': edge['town'],
            'route': edge['route'],
            'time': t.strftime("%I:%M %p"),
        })

    # Add final stop with actual route, time, and town
    final_stop, final_time = shortest_path[-1]
    final_town = df[df['Stop Location'] == final_stop]['Town'].iloc[0] if not df[df['Stop Location'] == final_stop].empty else '-'
    result.append({
        'stop': final_stop,
        'town': final_town,
        'route': result[-1]['route'] if result else '-',
        'time': final_time.strftime("%I:%M %p")
    })

    return result, int(shortest_cost)

# Select start and end
all_displays = sorted(df['StopDisplay'].dropna().unique())
start_display = st.selectbox("Select starting stop", all_displays, index=0)
end_display = st.selectbox("Select destination stop", all_displays, index=1)
start = stop_display_map[start_display]
end = stop_display_map[end_display]

trip_type = st.radio("Trip type", options=["One-way"])

show_all = st.checkbox("Show all possible routes without selecting time")

if show_all:
    routes_table = []
    for s_time in sorted([t for s, t in G.nodes if s == start]):
        result = find_transfer_path(start, end, s_time)
        if isinstance(result, tuple):
            path, duration = result
            routes_table.append({
                'Start Time': s_time.strftime("%I:%M %p"),
                'Duration (min)': duration,
                'Transfers': sum(1 for i in range(1, len(path)) if path[i]['route'] != path[i-1]['route'])
            })
    if routes_table:
        st.dataframe(pd.DataFrame(routes_table))
    else:
        st.warning("No available routes found from this stop to the destination.")

elif st.button("Find Shortest Route"):
    result = find_transfer_path(start, end, user_time)
    if isinstance(result, str):
        st.error(result)
    else:
        route, duration = result
        st.success(f"Trip time: {duration} minutes")
        st.write("### Route Details:")
        previous_route = None
        for step in route:
            transfer_notice = " (Transfer)" if previous_route and step['route'] != previous_route else ""
            st.write(f"➡️ {step['stop']} ({step['town']}) via Route {step['route']}{transfer_notice} at {step['time']}")
            previous_route = step['route']
