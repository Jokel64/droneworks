"""
Test File for the Dockerfile.
"""
import time
from pythonping import ping

hostname = "google.com"
counter = 0
while True:
    response = ping(hostname, 2, 1)
    #if response == 0:
    #    print(f'[{counter}] Connected to the internet.')
    #else:
    #    print(f'[{counter}] Not connected to the internet!')
    print(response)
    counter += 1
    time.sleep(5)
