import logging
import threading
import time

import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output
import plotly.express as px

import numpy as np

from engine import World, FlightController, C3d
from shape_logic import ShapeStep

n_drones = 97
w_list = []
fc_list = []
for i in range(n_drones):
    world = World(max_drone_force=C3d(1.5, 1.5, 0.1), weight=0.2, start_position=C3d(0, 0, np.random.uniform(-20, 20)), disable_logging=True)
    w_list.append(world)
    fc = FlightController(world_ref=world, start_destination=C3d(0, 0, 0))
    fc_list.append(fc)
    world.run_simulation()
    fc.run_controller()


def positions():
    st_big = ShapeStep(svg_path=f'shapes/star.svg', height_level=2)
    st_small = ShapeStep(svg_path=f'shapes/star_small.svg', height_level=2)
    corr = n_drones-7
    pos_big = st_big.get_positions(corr)
    print(f"pos_len: {len(pos_big)}")
    pos_small = st_small.get_positions(corr)
    for elm in pos_small:
        elm/10
    for elm in pos_big:
        elm/10

    while True:
        for i in range(n_drones):
            fc_list[i].go_to_point(pos_big[i])
        time.sleep(15)
        for i in range(n_drones):
            fc_list[i].go_to_point(pos_small[i])
        time.sleep(15)


FC_thread = threading.Thread(target=positions)
FC_thread.start()

# Plotly dash server
app = dash.Dash(__name__)

app.layout = html.Div([
    dcc.Graph(id="scatter-plot"),
    dcc.Interval(
        id='interval-component',
        interval=1 * 100)
])

@app.callback(
    Output("scatter-plot", "figure"),
    [Input("interval-component", 'n_intervals')])
def update_bar_chart(n_interval):
    coords = []
    for i in range(n_drones):
        coords.append(w_list[i].position.to_numpy_array())
    arr = np.array(coords)
    # Change between 2D and 3D
    #fig = px.scatter(x=arr[:, 0], y=arr[:, 1], width=1500, height=1200, range_y=[0,60], range_x=[0, 75])
    fig = px.scatter_3d(x=arr[:, 0], y=arr[:, 1], z=arr[:, 2], width=1500, height=1200, range_y=[0,60], range_x=[0, 75], range_z=[-25, 25])
    fig['layout']['uirevision'] = 'False'
    return fig

app.run_server(debug=True)