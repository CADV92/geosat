import os
from pathlib import Path

def list_local_files(directory, extension=None):
    """
    Lista archivos en un directorio local, filtrados por extensión.

    Args:
        directory (str): Ruta al directorio.
        extension (str, optional): Extensión del archivo para filtrar (e.g., '.nc', '.tiff').
    
    Returns:
        list: Lista de rutas de archivos.
    """
    directory = Path(directory)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"El directorio {directory} no existe o no es válido.")
    
    files = directory.glob(f"*{extension}" if extension else "*")
    return [str(file) for file in files if file.is_file()]