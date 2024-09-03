from PIL import Image
import sys
import math

def dpc(img1, img2):
    img1 = img1.convert('L')  # Convert to grayscale
    img2 = img2.convert('L')  # Convert to grayscale

    # Ensure images have the same size
    if img1.size != img2.size:
        raise ValueError("Images must have the same dimensions")

    # Create a new image to store the result
    result = Image.new('L', img1.size)

    # Iterate over pixels and subtract grayscale values
    for x in range(img1.width):
        for y in range(img1.height):
            pixel1 = img1.getpixel((x, y))
            pixel2 = img2.getpixel((x, y))
            delta = pixel1 - pixel2
            vsum = pixel1 + pixel2
            dpc = delta/vsum if vsum != 0 else -1
            dpc_8bit = int((1 + dpc)*128)
            result.putpixel((x, y), dpc_8bit)

    return result

img_led1 = Image.open(sys.argv[1])
img_led2 = Image.open(sys.argv[2])

v1s = [t[0] for t in img_led1.getdata()]
v2s = [t[0] for t in img_led2.getdata()]
vsum = [v1 + v2 for v1,v2 in zip(v1s, v2s)]
vdelta = [v1 - v2 for v1,v2 in zip(v1s, v2s)]
dpc = [vd/vs if vs !=0 else math.nan for vs,vd in zip(vsum, vdelta)]

