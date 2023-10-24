#!/usr/bin/python3
import click
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
def scan_full(hostname='localhost', port=8080):
    api.init(hostname, port)
    print(api.get_head_info())
    xy_info = api.get_stage_xy()

    xrange= xy_info['x.range']
    XMAX = xrange[1] // 2
    yrange= xy_info['y.range']
    YMAX = yrange[1] // 2
    MIN_STEP=105
    DX=MIN_STEP*27 #2840
    DY=MIN_STEP*20 #2130

    api.autofocus()
    import time
    
    images = dict()
    for x in range(0, XMAX, DX):
        for y in range(0, YMAX, DY):
            print("Moving to {},{}".format(x,y))
            api.xy_move(x,y)
            tstart = time.time()
            while api.is_moving():
                time.sleep(0.1)
            
            print("Move complete after {}s".format(time.time() - tstart))
            
            tstamp = time.time()
            res = api.image_capture_save({'x':x, 'y':y})
            print(res.json())
            file_ids = res.json()['file_ids']
            images[(x,y)] = file_ids
            #TODO - record locations, timestamp, and file id
            # use influxdb?
            print("images[({},{})] = {}".format(x,y,file_ids))

if __name__ == "__main__":
    cmds()
