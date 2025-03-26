"""
Módulo para cálculos de ángulos solares y funciones relacionadas.
Proporciona funciones para calcular el ángulo cenital solar, coseno theta,
y reflectancia para imágenes GOES-16.
"""

import numpy as np
from datetime import datetime
from pyorbital import astronomy
from pyspectral.near_infrared_reflectance import Calculator

def calculate_sun_zenith(fecha, extent, data):
    """
    Calcula el ángulo cenital solar para una región y tiempo específicos.
    
    Args:
        fecha (datetime): Fecha y hora UTC
        extent (list): [xmin, xmax, ymin, ymax] - Extensión geográfica
        data (numpy.ndarray): Array 2D con los datos para obtener dimensiones
    
    Returns:
        numpy.ndarray: Ángulo cenital solar para cada pixel
    """
    print(fecha)
    lat = np.linspace(extent[3], extent[2], data.shape[0])
    lon = np.linspace(extent[0], extent[1], data.shape[1])
    xx, yy = np.meshgrid(lon, lat)
    lats = xx.reshape(data.shape[0], data.shape[1])
    lons = yy.reshape(data.shape[0], data.shape[1])
    return astronomy.sun_zenith_angle(fecha, lats, lons)

def calculate_cos_theta(fecha, extent, data):
    """
    Calcula el coseno del ángulo cenital solar con correcciones.
    
    Args:
        fecha (datetime): Fecha y hora UTC
        extent (list): [xmin, xmax, ymin, ymax] - Extensión geográfica
        data (numpy.ndarray): Array 2D con los datos para obtener dimensiones
    
    Returns:
        numpy.ndarray: Coseno del ángulo cenital solar corregido
    """
    MinCosTheta = 0.019
    # Calcular coseno theta usando el ángulo cenital
    CosTheta = np.cos(calculate_sun_zenith(fecha, extent, data)*np.pi/180.0)
    CosTheta[np.where(CosTheta < MinCosTheta)] = np.nan

    return np.array(CosTheta)

def calculate_rfl39(fecha, extent, data1, data2):
    """
    Calcula la reflectancia para la banda 3.9 µm.
    
    Args:
        fecha (datetime): Fecha y hora UTC
        extent (list): [xmin, xmax, ymin, ymax] - Extensión geográfica
        data1 (numpy.ndarray): Datos de la banda 7
        data2 (numpy.ndarray): Datos de temperatura de brillo
    
    Returns:
        numpy.ndarray: Reflectancia calculada
    """
    # Calcular ángulo cenital solar
    zenith = calculate_sun_zenith(fecha, extent, data1)
    
    # Calcular componente solar (banda 3.7 µm)
    refl39 = Calculator('GOES-16', 'abi', 'ch7')
    return refl39.reflectance_from_tbs(zenith, data1, data2)

