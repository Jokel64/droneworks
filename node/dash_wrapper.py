import dash
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import numpy as np
import plotly.express as px


_app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

node_list_ref = None

control = dbc.Card(
    [
        html.H2("Control", className="card-title"),
        html.Div(
            [
                dbc.Label("Shape Selector"),
                dcc.Dropdown(
                    id="dropdown_shape",
                    options=[
                        {'label': 'Star', 'value': 'shape_star'},
                        {'label': 'Ellipse', 'value': 'shape_ellipse'}
                    ],
                    value='shape_star'
                )
            ]
        )
    ],
    body=True,
    color="primary",
    outline=True,
)

data = dbc.Card(
    [
        html.H2("Data", className="card-title"),
        html.Div(
            [
                html.P(id="current_shape")
            ]
        ),
    ],
    body=True,
    color="secondary",
    outline=True,
)

graph = dbc.Card(
    [

        html.H2("Drone Position Visualisation", className="card-title"),
        dcc.Graph(id="scatter-plot"),
        dcc.Interval(
            id='interval-component',
            interval=1 * 100)
    ],
    body=True,
)

_app.layout = dbc.Container(
    [
        html.H1("Droneworks Control Center"),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(graph, md=8),
                dbc.Col(control, md=2),
                dbc.Col(data, md=2)
            ],
            align="center",
        ),
    ],
    fluid=True,
)

@_app.callback(
    Output("scatter-plot", "figure"),
    [Input("interval-component", 'n_intervals')])
def _update_bar_chart(n_interval):
    global node_list_ref
    coords = []
    #for i in range(n_drones):
    #    coords.append(w_list[i].position.to_numpy_array())
    arr = np.array(coords)
    # Change between 2D and 3D
    fig = px.scatter(x=np.array([1,2]), y=np.array([1,2]), width=1500, height=1200, range_y=[0,5], range_x=[0, 5])
    #fig = px.scatter_3d(x=arr[:, 0], y=arr[:, 1], z=arr[:, 2], width=1500, height=1200, range_y=[0,60], range_x=[0, 75], range_z=[-25, 25])
    fig['layout']['uirevision'] = 'False'
    return fig

@_app.callback(
    Output("current_shape", "children"),
    Input("dropdown_shape", "value")
)
def _update_output(value):
    return 'Currently Selected Shape: "{}"'.format(value)

def t_dash_interface():
    _app.run_server(debug=False, host="0.0.0.0")

def set_node_list(node_list):
    global node_list_ref
    node_list_ref = node_list
