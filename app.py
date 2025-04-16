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
st.set_page_config(layout="wide")
st.markdown("""
    <style>
        body {
            background-image: url('slcPTCover11.jpg');
            background-size: cover;
            background-position: center;
            font-family: 'Segoe UI', sans-serif;
        }
        .main > div {
            display: flex;
            justify-content: center;
            padding: 2rem 1rem;
        }
        .block-container {
            max-width: 880px;
            background: #073531;
            padding: 2rem;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            color: white;
        }
        .stSelectbox > div > label, .stRadio > div > label, .stTimeInput > div > label, .stCheckbox > div > label {
            color: white !important;
            font-weight: 600;
        }
        .stButton button {
            width: 100%;
            background-color: #f6c700;
            color: black;
            border-radius: 6px;
            font-size: 1rem;
            padding: 0.75rem;
            margin-top: 1.25rem;
        }
        .stButton button:hover {
            background-color: #dab700;
        }
        .route-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .route-selectbox {
            flex-grow: 1;
        }
        .swap-button {
            margin: 0 auto;
            background: #f6c700;
            color: black;
            font-weight: bold;
            border: none;
            border-radius: 8px;
            font-size: 20px;
            padding: 0.5rem 1.5rem;
            display: block;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🚌 Bus Route Time Optimizer")

# Select operating day
days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
selected_day = st.selectbox("Select operating day", days_of_week, index=datetime.today().weekday())

# Filter data by selected day
df = df[df[selected_day] == 1]

# Add town to stop name for display
df['StopDisplay'] = df['Stop Location'].str.replace(r'\s*\(Loop\)', '', regex=True).fillna('Unknown Stop') + " (" + df['Town'].fillna('Unknown Town') + ")"
stop_display_map = dict(zip(df['StopDisplay'], df['Stop Location']))
reverse_stop_display_map = {v: k for k, v in stop_display_map.items()}
all_displays = sorted(df['StopDisplay'].dropna().unique())

# Time selection
time_options = sorted(df['Time'].dropna().unique())
default_time = min(time_options) if time_options else time(6, 0)
user_time = st.time_input("Select earliest available departure time", value=default_time)

# Session state defaults
if 'start_display' not in st.session_state:
    st.session_state['start_display'] = all_displays[0]
if 'end_display' not in st.session_state:
    st.session_state['end_display'] = all_displays[1]

# Route selectors
col1, col2, col3 = st.columns([4, 2, 4])
with col1:
    start_display = st.selectbox("Select starting stop", all_displays, index=all_displays.index(st.session_state['start_display']), key="start")
with col2:
    if st.button("⇄ Swap Stops", key="swap_button"):
        st.session_state['start_display'], st.session_state['end_display'] = st.session_state['end_display'], st.session_state['start_display']
with col3:
    end_display = st.selectbox("Select destination stop", all_displays, index=all_displays.index(st.session_state['end_display']), key="end")

st.session_state['start_display'] = start_display
st.session_state['end_display'] = end_display
start = stop_display_map[start_display]
end = stop_display_map[end_display]

trip_type = st.radio("Trip type", options=["One-way"])
show_all = st.checkbox("Show all possible routes without selecting time")

# Graph build
G = nx.DiGraph()
df = df[df['Time'].notnull()].sort_values(by=['Stop Location', 'Time'])

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
        dt_a = datetime.combine(datetime.today(), row_a['Time'])
        dt_b = datetime.combine(datetime.today(), row_b['Time'])
        if dt_b < dt_a:
            dt_b += timedelta(days=1)
        duration = (dt_b - dt_a).total_seconds() / 60.0
        if duration >= 0:
            G.add_edge((row_a['Stop Location'], row_a['Time']), (row_b['Stop Location'], row_b['Time']), weight=duration, route=route, town=row_a['Town'])

# Add transfer waits
for stop, group in df.groupby('Stop Location'):
    times = sorted(group['Time'].unique())
    for i in range(len(times) - 1):
        dt1 = datetime.combine(datetime.today(), times[i])
        dt2 = datetime.combine(datetime.today(), times[i + 1])
        if dt2 < dt1:
            dt2 += timedelta(days=1)
        wait = (dt2 - dt1).total_seconds() / 60.0
        if wait > 0:
            G.add_edge((stop, times[i]), (stop, times[i + 1]), weight=wait, route='Transfer', town=group.iloc[0]['Town'])

# Shortest path search
def find_transfer_path(start, end, start_time):
    candidates = [(s, t) for s, t in G.nodes if s == start and t >= start_time]
    targets = [(s, t) for s, t in G.nodes if s == end]
    shortest_path, shortest_cost, best_start_time = None, float('inf'), None

    for s_node in candidates:
        for e_node in targets:
            try:
                path = nx.dijkstra_path(G, s_node, e_node, weight='weight')
                cost = sum(G[path[i]][path[i + 1]]['weight'] for i in range(len(path) - 1))
                if cost < shortest_cost:
                    shortest_path, shortest_cost, best_start_time = path, cost, s_node[1]
            except nx.NetworkXNoPath:
                continue

    if not shortest_path:
        return "No path found"

    result = []
    for i in range(len(shortest_path) - 1):
        stop, t = shortest_path[i]
        edge = G[shortest_path[i]][shortest_path[i + 1]]
        result.append({
            'stop': stop,
            'town': edge['town'],
            'route': edge['route'],
            'time': t.strftime("%H:%M"),
            'transfer': edge['route'] == 'Transfer'
        })
    final_stop, final_time = shortest_path[-1]
    final_town = df[df['Stop Location'] == final_stop]['Town'].iloc[0] if not df[df['Stop Location'] == final_stop].empty else '-'
    result.append({
        'stop': final_stop,
        'town': final_town,
        'route': result[-1]['route'] if result else '-',
        'time': final_time.strftime("%H:%M"),
        'transfer': False
    })
    return result, int(shortest_cost), best_start_time

# Output results
if show_all:
    found = False
    shown = set()
    for s_time in sorted([t for s, t in G.nodes if s == start]):
        result = find_transfer_path(start, end, s_time)
        if isinstance(result, tuple):
            path, duration, correct_start_time = result
            sig = tuple((s['stop'], s['route'], s['time']) for s in path)
            if sig in shown: continue
            shown.add(sig)
            found = True
            st.write(f"🕒 **Start Time:** {correct_start_time.strftime('%H:%M')}")
            st.write(f"⏱️ **Trip Duration:** {duration} minutes")
            prev_route = None
            for s in path:
                if s['transfer']:
                    st.write(f"🔁 Transfer at {s['stop']} ({s['town']}) — wait and take Route {path[path.index(s)+1]['route']} at {s['time']}")
                else:
                    trans = f" (Transfer to Route {s['route']})" if prev_route and s['route'] != prev_route else ""
                    st.write(f"➡️ {s['stop']} ({s['town']}) via Route {s['route']}{trans} at {s['time']}")
                prev_route = s['route']
            st.markdown("---")
    if not found:
        st.warning("No available routes found from this stop to the destination.")
elif st.button("Find Shortest Time"):
    result = find_transfer_path(start, end, user_time)
    if isinstance(result, str):
        st.error(result)
    else:
        route, duration, correct_start_time = result
        st.success(f"Trip time: {duration} minutes")
        st.write(f"🕒 **Start Time:** {correct_start_time.strftime('%H:%M')}")
        st.write("### Route Details:")
        prev_route = None
        for s in route:
            if s['transfer']:
                st.write(f"🔁 Transfer at {s['stop']} ({s['town']}) — wait and take Route {route[route.index(s)+1]['route']} at {s['time']}")
            else:
                trans = f" (Transfer to Route {s['route']})" if prev_route and s['route'] != prev_route else ""
                st.write(f"➡️ {s['stop']} ({s['town']}) via Route {s['route']}{trans} at {s['time']}")
            prev_route = s['route']
