from setuptools import setup, find_packages

setup(
    name="geosat",
    version="0.0",
    description="Utilities for processing GOES satellite data",
    author="SENAMHI",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.26.4",
        "s3fs>=2025.2.0",
        "pytz>=2024.1",
        "concurrent-futures",
        "pathlib",
        "Pillow>=10.4.0",
        "matplotlib>=3.8.4",
        "cadv>=1.3.0",
        "GDAL>=3.9.1",
        "cartopy>=0.24.0",
        "netCDF4>=1.7.1",
    ],
    python_requires=">=3.12",  # Based on Python version in nuna env
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
