__all__ = [
    "ppm_pixel"
      , "gen_ppm"
          , "gen_ppm_photo_image"
]


from six.moves.tkinter import (
    PhotoImage,
)


def ppm_pixel(rgb):
    if len(rgb) != 3:
        raise ValueError("color size %d must be 3" % (len(rgb),))
    return bytes(rgb)

def gen_ppm(framebuffer, width):
    l = len(framebuffer)
    height = l // width
    exp_l = width * height
    if l != exp_l:
        raise ValueError("framebuffer size %d is not aligned %dx%d = %d" % (
            l, width, height, exp_l
        ))
    header = ("P6\n%d %d\n255\n" % (width, height)).encode("ascii")
    data = b"".join(map(ppm_pixel, framebuffer))
    return header + data

def gen_ppm_photo_image(*a, **kw):
    return PhotoImage(data = gen_ppm(*a, **kw))
