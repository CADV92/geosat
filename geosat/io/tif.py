"""
Module for reading TIFF files using rasterio.

This module provides the TIFReader class, which can read TIFF files and extract data
based on specified geographic extents.
"""
import rasterio
from rasterio.windows import from_bounds

class TIFReader:
    """
    A reader for TIFF files that extracts data within a specified extent.

    Attributes:
        file (str): The file path to the TIFF file.
        data (ndarray): The extracted data from the TIFF file.
        extent (list): The geographical extent of the data.
    """
    def __init__(self, file, extent=None):
        """
        Initializes the TIFReader with a file and optional extent.

        Args:
            file (str): The path to the TIFF file.
            extent (list, optional): The geographical extent to extract. Defaults to None.
        """
        self.file = file
        self.data, self.extent = self.read(file, extent)

    def read(self, file, extent=None):
        """
        Reads data from a TIFF file and extracts it based on the extent.

        Args:
            file (str): The path to the TIFF file.
            extent (list, optional): The geographical extent to extract. Defaults to None.

        Returns:
            tuple: A tuple containing the data and its full extent.
        """
        with rasterio.open(file) as src:
            # Data from tif
            data = src.read(1)
            transform = src.transform

            # Get extent
            full_extent = self.get_extent(transform,
                                src.width,
                                src.height)
            
            # Subarea
            if not extent is None:
                data, extent = self.subarea(data, full_extent)
            
            return data, full_extent
    
    def get_extent(self, transform, width, height):
        """
        Calculates the geographical extent of the TIFF data.

        Args:
            transform (Affine): The affine transformation of the TIFF.
            width (int): The width of the TIFF data.
            height (int): The height of the TIFF data.

        Returns:
            list: A list representing the geographical extent [lon_min, lon_max, lat_min, lat_max].
        """
        # Making extent
        extent = [
            transform.c,    # Lon min
            transform.c + width * transform.a,  # Lon max
            transform.f + height * transform.e, # Lat min
            transform.f     # Lat max
        ]
        return extent

    def subarea(self, extent):
        """
        Extracts a subarea from the data based on the given extent.

        Args:
            extent (list): The geographical extent to extract.

        Returns:
            tuple: A tuple containing the subarea data and its extent.
        """
        sub_latn = extent[2] if self.extent[2]<extent[2] else self.extent[2]
        sub_latx = extent[3] if self.extent[3]>extent[3] else self.extent[3]
        sub_lonn = extent[0] if self.extent[0]<extent[0] else self.extent[0]
        sub_lonx = extent[1] if self.extent[1]>extent[1] else self.extent[1]

        extent = [sub_lonn, sub_lonx, sub_latn, sub_latx]
        

        start_col = int((sub_lonn - self.extent[0])/(self.extent[1]-self.extent[0])*self.data.shape[1])
        start_row = int((self.extent[3] - sub_latx)/(self.extent[3]-self.extent[2])*self.data.shape[0])
        end_col = int((sub_lonx - self.extent[0])/(self.extent[1]-self.extent[0])*self.data.shape[1])
        end_row = int((self.extent[3] - sub_latn)/(self.extent[3]-self.extent[2])*self.data.shape[0])
        return self.data[start_row:end_row, start_col:end_col], extent
