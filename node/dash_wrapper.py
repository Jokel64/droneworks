import dash
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import numpy as np
import plotly.express as px


_app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

node_list_ref = None
cb_new_shape = None
available_shapes = []


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
    color="primary",
    outline=True,
)

graph = dbc.Card(
    [

        html.H2("Drone Position Visualisation", className="card-title"),
        html.Div(children=[
            html.Div(children=[
                dcc.Graph(id="scatter-plot"),
                dcc.Interval(
                    id='interval-component',
                    interval=1 * 100)
            ])
        ],
        style={'display': 'inline-block', 'width': '100%'})

    ],
    body=True,
    color="primary",
    outline=True,
)


def set_leader_content():
    options = list()
    for shape in available_shapes:
        options.append({'label': str(shape).replace(".svg", ""), 'value': shape})
    control = dbc.Card(
        [
            html.H2("Control", className="card-title"),
            html.Div(
                [
                    dbc.Label("Shape Selector"),
                    dcc.Dropdown(
                        id="dropdown_shape",
                        options=options,
                        value='shape_star'
                    )
                ]
            )
        ],
        body=True,
        color="primary",
        outline=True,
    )

    _app.layout = dbc.Container(
        [
            html.H1("Droneworks Control Center"),
            html.Hr(),
            dbc.Row(
                [
                    dbc.Col(graph),
                ],
                align="center",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.CardGroup([control, data])),
                ],
                align="center",
            ),
        ],
        fluid=True,
    )

def set_slave_content():
    _app.layout = dbc.Container(
        [
            html.H1("This Drone is not the leader of the swarm.")
        ],
        fluid=True,
    )

# Set the default layout.
set_slave_content()


@_app.callback(
    Output("scatter-plot", "figure"),
    [Input("interval-component", 'n_intervals')])
def _update_bar_chart(n_intervals):
    global node_list_ref
    coords = np.empty((len(node_list_ref), 3))
    counter = 0
    for uuid in node_list_ref:
        coords[counter][0] = node_list_ref[uuid]["pos"]["x"]
        coords[counter][1] = node_list_ref[uuid]["pos"]["y"]
        coords[counter][2] = node_list_ref[uuid]["pos"]["z"]

        counter += 1

    # Change between 2D and 3D
    fig = px.scatter(x=coords[:, 0], y=coords[:, 1], range_y=[-10,50], range_x=[-10, 50])
    #fig = px.scatter_3d(x=coords[:, 0], y=coords[:, 1], z=coords[:, 2], width=1500, height=1200, range_y=[0,60], range_x=[0, 75], range_z=[-25, 25])
    fig['layout']['uirevision'] = 'False'
    return fig

@_app.callback(
    Output("current_shape", "children"),
    Input("dropdown_shape", "value")
)

def _update_output(value):
    global cb_new_shape
    try:
        cb_new_shape(value)
    except Exception as e:
        print(f"Error calling new shape callback function: {e}")

    return 'Currently Selected Shape: "{}"'.format(value)

def t_dash_interface(ip, node_list, a_cb_new_shape, a_available_shapes):
    global node_list_ref, cb_new_shape, available_shapes
    cb_new_shape = a_cb_new_shape
    node_list_ref = node_list
    available_shapes = a_available_shapes
    _app.run_server(debug=False, host="0.0.0.0")

def set_node_list(node_list):
    global node_list_ref
    node_list_ref = node_list
