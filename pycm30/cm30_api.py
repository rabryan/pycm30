import requests
from PIL import Image
from io import BytesIO

URL_BASE='http://localhost:8080/cm/'
API_BASE='http://localhost:8080/cm/v1/'

def _api_get(path):
    url = API_BASE + path
    r = requests.get(url)
    return r.json()

def _api_post(path, json={}):
    url = API_BASE + path
    r = requests.post(url, json= json)
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
    r = requests.post(url, json= {'z': z})
    return r

def get_stage_z(): return _api_get('stage_z')

def get_api_info(): return _api_get('info')

def get_head_info(): return _api_get('head')

def head_init(): return _api_post('head.init')

def get_device_info(): return _api_get('info')

def get_light_params(): return _api_get('light')

def image_capture_save(user_data={}): 
    return _api_post('image.capture_save', json=user_data)

def autofocus(z_default=1000, z_offset=0):
    url = API_BASE + 'stage_z.focus'
    r = requests.post(url, json= {'z_default': z_default, 'z_offset': z_offset})
    return r

def set_resolution(width, height):
    url = API_BASE + 'image'
    r = requests.put(url, json={'width': width, 'height': height})
    return r
   
def is_moving():
    xy_info = get_stage_xy()
    return xy_info['is_moving']

if __name__ == '__main__':
    head_init()
    head_info = get_head_info()
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

            res = image_capture_save({'x':x, 'y':y})
            print(res.json())
            file_ids = res.json()['file_ids']
            images[(x,y)] = file_ids
            print("images[({},{})] = {}".format(x,y,file_ids))
