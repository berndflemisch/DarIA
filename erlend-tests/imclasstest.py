import daria as da
import cv2
import numpy as np

im = cv2.imread("images/originals/Profilbilde.jpg")


# print(im.shape[1])

img = da.Image(im, [0, 0], 1, 1)


print(img.dx)


img2 = da.extractROI(img, [0.2, 0.75], [0.4, 0.8])

img2.write()