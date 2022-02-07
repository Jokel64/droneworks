import os

from svg.path import parse_path
from svg.path.path import Line
from xml.dom import minidom
from engine import C3d
import matplotlib.pyplot as plt
import numpy as np

plt.style.use('seaborn-whitegrid')
shapedir = 'shapes'


class ShapeStep:
    def __init__(self, height_level, svg_path):
        doc = minidom.parse(svg_path)
        path_strings = [path.getAttribute('d') for path in doc.getElementsByTagName('path')]
        doc.unlink()

        self.total_length = 0
        self.lines = []
        for path_string in path_strings:
            path = parse_path(path_string)

            for e in path:
                if isinstance(e, Line):
                    self.total_length += e.length()
                    self.lines.append(e)

        self.height_level = height_level

    def get_positions(self, number_of_drones):
        coords = []
        gap = self.total_length / number_of_drones
        overlap = 0
        for line in self.lines:
            coords.append(C3d(line.start.real, line.start.imag, self.height_level))
            a = np.array([line.start.real, line.start.imag])
            b = np.array([line.end.real, line.end.imag])
            s = b - a
            norm = np.linalg.norm(s)
            s_norm = s / norm
            fitting = True
            i = 0
            while fitting:
                scale = overlap + gap * i
                if scale > norm:
                    overlap = norm - (overlap + gap * (i-1))
                    fitting = False
                else:
                    new_point = a + s_norm * scale
                    coords.append(C3d(new_point[0], new_point[1], self.height_level))
                    i += 1
        return coords


def get_available_shapes():
    return os.listdir(shapedir)


if __name__ == '__main__':
    while True:
        print("Select one of the folowing shapes:")
        paths = os.listdir(shapedir)
        for path, i in zip(paths, range(len(paths))):
            print(f'[{i}]: {path}')
        idx = input()
        st = ShapeStep(svg_path=f'{shapedir}/{paths[int(idx)]}', height_level= 2)
        poss = st.get_positions(100)
        my_list = []
        for pos in poss:
            print(pos)
            my_list.append(pos.to_numpy_array())

        arr = np.array(my_list)
        plt.plot(arr[:,0], arr[:,1], 'o', color='black')
        plt.gca().invert_yaxis()
        plt.gca().set_aspect('equal', adjustable='box')
        plt.show()
