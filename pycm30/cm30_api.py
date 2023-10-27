import requests
from PIL import Image
from io import BytesIO

URL_BASE=None
API_BASE=None
def init(hostname='localhost', port=8080):
    global URL_BASE
    global API_BASE
    URL_BASE='http://{}:{}/cm/'.format(hostname, port)
    API_BASE=URL_BASE + 'v1/'

def _api_get(path):
    url = API_BASE + path
    r = requests.get(url)
    return r.json()

def _api_post(path, json=None):
    url = API_BASE + path
    if json:
        r = requests.post(url, json= json)
    else:
        r = requests.post(url)
    return r

def get_image():
    url = API_BASE + 'image.capture'
    r = requests.post(url)
    b = BytesIO(r.content)
    img = Image.open(b)
    return img

def xy_move(x, y):
    url = API_BASE + 'stage_xy.move'
    print("Moving to {},{}".format(x,y))
    r = requests.post(url, json= {'x': x, 'y':y})
    return r

def get_stage_xy():
    url = API_BASE + 'stage_xy'
    r = requests.get(url)
    return r.json()

def z_move(z):
    url = API_BASE + 'stage_z.move'
    r = requests.post(url, json= {'z': z, 'z_mode': 'absolute'})
    return r

def get_stage_z(): return _api_get('stage_z')

def reboot(): return _api_post('power.reboot', {'sleep_sec':1})

def get_api_info(): return _api_get('info')

def get_head_info(): return _api_get('head')

def head_init(): return _api_post('head.init')

def get_device_info(): return _api_get('info')

def get_light_params(): return _api_get('light')

def image_capture_save(user_data={}): 
    return _api_post('image.capture_save', json=user_data)

def autofocus(z_default=3240, z_offset=0):
    url = API_BASE + 'stage_z.focus'
    r = requests.post(url, json= {'z_default': z_default, 'z_offset': z_offset})
    return r

def set_z_focus_range(zmin=3230, zmax=3250):
    url = API_BASE + 'stage_z'
    r = requests.patch(url, json={'z_focus.range': [zmin, zmax]})
    return r

def set_resolution(width, height):
    url = API_BASE + 'image'
    r = requests.put(url, json={'width': width, 'height': height})
    return r
   
def is_moving():
    xy_info = get_stage_xy()
    return xy_info['is_moving']

def is_head_connected():
    if head_info.get('code', 0) == 5031:
        return False

    return True

if __name__ == '__main__':
    import sys
    import time
    hostname = 'localhost'
    port = 8080
    if len(sys.argv) > 1:
        hostname = sys.argv[1]
        print("Using hostname {}".format(hostname))
    if len(sys.argv) > 2:
        port = sys.argv[2]
        print("Using port {}".format(port))

    init(hostname, port)
    head_init()
    head_info = get_head_info()
    while head_info.get('code', 0) == 5031:
        print("Waiting for head to connect...", end='\r')
        time.sleep(1)
    
    print("Head connected - info:")
    print(head_info)

    device_info = get_device_info()
    light_params = get_light_params()
    
    xy_info = get_stage_xy()

    xrange= xy_info['x.range']
    XMAX = xrange[1] // 2
    yrange= xy_info['y.range']
    YMAX = yrange[1] // 2
    MIN_STEP=105
    DX=MIN_STEP*27 #2840
    DY=MIN_STEP*20 #2130

    autofocus()
    import time
    
    images = dict()
    for x in range(0, XMAX, DX):
        for y in range(0, YMAX, DY):
            print("Moving to {},{}".format(x,y))
            xy_move(x,y)
            tstart = time.time()
            while is_moving():
                time.sleep(0.1)
            
            print("Move complete after {}s".format(time.time() - tstart))
            
            tstamp = time.time()
            res = image_capture_save({'x':x, 'y':y})
            print(res.json())
            file_ids = res.json()['file_ids']
            images[(x,y)] = file_ids
            #TODO - record locations, timestamp, and file id
            # use influxdb?
            print("images[({},{})] = {}".format(x,y,file_ids))
