import os
import re
import datetime
import pandas as pd
from PIL import Image

def data_from_fname(fname):
    try: 
        datestr, locstr = fname.split("_atloc_")
    except:
        return None
    dt = datetime.datetime.strptime(datestr, "%Y-%m-%d-%H_%M_%S")
    regex = "x(\d+)_y(\d+)_z(\d+.\d+).jpg"
    m = re.match(regex, locstr)
    if m is None:
        return None

    x,y,z = m.groups()
    return {'datetime': dt, 
            'x': int(x),
            'y': int(y),
            'z': float(z),
            'fname': fname,
            }
    
if __name__ == '__main__':
    #img_dir = os.path.expanduser("~/Documents/lucid/experiments/cm30/calibration-slide/lowres")
    #img_dir = os.path.expanduser("~/Documents/lucid/experiments/cm30/calibration-slide/highres-clear-top")
    #img_dir = os.path.expanduser("~/Documents/lucid/experiments/cm30/calibration-slide/highres-orange-lid")
    #img_dir = os.path.expanduser("~/Documents/lucid/experiments/cm30/calibration-slide/highres-orange-lid-ss_1_10_iso_100")
    import sys
    img_dir = sys.argv[1]
    highres = True
    #img_dir = os.path.expanduser("~/Documents/lucid/experiments/cm30/calibration-slide/")
    files = os.listdir(img_dir)
    
    data = [ data_from_fname(f) for f in files]
    df = pd.DataFrame(d for d in data if d is not None)
    if highres:
        WIDTH_PX=2048
        HEIGHT_PX=1536
    else:
        WIDTH_PX=640
        HEIGHT_PX=480

    nx = len(df.x.unique())
    ny = len(df.y.unique())

    TILED_WIDTH_PX = WIDTH_PX * nx
    TILED_HEIGHT_PX = HEIGHT_PX * ny

    tiled_im = Image.new('RGB', (TILED_WIDTH_PX, TILED_HEIGHT_PX))
    
    xmin = df.x.min()
    xmax = df.x.max()
    ymin = df.y.min()
    ymax = df.y.max()
    
    DX=105*27
    DY=105*20
    
    print("New image - {} x {} px".format(TILED_WIDTH_PX, TILED_HEIGHT_PX))
    def get_indices(x,y):
        i = round((x - xmin) / DX)
        j = round((y - ymin) / DY)
        return i, j

    for i, r in df.iterrows():
        i, j = get_indices(r.x, r.y)
        image = Image.open(os.path.join(img_dir, r.fname))

        tiled_im.paste(image, (i*WIDTH_PX, j*HEIGHT_PX))


    fpath = os.path.expanduser('~/.tmp/tiled.jpg')
    tiled_im.save(fpath)
    print("saved to {}".format(fpath))

