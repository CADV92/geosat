import os
import numpy as np
from datetime import datetime, timezone
from osgeo import osr, gdal
import cartopy.crs as ccrs
from netCDF4 import Dataset
from ..utils.solar import calculate_cos_theta, calculate_sun_zenith

class GOESReproject:
    """
    Clase para manejar la reproyección de imágenes GOES-16 a proyección PlateCarree.
    Basada en el procesamiento de imágenes GOES-16 del SENAMHI.
    """
    def __init__(self, file_path):
        """
        Inicializa el reproyector con un archivo GOES-16.
        
        Args:
            file_path (str): Ruta al archivo GOES-16 NetCDF
        """
        self.filename = file_path
        self.file = Dataset(file_path)
        self.date = datetime.strptime(
            self.file.time_coverage_start, 
            '%Y-%m-%dT%H:%M:%S.%fZ'
        )
        self.date = self.date.replace(tzinfo=timezone.utc)
        self.projection = self._proj_info()
        self.xy_resolution = float(
            self.file.spatial_resolution.split('km')[0]
        )
        self.product = os.path.basename(file_path).split('_')[1]
        
    def _proj_info(self):
        """
        Obtiene la información de proyección del archivo GOES.
        
        Returns:
            dict: Información de proyección
        """
        proj_info = {
            attrname: getattr(
                self.file.variables['goes_imager_projection'], 
                attrname
            ) for attrname in self.file.variables['goes_imager_projection'].ncattrs()
        }
        
        self.x = self.file.variables['x']
        self.y = self.file.variables['y']
        x, y = self.x[:], self.y[:]
        height = proj_info['perspective_point_height']
        
        proj_info['image_extent'] = [
            x.min()*height, x.max()*height,
            y.min()*height, y.max()*height
        ]
        return proj_info

    def get_data(self, variable, skip=1):
        """
        Obtiene los datos de una variable del archivo.
        
        Args:
            variable (str): Nombre de la variable
            skip (int): Factor de sub-muestreo
        
        Returns:
            numpy.ndarray: Datos de la variable
        """
        if 'extent' in self.projection:
            llx, urx, lly, ury = self.projection['extent']
            return self.file.variables[variable][ury:lly:skip, llx:urx:skip]
        else:
            return self.file.variables[variable][::skip, ::skip]

    def _get_geotransform(self, extent, nrows, ncols):
        """
        Calcula la transformación geográfica para la reproyección.
        
        Args:
            extent (list): [xmin, xmax, ymin, ymax]
            nrows (int): Número de filas
            ncols (int): Número de columnas
        
        Returns:
            list: Parámetros de transformación geográfica
        """
        resx = (extent[1] - extent[0])/ncols
        resy = (extent[3] - extent[2])/nrows
        return [extent[0], resx, 0, extent[3], 0, -resy]

    def reproject(self, variable, target_extent, resolution=None, 
                output_format=None, output_path='./', filename=None):
        """
        Reproyecta los datos a coordenadas PlateCarree.
        
        Args:
            variable (str): Variable a reproyectar
            target_extent (list): [xmin, xmax, ymin, ymax]
            resolution (float): Resolución en km (opcional)
            output_format (str): Formato de salida ('GTiff' o 'NETCDF')
            output_path (str): Directorio de salida
            filename (str): Nombre del archivo de salida
        
        Returns:
            numpy.ndarray: Datos reproyectados
        """
        gdal.PushErrorHandler('CPLQuietErrorHandler')
        
        # Configurar proyección de salida
        self.projection['MapProject'] = ccrs.PlateCarree()
        raw = gdal.Open(f'NETCDF:{self.filename}:{variable}')
        metadata = raw.GetMetadata()
        
        # Obtener factores de escala y offset
        if variable == 'DQF':
            scale, offset = 1, 0
        else:
            scale = float(metadata.get(variable + '#scale_factor'))
            offset = float(metadata.get(variable + '#add_offset'))
        
        # Calcular dimensiones de salida
        if resolution is not None:
            KM_PER_DEGREE = 111.32
            sizex = int((target_extent[1]-target_extent[0])*KM_PER_DEGREE/resolution)
            sizey = int((target_extent[3]-target_extent[2])*KM_PER_DEGREE/resolution)
        else:
            sizex = self.get_data(variable).shape[0]
            sizey = self.get_data(variable).shape[1]

        # Configurar sistemas de referencia
        source_proj = osr.SpatialReference()
        source_proj.ImportFromProj4(raw.GetProjectionRef())
        
        target_proj = osr.SpatialReference()
        target_proj.ImportFromProj4(
            '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
        )
        
        # Crear grid de salida
        driver = gdal.GetDriverByName('MEM')
        grid = driver.Create('grid', sizex, sizey, 1, gdal.GDT_Float32)
        grid.SetProjection(target_proj.ExportToWkt())
        
        geotransform = self._get_geotransform(
            target_extent, 
            grid.RasterYSize, 
            grid.RasterXSize
        )
        grid.SetGeoTransform(geotransform)
        
        # Reproyectar
        gdal.ReprojectImage(
            raw, grid,
            source_proj.ExportToWkt(),
            target_proj.ExportToWkt(),
            gdal.GRA_NearestNeighbour,
            options=['NUM_THREADS=ALL_CPUS']
        )
        
        # Procesar datos
        data = grid.ReadAsArray()
        data = data * scale + offset
        
        if variable == 'Rad':
            data = self._process_radiance(data, target_extent)
        elif variable == 'CMI':
            data = self._process_cmi(data)
        
        grid.GetRasterBand(1).SetNoDataValue(-1)
        grid.GetRasterBand(1).WriteArray(data)

        # Exportar si se especifica
        if output_format:
            out_path = self._export_data(
                grid, data, output_format, output_path, 
                filename, target_extent
            )
            return {"data": data, "filename": out_path}
        
        return {"data": data}

    def _process_radiance(self, data, extent):
        """
        Procesa datos de radiancia.
        """
        band = self.file.variables['band_id'][:][0]
        if band in range(1, 7):
            kappa = self.file.variables['kappa0'][:]
            data = kappa * data
            cos_theta_values = calculate_cos_theta(
                self.date, extent, data
            )
            data_cor = data/cos_theta_values
            data_cor = np.clip(data_cor, 0, 1)
            data_cor = data_cor * 100
            return data_cor.astype(np.int16)
        elif band in range(7, 17):
            planck = [
                self.file.variables['planck_fk1'][:],
                self.file.variables['planck_fk2'][:],
                self.file.variables['planck_bc1'][:],
                self.file.variables['planck_bc2'][:]
            ]
            data = (planck[1]/(np.log((planck[0]/data)+1)) - planck[2])/planck[3]
            return data.astype(np.float16)
        return data

    def _process_cmi(self, data):
        """
        Procesa datos CMI.
        """
        band = self.file.variables['band_id'][:][0]
        if band in range(1, 7):
            data = data * 100
            return data.astype(np.uint8)
        elif band in range(7, 17):
            return data.astype(np.float16)
        return data

    def _export_data(self, grid, data, output_format, output_path, 
                filename, extent):
        """
        Exporta los datos procesados al formato especificado.
        """
        os.makedirs(output_path, exist_ok=True)
        
        if filename is None:
            filename = f"{self.product}_{self.date:%Y%m%d%H%M}"

        # out filename with path
        out_path = os.path.join(output_path, filename)
        
        if output_format == 'NETCDF':
            driver = gdal.GetDriverByName(output_format)
            driver.Register()
            export_options = ['FORMAT=NC4C', 'COMPRESS=DEFLATE']
            driver.CreateCopy(
                out_path,
                grid, 0,
                options=export_options
            )
        
        elif output_format == 'GTiff':
            driver = gdal.GetDriverByName(output_format)
            export_options = ['COMPRESS=DEFLATE']
            driver.CreateCopy(out_path, grid, 0, options=export_options)
            
            cols, rows = data.shape
            print(f"\nGTiff Exported: {os.path.split(out_path)[-1]}")
            print(f"Data Extent: {extent}")
            print(f"Grid Size: {cols} x {rows}")
            print(f"Data Min Max: {data.min()}, {data.max()}\n")

        return out_path
