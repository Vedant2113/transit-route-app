import streamlit as st
import networkx as nx
import pandas as pd
from datetime import datetime, timedelta, time

# Load your Excel data
file_path = "merged_data.xlsx"
df = pd.read_excel(file_path)

# Fix the time format
df['Time'] = pd.to_datetime(df['DepartTime'], errors='coerce').dt.time

# Streamlit UI
st.title("🚌 Bus Route Time Optimizer")

# Select operating day
days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
selected_day = st.selectbox("Select operating day", days_of_week, index=datetime.today().weekday())

# Filter data by selected day
df = df[df[selected_day] == 1]

# Add town to stop name for display, remove (Loop)
df['StopDisplay'] = df['Stop Location'].str.replace(r'\s*\(Loop\)', '', regex=True).fillna('Unknown Stop') + " (" + df['Town'].fillna('Unknown Town') + ")"
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
    route_df = df[df['Route'] == route].copy()

    if route == '68':
        hospital_times = route_df[route_df['Stop Location'] == 'Canton-Potsdam Hospital']['Time']
        if hospital_times.empty:
            route_df = route_df[route_df['Stop Location'] != 'Canton-Potsdam Hospital']

    route_df = route_df.sort_values(by='Time')
    for i in range(len(route_df) - 1):
        row_a = route_df.iloc[i]
        row_b = route_df.iloc[i + 1]
        time_a = row_a['Time']
        time_b = row_b['Time']
        dt_a = datetime.combine(datetime.today(), time_a)
        dt_b = datetime.combine(datetime.today(), time_b)
        if dt_b < dt_a:
            dt_b += timedelta(days=1)
        duration = (dt_b - dt_a).total_seconds() / 60.0
        if duration >= 0:
            G.add_edge(
                (row_a['Stop Location'], time_a),
                (row_b['Stop Location'], time_b),
                weight=duration,
                route=route,
                town=row_a['Town']
            )

# Add transfer edges (waiting at same stop)
for stop, group in df.groupby('Stop Location'):
    times = sorted(group['Time'].unique())
    for i in range(len(times) - 1):
        t1 = times[i]
        t2 = times[i + 1]
        dt1 = datetime.combine(datetime.today(), t1)
        dt2 = datetime.combine(datetime.today(), t2)
        if dt2 < dt1:
            dt2 += timedelta(days=1)
        wait = (dt2 - dt1).total_seconds() / 60.0
        if wait > 0:
            G.add_edge(
                (stop, t1),
                (stop, t2),
                weight=wait,
                route='Transfer',
                town=group.iloc[0]['Town']
            )

# Find shortest path function
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
        action = {
            'stop': stop,
            'town': edge['town'],
            'route': edge['route'],
            'time': t.strftime("%H:%M"),
            'transfer': edge['route'] == 'Transfer'
        }
        result.append(action)

    final_stop, final_time = shortest_path[-1]
    final_town = df[df['Stop Location'] == final_stop]['Town'].iloc[0] if not df[df['Stop Location'] == final_stop].empty else '-'
    result.append({
        'stop': final_stop,
        'town': final_town,
        'route': result[-1]['route'] if result else '-',
        'time': final_time.strftime("%H:%M"),
        'transfer': False
    })

    return result, int(shortest_cost)

# User input
all_displays = sorted(df['StopDisplay'].dropna().unique())
start_display = st.selectbox("Select starting stop", all_displays, index=0)
end_display = st.selectbox("Select destination stop", all_displays, index=1)
start = stop_display_map[start_display]
end = stop_display_map[end_display]

trip_type = st.radio("Trip type", options=["One-way"])
show_all = st.checkbox("Show all possible routes without selecting time")

# Show all available routes in readable format
if show_all:
    found_any = False
    for s_time in sorted([t for s, t in G.nodes if s == start]):
        result = find_transfer_path(start, end, s_time)
        if isinstance(result, tuple):
            path, duration = result
            found_any = True
            st.markdown(f"---\n**Start Time:** {s_time.strftime('%H:%M')}  \n**Trip Duration:** {duration} minutes")

            previous_route = None
            for step in path:
                if step['transfer']:
                    st.markdown(f"🔁 **Transfer at {step['stop']} ({step['town']})** — wait and take Route **{path[path.index(step)+1]['route']}** at **{step['time']}**")
                else:
                    transfer_notice = f" (Transfer to Route {step['route']})" if previous_route and step['route'] != previous_route else ""
                    st.markdown(f"➡️ **{step['stop']} ({step['town']})** via Route **{step['route']}**{transfer_notice} at **{step['time']}**")
                previous_route = step['route']
    if not found_any:
        st.warning("No available routes found from this stop to the destination.")

# Show single route based on selected time
elif st.button("Find Shortest Time"):
    result = find_transfer_path(start, end, user_time)
    if isinstance(result, str):
        st.error(result)
    else:
        route, duration = result
        st.success(f"Trip time: {duration} minutes")
        st.write("### Route Details:")
        previous_route = None
        for step in route:
            if step['transfer']:
                st.markdown(f"🔁 **Transfer at {step['stop']} ({step['town']})** — wait and take Route **{route[route.index(step)+1]['route']}** at **{step['time']}**")
            else:
                transfer_notice = f" (Transfer to Route {step['route']})" if previous_route and step['route'] != previous_route else ""
                st.write(f"➡️ {step['stop']} ({step['town']}) via Route {step['route']}{transfer_notice} at {step['time']}")
            previous_route = step['route']
