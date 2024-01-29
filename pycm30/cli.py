#!/usr/bin/python3
import click
import time
import datetime
import pycm30.cm30_api as api

@click.group()
def cmds():
    pass

@cmds.command()
@click.option('--hostname', default='localhost')
@click.option('--port', default=8080)
def get_head_info(hostname='localhost', port=8080):
    api.init(hostname, port)
    print(api.get_head_info())

@cmds.command()
@click.option('--hostname', default='localhost')
@click.option('--port', default=8080)
def image_show(hostname='localhost', port=8080):
    from PIL import ImageTk
    from tkinter import ttk
    from tkinter import Tk
    api.init(hostname, port)
    api.set_resolution(2048, 1536)
    tstart = time.time()
    img = api.get_image()
    print("Image captured in {} ms".format(int(1000*(time.time() - tstart))))
    root = Tk()
    frm = ttk.Frame(root, padding=10)
    grid = frm.grid()
    render = ImageTk.PhotoImage(img)
    img_label = ttk.Label(frm, image=render)
    img_label.grid(column=0, row=0)
    root.geometry('1900x1200')
    root.mainloop()

@cmds.command()
@click.option('--hostname', default='localhost')
@click.option('--port', default=8080)
@click.option('--autofocus-all', default=True)
def image_loop(hostname='localhost', port=8080, autofocus_all=True):
    api.init(hostname, port)
    print(api.get_head_info())
    if autofocus_all:
        api.autofocus()
        print(api.get_stage_z())
    
    import time
    
    images = dict()
    while True:
        if autofocus_all:
            r = api.autofocus()
            print(api.get_stage_z())

        tstamp = time.time()
        res = api.image_capture_save()
        print("Image capture_save took {}s".format(time.time() - tstamp))
        print(res.json())
        file_ids = res.json()['file_ids']
        #images[(x,y)] = file_ids
        #TODO - record locations, timestamp, and file id
        # use influxdb?
        #print("images[({},{})] = {}".format(x,y,file_ids))
        print("{} {}".format(tstamp, file_ids))

@cmds.command()
@click.option('--hostname', default='localhost')
@click.option('--port', default=8080)
@click.option('--autofocus-all', default=True)
def scan_full(hostname='localhost', port=8080, autofocus_all=True):
    api.init(hostname, port)
    print(api.get_head_info())
    xy_info = api.get_stage_xy()

    xrange= xy_info['x.range']
    XMAX = xrange[1] // 2 
    yrange= xy_info['y.range'] 
    YMAX = yrange[1] // 2 
    MIN_STEP=105 
    DX=MIN_STEP*27 #2840 
    DY=MIN_STEP*20 #213
    
    api.autofocus()
    print(api.get_stage_z())
    import time
    
    images = dict()
    for x in range(0, XMAX, DX):
        for y in range(0, YMAX, DY):
            print("Moving to {},{}".format(x,y))
            api.xy_move(x,y)
            tstart = time.time()
            while api.is_moving():
                time.sleep(0.1)
            
            if autofocus_all:
                r = api.autofocus()
                print(api.get_stage_z())

            print("Move complete after {}s".format(time.time() - tstart))
            
            tstamp = time.time()
            res = api.image_capture_save({'x':x, 'y':y})
            print("Image capture_save took {}s".format(time.time() - tstamp))
            print(res.json())
            file_ids = res.json()['file_ids']
            images[(x,y)] = file_ids
            #TODO - record locations, timestamp, and file id
            # use influxdb?
            print("images[({},{})] = {}".format(x,y,file_ids))

@cmds.command()
@click.argument('xmin', type=int)
@click.argument('xmax', type=int)
@click.argument('ymin', type=int)
@click.argument('ymax', type=int)
@click.argument('directory')
@click.option('--hostname', default='localhost')
@click.option('--port', default=8080)
@click.option('--autofocus-init', default=True)
@click.option('--autofocus-all', default=True)
@click.option('--fixed-z', default=800.0)
@click.option('--iso', default=100)
@click.option('--shutter-speed-denominator', default=20)
def scan_area(xmin, xmax, ymin, ymax, directory, hostname='localhost', port=8080, 
        autofocus_init=True, autofocus_all=True, fixed_z=800.0, iso=100, 
        shutter_speed_denominator=20):
    api.init(hostname, port)
    print(api.get_head_info())
    #api.set_power_saving(False)
    xy_info = api.get_stage_xy()
    api.set_light_params('led2_on')
    api.set_resolution(2048, 1536)
    api.set_exposure_settings(iso = iso, 
            shutter_speed_denominator = shutter_speed_denominator)

    print("Using exposure iso {} with shutter 1/{}".format(iso, shutter_speed_denominator))
    xrange= xy_info['x.range']
    XMAX = xrange[1] // 2 
    yrange= xy_info['y.range'] 
    YMAX = yrange[1] // 2 
    MIN_STEP=105 
    DX=MIN_STEP*27 #2840 
    DY=MIN_STEP*20 #213
    
    if autofocus_init:
        api.autofocus()
        r = api.autofocus()
        z_info = api.get_stage_z()
        print(z_info)
        z = z_info['z']
    else:
        api.z_move(fixed_z)
    import time
    
    images = dict()
    for x in range(xmin, xmax, DX):
        for y in range(ymin, ymax, DY):
            print("Moving to {},{}".format(x,y))
            api.xy_move(x,y)
            tstart = time.time()
            while api.is_moving():
                time.sleep(0.1)
            
            if autofocus_all:
                r = api.autofocus()
                z_info = api.get_stage_z()
                print(z_info)
                z = z_info['z']
            else:
                z = fixed_z
            print("Move complete after {}s".format(time.time() - tstart))
            
            tstamp = time.time()
            img = api.get_image()
            dt = datetime.datetime.fromtimestamp(tstamp)
            fname = dt.strftime("%Y-%m-%d-%H_%M_%S") + "_atloc_x{}_y{}_z{}.jpg".format(x, y, z)
            fpath = "{}/{}".format(directory, fname)
            img.save(fpath)
            print("wrote {}".format(fpath))
            #res = api.image_capture_save({'x':x, 'y':y})
            #print("Image capture_save took {}s".format(time.time() - tstamp))
            #print(res.json())
            #file_ids = res.json()['file_ids']
            #images[(x,y)] = file_ids
            #TODO - record locations, timestamp, and file id
            # use influxdb?
            #print("images[({},{})] = {}".format(x,y,file_ids))

@cmds.command()
@click.argument('row', type=int)
@click.argument('col', type=int)
@click.argument('directory')
@click.option('--hostname', default='localhost')
@click.option('--port', default=8080)
@click.option('--autofocus-init', default=False)
@click.option('--autofocus-all', default=False)
@click.option('--fixed-z', default=800.0)
@click.option('--iso', default=100)
@click.option('--shutter-speed-denominator', default=20)
def scan_well(row, col, directory, hostname='localhost', port=8080, 
        autofocus_init=False, autofocus_all=False, fixed_z=2900.0, iso=100, 
        shutter_speed_denominator=20):
    
    api.init(hostname, port)
    print(api.get_head_info())
    #api.set_power_saving(False)
    xy_info = api.get_stage_xy()
    api.set_light_params('led1_on')
    api.set_resolution(2048, 1536)
    api.set_exposure_settings(iso = iso, 
            shutter_speed_denominator = shutter_speed_denominator)

    print("Using exposure iso {} with shutter 1/{}".format(iso, shutter_speed_denominator))
    xrange= xy_info['x.range']
    XMAX = xrange[1] // 2 
    yrange= xy_info['y.range'] 
    YMAX = yrange[1] // 2 
    MIN_STEP=105 
    DX=MIN_STEP*27 #2840 
    DY=MIN_STEP*20 #213
    
    if autofocus_init:
        api.autofocus()
        r = api.autofocus()
        z_info = api.get_stage_z()
        print(z_info)
        z = z_info['z']
    else:
        api.z_move(fixed_z)
        z = fixed_z
    import time
    
    positions = get_positions_for_well(row, col)
    images = dict()
    for x,y,x_idx,y_idx in positions:
        print("Moving to {},{}".format(x,y))
        api.xy_move(x,y)
        tstart = time.time()
        while api.is_moving():
            time.sleep(0.1)
        
        if autofocus_all:
            r = api.autofocus()
            z_info = api.get_stage_z()
            print(z_info)
            z = z_info['z']
        else:
            z = fixed_z
        print("Move complete after {}s".format(time.time() - tstart))
        
        tstamp = time.time()
        img = api.get_image()
        dt = datetime.datetime.fromtimestamp(tstamp)
        fname = dt.strftime("%Y-%m-%d-%H_%M_%S") + "_atloc_x{}_y{}_z{}.jpg".format(x, y, z)
        fpath = "{}/{}".format(directory, fname)
        img.save(fpath)
        print("wrote {}".format(fpath))
        #res = api.image_capture_save({'x':x, 'y':y})
        #print("Image capture_save took {}s".format(time.time() - tstamp))
        #print(res.json())
        #file_ids = res.json()['file_ids']
        #images[(x,y)] = file_ids
        #TODO - record locations, timestamp, and file id
        # use influxdb?
        #print("images[({},{})] = {}".format(x,y,file_ids))


#CAL_OFFSET_X=0 #um
#CAL_OFFSET_Y=-0.2 #um
def get_well_center(row, col):
    #plate is oriented such that row is horizontal (x direction)
    # and y is vertical 
    # we will assume notch is at bottom (near buttons)
    # so col 12 is near the the zero y position
    # and row H is near the zero x position for nunc/falcon
    VERT_OFFSET_TO_FIRST_COL_CENTER = 14.36 #labeled as X1 typically
    HORIZ_OFFSET_TO_FIRST_ROW_CENTER = 11.22 #label as y1
    INTER_WELL_SPACING=9
    
    #row 0 is 'A' but y 0 is at 'H' so flip the row index
    row_rel = 7 - row

    y = VERT_OFFSET_TO_FIRST_COL_CENTER + col*INTER_WELL_SPACING
    x = HORIZ_OFFSET_TO_FIRST_ROW_CENTER + row_rel*INTER_WELL_SPACING
    #mm to um
    x_um =  int(1000*x)
    y_um = int(1000*y)
    return x_um, y_um

def pos_round(x_um, y_um):
    #round position to nearest whole multiple of step resolution
    return MIN_STEP*(x_um // MIN_STEP), MIN_STEP*(y_um // MIN_STEP)
MIN_STEP=105 
DX=MIN_STEP*26 #2730 
DY=MIN_STEP*20 #2100
WELL_DIAMETER=9

def get_positions_for_well(row_idx, col_idx):
    cx,cy = get_well_center(row_idx, col_idx)
    #generate square tile set for left to right - top to bottom scan
    VERT_SLICES=4
    HORIZ_SLICES=4
    ul_x = cx - DX*HORIZ_SLICES/2 + DX/2
    ul_y = cy - DY*VERT_SLICES/2 + DY/2

    ul_x, ul_y = pos_round(ul_x, ul_y)
    
    positions = []
    #FIXME - this only covers a portion of the well
    for j in range(VERT_SLICES):
        y_pos = ul_y + j*DY
        for i in range(HORIZ_SLICES):
            x_pos = ul_x + i*DX
            positions.append((x_pos, y_pos, i, j))
    
    return positions

@cmds.command()
@click.argument('directory')
@click.option('--hostname', default='localhost')
@click.option('--port', default=8080)
@click.option('--z-default', default=3240.0)
def scan_32x_ss(directory, hostname='localhost', port=8080, z_default=3230):
    api.init(hostname, port)
    print(api.get_head_info())
    xy_info = api.get_stage_xy()

    xrange= xy_info['x.range']
    XMAX = xrange[1] // 2 
    yrange= xy_info['y.range'] 
    YMAX = yrange[1] // 2 
    MIN_STEP=105 
    DX=MIN_STEP*27 #2840 
    DY=MIN_STEP*20 #213
    
    api.z_move(z_default)
    r = api.set_z_focus_range(3200, 3260)
    print(r)
    r = api.autofocus(z_default=z_default, z_offset=-30)
    print(r)
    print(api.get_stage_z())
    import time
    
    for col in [3, 4, 9, 10]:
        for row in range(1,9)[::-1]:
            col_idx = col-1
            row_idx = row - 1

            for x,y,tile_x_idx, tile_y_idx in get_positions_for_well(row_idx, col_idx):
                print("rc {},{}".format(row,col))
                print("Moving to {},{}".format(x,y))
                api.xy_move(x,y)
                tstart = time.time()
                while api.is_moving():
                    time.sleep(0.1)
                
                xy = api.get_stage_xy()
                x,y = xy['x'], xy['y'] #actual x,y may differ from requested due to stepper min res
                print("Move complete after {}s".format(time.time() - tstart))
            
                #r = api.autofocus(z_default=z_default, z_offset=-30)
                #print(r.content)
                z_info = api.get_stage_z()
                print(z_info)
                z = z_info['z']
                print("autofocused to {}".format(z))
                
                tstamp = time.time()
                img = api.get_image()
                dt = datetime.datetime.fromtimestamp(tstamp)
                #z = fixed_z
                fname = dt.strftime("%Y-%m-%d-%H_%M_%S") + "_atloc_x{}_y{}_z{}_r{}_c{}_xt{}_yt{}.jpg".format(x, y, z, 
                        row, col, tile_x_idx, tile_y_idx)
                fpath = "{}/{}".format(directory, fname)
                img.save(fpath)
                print("wrote {}".format(fpath))
                #res = api.image_capture_save({'x':x, 'y':y})
                #print("Image capture_save took {}s".format(time.time() - tstamp))
                #print(res.json())
                #file_ids = res.json()['file_ids']
                #images[(x,y)] = file_ids
                #TODO - record locations, timestamp, and file id
                # use influxdb?
                #print("images[({},{})] = {}".format(x,y,file_ids))
if __name__ == "__main__":
    cmds()
