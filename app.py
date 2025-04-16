import streamlit as st
import networkx as nx
import pandas as pd
from datetime import datetime, timedelta, time

# Load Excel data
file_path = "merged_data.xlsx"
df = pd.read_excel(file_path)
df['Time'] = pd.to_datetime(df['DepartTime'], errors='coerce').dt.time

# Streamlit UI
st.set_page_config(layout="wide")
st.markdown("""
<style>
body {
    background-color: #0f0f0f;
    font-family: 'Segoe UI', sans-serif;
}
.main > div {
    display: flex;
    justify-content: center;
    padding: 2rem 1rem;
}
.block-container {
    width: 100%;
    max-width: 720px;
    padding: 2rem;
    background: #1a1a1a;
    border-radius: 16px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
    color: #ffffff;
}
.stSelectbox > div, .stRadio > div, .stTimeInput > div, .stCheckbox > div {
    margin-bottom: 1rem;
}
.stButton button {
    width: 100%;
    background-color: #ff5c5c;
    color: white;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: bold;
    padding: 0.75rem;
    transition: background 0.3s ease;
}
.stButton button:hover {
    background-color: #e04e4e;
}
.swap-button-container {
    display: flex;
    justify-content: center;
    align-items: center;
    margin-top: 1.3rem;
}
.swap-button {
    background: #333;
    color: white;
    border: none;
    border-radius: 50%;
    font-size: 18px;
    width: 36px;
    height: 36px;
    display: flex;
    justify-content: center;
    align-items: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.25);
}
.swap-button:hover {
    background: #555;
}
.transfer-step {
    color: #34eb77;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)


st.title("🚌 Bus Route Time Optimizer")

# Select operating day
days_of_week = ['All Days', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
selected_day = st.selectbox("Select operating day", days_of_week, index=datetime.today().weekday() + 1)

# Filter data by selected day
if selected_day != 'All Days':
    df = df[df[selected_day] == 1]

# Add town to stop name for display
df['StopDisplay'] = df['Stop Location'].str.replace(r'\s*\(Loop\)', '', regex=True).fillna('Unknown Stop') + " (" + df['Town'].fillna('Unknown Town') + ")"
stop_display_map = dict(zip(df['StopDisplay'], df['Stop Location']))
reverse_stop_display_map = {v: k for k, v in stop_display_map.items()}
all_displays = sorted(df['StopDisplay'].dropna().unique())

# Limit time options
time_options = sorted(df['Time'].dropna().unique())
default_time = min(time_options) if time_options else time(6, 0)
colt1, colt2 = st.columns([1, 1])
with colt1:
    time_mode = st.radio("Time Mode", ["Specific Time", "Any Time"], horizontal=True)
with colt2:
    user_time = default_time if time_mode == "Any Time" else st.time_input("Select earliest available departure time", value=default_time)

# Initialize session state defaults
if 'start_display' not in st.session_state:
    st.session_state['start_display'] = all_displays[0]
if 'end_display' not in st.session_state:
    st.session_state['end_display'] = all_displays[1]

# Swap trigger button
swap = False
col1, col2, col3 = st.columns([4.2, 0.6, 4.2])
with col2:
    st.markdown("""
        <div style='display: flex; justify-content: center; align-items: center; margin-top: 2.4rem; height: 40px;'>
    <button class='swap-button' onclick='document.querySelector("button[kind=\"secondary\"]").click();'>🔄</button>
</div>
    """, unsafe_allow_html=True)
    swap = st.button("", key="swap_button", help="Switch start and destination")

# Handle swap before dropdowns
if swap:
    st.session_state['start_display'], st.session_state['end_display'] = st.session_state['end_display'], st.session_state['start_display']

# Layout for route selection
with col1:
    start_display = st.selectbox("Select starting stop", all_displays, index=all_displays.index(st.session_state['start_display']), key="start")
with col3:
    end_display = st.selectbox("Select destination stop", all_displays, index=all_displays.index(st.session_state['end_display']), key="end")

# Persist values
st.session_state['start_display'] = start_display
st.session_state['end_display'] = end_display

start = stop_display_map[start_display]
end = stop_display_map[end_display]

trip_type = st.radio("Trip type", options=["One-way"])
show_all = st.checkbox("Show all possible routes without selecting time")

# Graph construction
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
        time_a = row_a['Time']
        time_b = row_b['Time']
        dt_a = datetime.combine(datetime.today(), time_a)
        dt_b = datetime.combine(datetime.today(), time_b)
        if dt_b < dt_a:
            dt_b += timedelta(days=1)
        duration = (dt_b - dt_a).total_seconds() / 60.0
        if duration >= 0:
            G.add_edge((row_a['Stop Location'], time_a), (row_b['Stop Location'], time_b), weight=duration, route=route, town=row_a['Town'])

# Add transfers
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
            G.add_edge((stop, t1), (stop, t2), weight=wait, route='Transfer', town=group.iloc[0]['Town'])

# Shortest path finder
def find_transfer_path(start, end, start_time):
    candidates = [(s, t) for s, t in G.nodes if s == start and (time_mode == 'Any Time' or t >= start_time)]
    targets = [(s, t) for s, t in G.nodes if s == end]
    shortest_path = None
    shortest_cost = float('inf')
    best_start_time = None

    for start_node in candidates:
        for end_node in targets:
            try:
                path = nx.dijkstra_path(G, start_node, end_node, weight='weight')
                cost = sum(G[path[i]][path[i + 1]]['weight'] for i in range(len(path) - 1))
                if cost < shortest_cost:
                    shortest_cost = cost
                    shortest_path = path
                    best_start_time = start_node[1]
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

# Display routes
if show_all:
    found_any = False
    shown_paths = set()
    all_times = sorted(set(t for s, t in G.nodes if s == start))[:10]  # Limit to earliest 10
    for s_time in all_times:
        result = find_transfer_path(start, end, s_time)
        if isinstance(result, tuple):
            path, duration, correct_start_time = result
            path_signature = tuple((step['stop'], step['route'], step['time']) for step in path)
            if path_signature in shown_paths:
                continue
            shown_paths.add(path_signature)
            found_any = True
            st.write(f"🕒 **Start Time:** {correct_start_time.strftime('%H:%M')}")
            st.write(f"⏱️ **Trip Duration:** {duration} minutes")
            previous_route = None
            for step in path:
                if step['transfer']:
                    st.markdown(f"<span class='transfer-step'>🔁 Transfer at {step['stop']} ({step['town']}) — wait and take Route {route[route.index(step)+1]['route']} at {step['time']}</span>", unsafe_allow_html=True)
                else:
                    transfer_notice = f" (Transfer to Route {step['route']})" if previous_route and step['route'] != previous_route else ""
                    st.write(f"➡️ {step['stop']} ({step['town']}) via Route {step['route']}{transfer_notice} at {step['time']}")
                previous_route = step['route']
            st.markdown("---")

    if not found_any:
        st.warning("No available routes found from this stop to the destination.")

elif st.button("Find Shortest Time"):
    result = find_transfer_path(start, end, user_time)
    if isinstance(result, str):
        st.error(result)
    else:
        route, duration, correct_start_time = result
        st.success(f"Trip time: {duration} minutes")
        st.write(f"🕒 **Start Time:** {correct_start_time.strftime('%H:%M')}")
        st.markdown("""
        <style>
        .transfer-step {
            color: #2ecc71;
            font-weight: bold;
        }
        </style>
        """, unsafe_allow_html=True)
        st.write("### Route Details:")
        previous_route = None
        for step in route:
            if step['transfer']:
                st.markdown(f"<span class='transfer-step'>🔁 Transfer at {step['stop']} ({step['town']}) — wait and take Route {route[route.index(step)+1]['route']} at {step['time']}</span>", unsafe_allow_html=True)
            else:
                transfer_notice = f" (Transfer to Route {step['route']})" if previous_route and step['route'] != previous_route else ""
                st.write(f"➡️ {step['stop']} ({step['town']}) via Route {step['route']}{transfer_notice} at {step['time']}")
            previous_route = step['route']


# Removed duplicated route preview loop; already shown using Plotly
