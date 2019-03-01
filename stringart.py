import collections
import math
import os
import cv2
import numpy as np
import time

MAX_LINES = 4000
N_PINS = 36*8
MIN_LOOP = 20               # To avoid getting stuck in a loop
MIN_DISTANCE = 20           # To avoid very short lines
LINE_WEIGHT = 15            # Tweakable parameter
FILENAME = "h2.jpg"
SCALE = 25                  # For making a very high resolution render, to attempt to accurately gauge how thick the thread must be
HOOP_DIAMETER = 0.625       # To calculate total thread length

tic = time.perf_counter()

img = cv2.imread(FILENAME, cv2.IMREAD_GRAYSCALE)

# Didn't bother to make it work for non-square images
assert img.shape[0] == img.shape[1]
length = img.shape[0]

def disp(image):
    cv2.imshow('image', image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# Cut away everything around a central circle
X,Y = np.ogrid[0:length, 0:length]
circlemask = (X - length/2) ** 2 + (Y - length/2) ** 2 > length/2 * length/2
img[circlemask] = 0xFF
breakpoint()
pin_coords = []
center = length / 2
radius = length / 2 - 1/2

# Precalculate the coordinates of every pin
for i in range(N_PINS):
    angle = 2 * math.pi * i / N_PINS
    pin_coords.append((math.floor(center + radius * math.cos(angle)),
                       math.floor(center + radius * math.sin(angle))))

line_cache_y = [None] * N_PINS * N_PINS
line_cache_x = [None] * N_PINS * N_PINS
line_cache_weight = [1] * N_PINS * N_PINS # Turned out to be unnecessary, unused
line_cache_length = [0] * N_PINS * N_PINS

print("Precalculating all lines... ", end='', flush=True)

for a in range(N_PINS):
    for b in range(a + MIN_DISTANCE, N_PINS):
        x0 = pin_coords[a][0]
        y0 = pin_coords[a][1]

        x1 = pin_coords[b][0]
        y1 = pin_coords[b][1]

        d = int(math.sqrt((x1 - x0) * (x1 - x0) + (y1 - y0)*(y1 - y0)))

        #d = max(abs(y1-y0), abs(x1-x0)) inf-norm
        
        # A proper (slower) Bresenham does not give any better result *shrug*
        xs = np.linspace(x0, x1, d, dtype=int)
        ys = np.linspace(y0, y1, d, dtype=int)

        line_cache_y[b*N_PINS + a] = ys
        line_cache_y[a*N_PINS + b] = ys
        line_cache_x[b*N_PINS + a] = xs
        line_cache_x[a*N_PINS + b] = xs
        line_cache_length[b*N_PINS + a] = d
        line_cache_length[a*N_PINS + b] = d


print("done")

error = np.ones(img.shape) * 0xFF - img.copy()

img_result = np.ones(img.shape) * 0xFF
lse_buffer = np.ones(img.shape) * 0xFF    # Used in the unused LSE algorithm

result = np.ones((img.shape[0] * SCALE, img.shape[1] * SCALE), np.uint8) * 0xFF
line_mask = np.zeros(img.shape, np.float64) # XXX

line_sequence = []
pin = 0
line_sequence.append(pin)

thread_length = 0

last_pins = collections.deque(maxlen = MIN_LOOP)

for l in range(MAX_LINES):

    if l % 100 == 0:
        print("%d " % l, end='', flush=True)

        img_result = cv2.resize(result, img.shape, interpolation=cv2.INTER_AREA)

        # Some trickery to fast calculate the absolute difference, to estimate the error per pixel
        diff = img_result - img
        mul = np.uint8(img_result < img) * 254 + 1
        absdiff = diff * mul
        print(absdiff.sum() / (length * length))

    max_err = -math.inf
    best_pin = -1

    # Find the line which will lower the error the most
    for offset in range(MIN_DISTANCE, N_PINS - MIN_DISTANCE):
        test_pin = (pin + offset) % N_PINS
        if test_pin in last_pins:
            continue

        xs = line_cache_x[test_pin * N_PINS + pin]
        ys = line_cache_y[test_pin * N_PINS + pin]

        # Simple
        # Error defined as the sum of the brightness of each pixel in the original
        # The idea being that a wire can only darken pixels in the result
        line_err = np.sum(error[ys,xs]) * line_cache_weight[test_pin*N_PINS + pin]
        '''

        # LSE Unused
        goal_pixels = img[ys, xs]
        old_pixels = lse_buffer[ys, xs]
        new_pixels = np.clip(old_pixels - LINE_WEIGHT * line_cache_weight[test_pin*N_PINS + pin], 0, 255)

        line_err = np.sum((old_pixels - goal_pixels) ** 2) - np.sum((new_pixels - goal_pixels) ** 2)
        #LSE
        '''

        if line_err > max_err:
            max_err = line_err
            best_pin = test_pin

    line_sequence.append(best_pin)

    xs = line_cache_x[best_pin * N_PINS + pin]
    ys = line_cache_y[best_pin * N_PINS + pin]
    weight = LINE_WEIGHT * line_cache_weight[best_pin*N_PINS + pin]

    '''
    #LSE
    old_pixels = lse_buffer[ys, xs]
    new_pixels = np.clip(old_pixels - weight, 0, 255)

    lse_buffer[ys, xs] = new_pixels
    #LSE
    '''

    # Subtract the line from the error
    line_mask.fill(0)
    line_mask[ys, xs] = weight
    error = error - line_mask
    error.clip(0, 255)

    # Draw the line in the result
    cv2.line(result,
        (pin_coords[pin][0] * SCALE,      pin_coords[pin][1] * SCALE),
        (pin_coords[best_pin][0] * SCALE, pin_coords[best_pin][1] * SCALE),
        color=0, thickness=4, lineType=8)

    x0 = pin_coords[pin][0]
    y0 = pin_coords[pin][1]

    x1 = pin_coords[best_pin][0]
    y1 = pin_coords[best_pin][1]

    # Calculate physical distance
    dist = math.sqrt((x1 - x0) * (x1 - x0) + (y1 - y0)*(y1 - y0))
    thread_length += HOOP_DIAMETER / length * dist

    last_pins.append(best_pin)
    pin = best_pin

img_result = cv2.resize(result, img.shape, interpolation=cv2.INTER_AREA)

diff = img_result - img
mul = np.uint8(img_result < img) * 254 + 1
absdiff = diff * mul

print(absdiff.sum() / (length * length))

print('\x07')
toc = time.perf_counter()
print("%.1f seconds" % (toc - tic))

cv2.imwrite(os.path.splitext(FILENAME)[0] + "-out.png", result)

with open(os.path.splitext(FILENAME)[0] + ".json", "w") as f:
    f.write(str(line_sequence)) 
