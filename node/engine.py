import copy
import logging
import threading
import time
import numpy as np


class C3d:
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

    def __floordiv__(self, other):
        self.x = self.x / other
        self.y = self.y / other
        self.z = self.z / other
        return self

    def __truediv__(self, other):
        self.x = self.x / other
        self.y = self.y / other
        self.z = self.z / other
        return self

    def __pow__(self, power, modulo=None):
        self.x = self.x**power
        self.y = self.y**power
        self.z = self.z**power
        return self

    def __mul__(self, other):
        if type(other) == type(self):
            self.x = self.x * other.x
            self.y = self.y * other.y
            self.z = self.z * other.z
        else:
            self.x = self.x * other
            self.y = self.y * other
            self.z = self.z * other
        return self

    def __sub__(self, other):
        self.x = self.x - other.x
        self.y = self.y - other.y
        self.z = self.z - other.z
        return self

    def __add__(self, other):
        self.x = self.x + other.x
        self.y = self.y + other.y
        self.z = self.z + other.z
        return self

    def min_max_norm(self, norm):
        self.x = min(self.x, norm)
        self.y = min(self.y, norm)
        self.z = min(self.z, norm)
        self.x = max(self.x, norm * -1)
        self.y = max(self.y, norm * -1)
        self.z = max(self.z, norm * -1)
        return self

    def pow2_save_sign(self):
        if self.x < 0:
            self.x = -1*self.x**2
        else:
            self.x = self.x**2
        if self.y < 0:
            self.y = -1*self.y**2
        else:
            self.y = self.y**2
        if self.z < 0:
            self.z = -1*self.z**2
        else:
            self.z = self.z**2
        return self

    def to_numpy_array(self):
        return np.array([self.x, self.y, self.z])

    def __str__(self):
        return f"X: {self.x}\tY: {self.y}\tZ: {self.z}"

    def __eq__(self, other):
        return self.x==other.x and self.y==other.y and self.z==other.z

    def close_to_zero(self, epsilon):
        return abs(self.x) < epsilon and abs(self.y) < epsilon and abs(self.z) < epsilon


class World:
    def __init__(self, weight: float, start_position: C3d, max_drone_force: C3d, fps=100, cw_a_rho=0.3, disable_logging=False):
        self.weight = weight
        self.max_drone_force = max_drone_force
        self.position = start_position
        self.acceleration = C3d(0, 0, 0)
        self.velocity = C3d(0, 0, 0)
        self._force = C3d(0, 0, 0)
        self.fps = fps
        self.cw_A_rho = cw_a_rho
        self.thread = None
        self.force_lock = threading.Lock()
        self.do_logging = True
        self.global_logging_disabled = disable_logging

    def __str__(self):
        return f"Position: {self.position}<br>Velocity: {self.velocity}<br>Acceleration: {self.acceleration}"

    def __loop(self):
        counter = 0
        while True:
            timestamp = time.time()
            f_w = copy.deepcopy(self.velocity).pow2_save_sign() * self.cw_A_rho

            self.force_lock.acquire()
            f_eff = copy.deepcopy(self._force) - f_w
            self.force_lock.release()

            self.acceleration = f_eff/self.weight
            self.velocity += copy.deepcopy(self.acceleration) * 1/self.fps
            self.position += copy.deepcopy(self.velocity) * 1/self.fps

            runtime = (time.time()-timestamp)
            if counter > 10:
                if self.do_logging and not self.global_logging_disabled:
                    logging.debug(f"Acceleration: X: {round(self.acceleration.x, ndigits=5)} | Y: {round(self.acceleration.y, ndigits=5)} "
                                 f"| Z: {round(self.acceleration.z, ndigits=5)} |||  Velocity X: {round(self.velocity.x, ndigits=3)} | Y: {round(self.velocity.y, ndigits=3)} | "
                                f"Z: {round(self.velocity.z, ndigits=3)} ||| Position X: {round(self.position.x, ndigits=3)} | "
                                f"Y: {round(self.position.y, ndigits=3)} | Z: {round(self.position.z, ndigits=3)} | Runtime[ms]: {runtime*1000}")
                counter = 0
            else:
                counter += 1

            sleeptime = 1/self.fps - runtime
            if sleeptime < 0:
                logging.error("The physics simulation is overloaded. Please buy better hardware. Thanks.")
            else:
                time.sleep(1/self.fps - runtime)

    def run_simulation(self):
        self.thread = threading.Thread(target=self.__loop, daemon=True)
        self.thread.start()
        pass

    def stop_simulation(self):
        pass

    def accelerate(self, throttle: C3d):
        throttle.min_max_norm(1)
        self.force_lock.acquire()
        self._force = copy.deepcopy(self.max_drone_force) * copy.deepcopy(throttle)
        self.force_lock.release()


class FlightController:
    # In order to ensure a stable system choose (k_d^2)/4 > k_p
    # Other values: k_p=0.02, k_i=0.0001, k_d=-0.3    k_p=0.6, k_i=0.001, k_d=-1.5  k_p=0.5, k_i=0, k_d=-2
    def __init__(self, world_ref: World, start_destination: C3d, k_p=10, k_i=0.01, k_d=-3, update_interval=0.1):
        self.world = world_ref
        self.k_p = k_p
        self.k_i = k_i
        self.k_d = k_d
        self.destination = start_destination
        self.update_interval = update_interval
        self.thread = None
        self.arrived_at_destination = False

    def __str__(self):
        return f"Destination: {self.destination}<br>Arrived at Destination: {self.arrived_at_destination}"

    def go_to_point(self, destination: C3d):
        self.destination = destination
        logging.debug(f"Go to new destination: {destination}")
        self.world.do_logging = True
        self.arrived_at_destination = False

    def __control_loop(self):
        integration = C3d(0, 0, 0)
        while True:
            rel_pos = copy.deepcopy(self.destination) - copy.deepcopy(self.world.position)

            integration += copy.deepcopy(rel_pos)

            throttle = copy.deepcopy(rel_pos) * self.k_p + integration * self.k_i + copy.deepcopy(self.world.velocity) * self.k_d
            throttle.min_max_norm(1)
            self.world.accelerate(throttle)
            if copy.deepcopy(rel_pos).close_to_zero(0.00001):
                self.world.do_logging = False
                self.arrived_at_destination = True
            time.sleep(self.update_interval)

    def run_controller(self):
        self.thread = threading.Thread(target=self.__control_loop)

        self.thread.start()


if __name__ == '__main__':
    world = World(max_drone_force=C3d(1.5, 1.5, 1.5), weight=0.2, start_position=C3d(0, 0, 0))
    fc = FlightController(world_ref=world, start_destination=C3d(0, 0, 0))
    world.run_simulation()
    fc.run_controller()
    time.sleep(1)


    while True:
        if fc.arrived_at_destination:
            x = input("X:")
            y = input("Y:")
            z = input("Z:")
            fc.go_to_point(C3d(float(x), float(y), float(z)))
            logging.info(f"Command new destination at: x:{x} | y:{y} | z:{z}")
        else:
            time.sleep(1)
