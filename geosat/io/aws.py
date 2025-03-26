"""
AWS Utilities for GOES-16 Satellite Data.

This module provides utilities for accessing and processing GOES-16 satellite data 
from AWS S3 buckets. Focused on anonymous access for public GOES data.

Author: SENAMHI
"""

import s3fs
import numpy as np
import concurrent.futures

from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import List, Optional, Tuple, Union, Any

# Default parameters
DEFAULT_WORKERS = 6
TIME_DELAY = 12  # minutes
DEFAULT_SATELLITE = 16

DateInput = Union[str, List[str], Tuple[str, str]]
DateRange = Tuple[datetime, datetime]

class GoesAWSDownloader:
    """
    A utility class for accessing and processing GOES-16 satellite data from AWS S3.

    This class provides functionality to:
    - List available GOES satellite files on AWS S3
    - Filter files by date range and patterns
    - Download files concurrently
    - Process date inputs flexibly

    All AWS access is anonymous, suitable for public GOES data access.

    Attributes:
        product: The type of product to retrieve (e.g., "CMIPF")
        start_date: Starting date for data retrieval
        end_date: Ending date for data retrieval
        all_files: Whether to retrieve all files in date range
        workers: Number of concurrent download workers
        abi_level: ABI processing level (L1b or L2)
        fs: Anonymous S3 filesystem connection
        satellite: GOES satellite number (default 16)
    """

    def __init__(
        self, 
        product: str,
        date: Optional[DateInput] = None,
        **kwargs: Any
    ) -> None:
        """
        Initialize the GOES AWS downloader.

        Args:
            product: The product type to retrieve
            date: Date or date range for data retrieval
            **kwargs: Additional configuration options
                - all_files: Bool, retrieve all files
                - workers: Int, concurrent download workers
                - satellite: Int, GOES satellite number
        """
        self.all_files = kwargs.get("all_files", False)
        self.workers = kwargs.get("workers", DEFAULT_WORKERS)
        self.satellite = kwargs.get("satellite", DEFAULT_SATELLITE)

        self.product = product
        self.start_date, self.end_date = self._process_date_input(date)

        # Setup S3 connection
        self.abi_level = "L1b" if self.product == "RadF" else "L2"
        self.fs = s3fs.S3FileSystem(anon=True)
        self.bucket_goes = f"noaa-goes{self.satellite}"

    def _process_date_input(self, date: Optional[DateInput]) -> DateRange:
        """
        Process the input date and return start and end dates.

        Args:
            date: Input date specification

        Returns:
            Tuple of start and end datetime objects

        Raises:
            ValueError: If date format is invalid or dates are invalid
        """
        if date is None:
            now = datetime.now(UTC) - timedelta(minutes=TIME_DELAY)
            now = now.replace(
                minute=now.minute - now.minute % 10,
                second=0,
                microsecond=0
            )
            return now, now

        if isinstance(date, (list, tuple)) and len(date) == 2:
            start_date = self._parse_date(date[0])
            end_date = self._parse_date(date[1])
        elif isinstance(date, str):
            start_date = self._parse_date(date)
            end_date = start_date
        else:
            raise ValueError(
                "El parámetro 'date' debe ser un string o tupla/lista con dos fechas válidas."
            )

        if start_date > end_date:
            raise ValueError("La fecha de inicio no puede ser mayor que la fecha de fin.")

        return start_date, end_date

    def _parse_date(self, date: str) -> datetime:
        """
        Parse a date string into a datetime object.

        Args:
            date: Date string to parse

        Returns:
            datetime: Parsed datetime object

        Raises:
            ValueError: If date format is invalid
        """
        try:
            if len(date) == 12:
                return datetime.strptime(date, '%Y%m%d%H%M')
            elif len(date) == 10:
                self.all_files = True
                return datetime.strptime(date, '%Y%m%d%H')
            elif len(date) == 8:
                self.all_files = True
                return datetime.strptime(date, '%Y%m%d')
            else:
                raise ValueError("Formato de fecha inválido.")
        except ValueError:
            raise ValueError(
                "Formato de fecha inválido. Use '%Y%m%d%H%M', '%Y%m%d%H' o '%Y%m%d'."
            )

    def list_available_files(self) -> Optional[np.ndarray]:
        """
        List available files in the specified S3 path.

        Returns:
            np.ndarray: Array of available file paths or None if no files found
        """
        if self.start_date.replace(tzinfo=None) > datetime.now(UTC).replace(tzinfo=None):
            print("\t[ ERROR ] Fecha ingresada mayor a la actual.")
            return None

        all_files_list = []
        current_date = self.start_date

        s3_path = f"{self.bucket_goes}/ABI-{self.abi_level}-{self.product}"
        while current_date <= self.end_date:
            s3_link = f"s3://{s3_path}/{current_date:%Y/%j/%H}"

            try:
                s3_list = np.array(self.fs.ls(s3_link))
                if s3_list.size > 0:
                    all_files_list.extend(s3_list)
            except Exception as e:
                print("\t[ WARNING ] Sin ficheros encontrados.")
            current_date += timedelta(hours=1)

        return np.array(all_files_list)

    def filter_files(
        self,
        all_files: np.ndarray,
        pattern: Optional[List[str]] = None,
        interval: int = 10
    ) -> np.ndarray:
        """
        Filter files based on pattern and time interval.

        Args:
            all_files: Array of file paths to filter
            pattern: List of patterns to match
            interval: Time interval for filtering (minutes)

        Returns:
            np.ndarray: Filtered array of file paths
        """
        import re
        from numpy.core.defchararray import find

        # Filter files containing pattern
        if pattern is not None:
            files = []
            for p in pattern:
                files.extend(all_files[find(all_files, p) != -1])
        else:
            files = all_files

        # Extract timestamp from each file
        filtered_files = []
        for file in files:
            match = re.search(r'_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})', file)
            if match:
                year, day_of_year, hour, minute, second = map(int, match.groups())
                total_minutes = hour * 60 + minute
                
                # Create datetime objext from components
                file_date = datetime.strptime(f"{year}{day_of_year}{hour}{minute}",
                                              "%Y%j%H%M")
                
                if (self.start_date.replace(tzinfo=None) <= file_date <= self.end_date.replace(tzinfo=None) and total_minutes % interval == 0):  # Verificar si cae en el intervalo deseado
                    filtered_files.append(file)

        return np.array(filtered_files)

    def download(
        self,
        filename: str,
        local_path: Union[str, Path] = "./",
        force: bool = False
    ) -> Optional[str]:
        """
        Download a file from S3 to local path.

        Args:
            filename: S3 file path to download
            local_path: Local directory to save file
            force: Whether to force download if file exists

        Returns:
            str: Local file path if download successful, None otherwise
        """
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_file = local_path / Path(filename).name

        if local_file.exists() and not force:
            local_size = local_file.stat().st_size
            aws_size = self.fs.info(filename)["size"]

            if aws_size <= local_size:
                print(f"\t[ COMPLETE ] El archivo ya existe y está completo: {Path(filename).name}")
                return None

        try:
            self.fs.get(filename, str(local_file))
            print(f"\t[ NEW ] Descarga completada: {local_file}")
            return str(local_file)
        except Exception as e:
            print(f"\t[ ERROR ] Error al descargar {Path(filename).name}: {e}")
            return None

    def get_files(
        self,
        filenames: List[str],
        local_path: Union[str, Path] = "./"
    ) -> None:
        """
        Download multiple files concurrently.

        Args:
            filenames: List of S3 file paths to download
            local_path: Local directory to save files
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(self.download, filename, local_path): filename
                for filename in filenames
            }
            for future in concurrent.futures.as_completed(futures):
                filename = Path(futures[future]).name
                try:
                    future.result()
                except Exception as e:
                    print(f"\t[ERROR] {filename} {e}")

