from __future__ import annotations

import math

import daria as da


class CoordinateSystem:
    """Class for coordinate system for images.

    A coordinate system has knowledge about the conversion of pixels (in standard format),
    i.e., y,x pixels with (0,0) being identified with the top left corner. Conversion maps
    from pixel to coordinates and vice-versa are provided.

    Attributes:

    """

    def __init__(self, img: da.Image, dim: int = 2):
        """Generate a coordinate system based on the metadata of an existing image."""

        # Copy metadata from image. Will be used for conversions.
        self._width: float = img.width
        self._height: float = img.height
        self._num_pixels_width: int = img.num_pixels_width
        self._num_pixels_height: int = img.num_pixels_height

        # Determine the coordinate, corresponding to the origin pixel (0,0), i.e.,
        # the top left corner. NOTE img.origo corresponds to the lower left corner
        # FIXME make it more consistent throughout files
        self._coordinate_of_origin_pixel: tuple[float] = (
            img.origo[0],
            img.origo[1] + self._height,
        )

        # Determine the pixel, corresponding to the physical origin (0,0)
        self._pixel_of_origin_coordinate: tuple[int] = self.coordinateToPixel((0, 0))

        # Determine the bounding box of the image, in physical dimensions,
        # also defining the effective boundaries of the coordinate system.
        # for this, address the lower left and upper right corners.
        xmin, ymin = self.pixelToCoordinate(img.corners["lowerleft"])
        xmax, ymax = self.pixelToCoordinate(img.corners["upperright"])
        self.domain = {
            "xmin": xmin,
            "xmax": xmax,
            "ymin": ymin,
            "ymax": ymax,
        }

    def pixelToCoordinate(self, pixel: tuple[int]) -> tuple[float]:
        """Conversion from pixel in standard format to coordinate in physical units.

        Arguments:
            pixel (tuple of int): pixel location; in 2d, first and second arguments hold
                the y- and x-positions

        Returns:
            float: x-coordinate in physical units
            float: y-coordinate in physical units
        """
        # Fetch the top left corner.
        x0, y0 = self._coordinate_of_origin_pixel

        # Fetch the single pixel indices - note their order
        y_pixel, x_pixel = pixel

        # Obtain the coordinate by scaling - for the y-coordinate, one also has to flip
        # the y-axis due to the convention in numbering of pixels, and therefore subtract.
        x = x0 + x_pixel / self._num_pixels_width * self._width
        y = y0 - y_pixel / self._num_pixels_height * self._height

        # Return final coordinates
        return x, y

    def coordinateToPixel(self, coordinate: tuple[float]) -> tuple[int]:
        """Conversion from coordinate in physical units to pixel in standard format.

        Inverse to pixelToCoordinate, modulo rounding.

        Arguments:
            coordinate (tuple of float): coordinate in physical units

        Returns:
            int: pixel index locating the y-coordinate
            int: pixel index location the x-coordinate
        """
        # Fetch the top left corner.
        x0, y0 = self._coordinate_of_origin_pixel

        # Unpack the coordinate
        x, y = coordinate

        # Invert pixelToCoordinate, and apply floor to obtain an integer
        pixel_x: int = math.floor((x - x0) * self._num_pixels_width / self._width)
        pixel_y: int = math.floor(-(y - y0) * self._num_pixels_height / self._height)

        # Return final result
        return pixel_y, pixel_x