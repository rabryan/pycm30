import requests
from PIL import Image
from io import BytesIO

URL_BASE='http://localhost:8080/cm/v1/'
def get_image():
    url = URL_BASE + 'image.capture'
    r = requests.post(url)
    b = BytesIO(r.content)
    img = Image.open(b)
    return img

def xy_move(x, y):
    url = URL_BASE + 'stage_xy.move'
    print("Moving to {},{}".format(x,y))
    r = requests.post(url, json= {'x': x, 'y':y})
    return r

def get_stage_xy():
    url = URL_BASE + 'stage_xy'
    r = requests.get(url)
    return r.json()

def z_move(z):
    url = URL_BASE + 'stage_z.move'
    r = requests.post(url, json= {'z': z})
    return r

def get_stage_z():
    url = URL_BASE + 'stage_z'
    r = requests.get(url)
    return r.json()

def autofocus(z_default=1000, z_offset=0):
    url = URL_BASE + 'stage_z.focus'
    r = requests.post(url, json= {'z_default': z_default, 'z_offset': z_offset})
    return r

def set_resolution(width, height):
    url = URL_BASE + 'image'
    r = requests.put(url, json={'width': width, 'height': height})
    return r
    


