import cv2
import os
import re
import datetime
import pandas as pd
import stitching

def get_stitched(imgs):
    s = cv2.Stitcher_create(cv2.STITCHER_SCANS)
    status, img = s.stitch(imgs)
    return status, img

if __name__ == '__main__':
    img_dir = os.path.expanduser("~/Documents/lucid/experiments/c2c12-imaging/2023-10-27-coarse-interleave")
    stitch_dir = img_dir + '/stitched/'
    try:
        os.mkdir(stitch_dir)
    except:
        pass
    files = os.listdir(img_dir)
    start_tile_files = [f for f in files if 'xt0_yt0' in f]
    
    def data_from_fname(fname):
        try: 
            datestr, locstr = fname.split("_atloc_")
        except:
            return {}
        dt = datetime.datetime.strptime(datestr, "%Y-%m-%d-%H_%M_%S")
        regex = "x(\d+)_y(\d+)_z(\d+.\d+)_r(\d)_c(\d+)_xt(\d+)_yt(\d+).jpg"
        m = re.match(regex, locstr)
        if m is None:
            return None

        x,y,z,row,col,xtile,ytile = m.groups()
        return {'datetime': dt, 
                'x': int(x),
                'y': int(y),
                'z': float(z),
                'row': int(row),
                'col': int(col),
                'xtile': int(xtile),
                'ytile': int(ytile),
                'fname': fname,
                }
    
    def fpaths_for_keytile(df_all, kt):
        ts = kt.datetime
        tmax = ts + datetime.timedelta(minutes=5)
        subset = df_all[(df.datetime >= ts)]
        subset = subset[subset.datetime <= tmax]
        subset = subset[(subset.row == kt.row) & (subset.col == kt.col)]
        return subset.fname
    
    df = pd.DataFrame(data_from_fname(f) for f in files)
    keytiles  = df[(df.xtile ==0) & (df.ytile == 0)]
    
    def _fullpath(relpath):
        return os.path.join(img_dir, relpath)

    for i, k in keytiles.iterrows():
        fpaths = fpaths_for_keytile(df, k)
        if len(fpaths) != 16:
            print("Unable to get all tiles for {}".format(k.fname))
            continue

        imgs = [cv2.imread(_fullpath(p)) for p in fpaths]
        st = stitching.AffineStitcher()
        stiched = st.stitch(imgs)
        #img = c.process(_fullpath(p) for p in fpaths)
        if False:
            status, stitched = get_stitched(imgs)
            if status != 0:
                print("Stitching failed for {}".format(k.fname))
                continue
        print("Stitched {}".format(k.fname))
        dtstr = k.datetime.strftime("%Y-%m-%d-%H_%M_%S")
        outpath = os.path.join(stitch_dir, "{}_r{}_c{}_merged.jpg".format(dtstr, int(k.row), int(k.col)))
        cv2.imwrite(outpath, stiched)
        #img.save(outpath)

    #def get_fpath(row, col)
    #get start tiles    
    #fname = dt.strftime("%Y-%m-%d-%H_%M_%S") + "_atloc_x{}_y{}_z{}_r{}_c{}_xt{}_yt{}.jpg".format(x, y, z, 
