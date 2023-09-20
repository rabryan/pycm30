from tkinter import *
from tkinter import ttk
from cm30_api import *
from PIL import ImageTk
import time

root = Tk()
frm = ttk.Frame(root, padding=10)
grid = frm.grid()
ttk.Label(frm , text="CM30 Control Panel").grid(column=0, row=0)

def move_rel(dx, dy):
    stage_xy = get_stage_xy()
    new_x = stage_xy['x'] + dx
    new_y = stage_xy['y'] + dy
    
    print("moving to {},{}".format(new_x, new_y))
    r = xy_move(new_x, new_y)
    print(r)

MOVE_STEP=200

def set_lowres():
    set_resolution(640, 480)

def set_highres():
    set_resolution(2048, 1536)

set_highres()

def move_up():
    print("Moving up")
    move_rel(0, -MOVE_STEP)

def move_right():
    print("Moving right")
    move_rel(MOVE_STEP, 0)

def move_left():
    print("Moving left")
    move_rel(-MOVE_STEP, 0)

def move_down():
    print("Moving down")
    move_rel(0, MOVE_STEP)

img = get_image()
render = ImageTk.PhotoImage(img)
img_label = ttk.Label(frm, image=render)
img_label.grid(column=0, row=2)

def image_refresh():
    tstart = time.time()
    try:
        img = get_image()
        print("Image captured in {} ms".format(int(1000*(time.time() - tstart))))
        render = ImageTk.PhotoImage(img)
        img_label.image = render
        img_label.configure(image=render)
    except Exception as e:
        print(e)

    root.after(1000, image_refresh)

ttk.Button(frm, text="Move Up", command=move_up).grid(column=0, row=1)
ttk.Button(frm, text="Move Left", command=move_left).grid(column=1, row=1)
ttk.Button(frm, text="Move Right", command=move_right).grid(column=2, row=1)
ttk.Button(frm, text="Move Down", command=move_down).grid(column=3, row=1)
ttk.Button(frm, text="Refresh", command=image_refresh).grid(column=4, row=1)
ttk.Button(frm, text="Autofocus", command=autofocus).grid(column=5, row=1)
def on_key_press(ev):
    print(ev)
    print(ev.keysym)
    print(ev.keycode)
    if ev.keycode == 111:
        move_up()
    elif ev.keycode == 114:
        move_right()
    elif ev.keycode == 113:
        move_left()
    elif ev.keycode == 116:
        move_down()
    elif ev.keycode == 21: #plus
        global MOVE_STEP 
        MOVE_STEP = MOVE_STEP + 100
    elif ev.keycode == 20: #minus
        MOVE_STEP = MOVE_STEP - 100
        if MOVE_STEP < 10:
            MOVE_STEP = 10

root.bind('<Key>', on_key_press)
#img_label.bind('<Key>', on_key_press)
root.geometry('1900x1200')
root.after(2000, image_refresh)
root.mainloop()
