import io
import numpy as np
from pathlib import Path
from cadv.canvas import Canvas
from PIL import Image, WebPImagePlugin

def single_band(data, extent, cmap="viridis", vmin=None, vmax=None, **kwargs):
    vmin = vmin if not vmin is None else np.nanmin(data)
    vmax = vmax if not vmax is None else np.nanmax(data)

    ticks = kwargs.get("ticks", None)
    shapes = kwargs.get("shapes", None)
    format = kwargs.get("format", None)
    save = kwargs.get("save", None)

    try: 
        if data.ndim != 2:
            raise ValueError("El array 'data' debe se 2D para la visualización.")
        
        # Visualización
        canva = Canvas(extent=extent, grid=False, darkStyle=True, dpi=150)
        img = canva.imshow(data, extent, cmap=cmap, vmin=vmin, vmax=vmax)

        # shapes
        if shapes:
            process_shapes(canva, shapes)

        # Añadiendo colorbar
        if ticks is None:
            ticks = np.arange(np.floor(vmin/10)*10, vmax, 10)
        canva.colorbar(img, ticks=ticks[1:])

        # format: texts and logo
        if format:
            process_format(canva, format)

        # Guardando figura
        if save:
            buf = io.BytesIO()
            canva.save_img(buf)
            buf.seek(0)
            image = Image.open(buf)
            image = image.convert("RGB")
            # creando directorio
            Path(save).parent.mkdir(parents=True, exist_ok=True)
            image.save(save, format="JPEG", lossless=True, quality=80, dpi=(100, 100), optimize=True, progressive=True)

    except Exception as e:
        print(f"Error al visualizar el array: {e}")
    return canva

def sandwich_composite(data1, data2, extent, cmap1="gray", cmap2="rainbow", alpha=70, **kwargs):
    alpha = kwargs.get("alpha", 70)
    save = kwargs.get("save", "sandwich.jpg")

    def render_band(data, extent, cmap, vmin=None, vmax=None):
        vmin = np.nanmin(data) if vmin is None else vmin
        vmax = np.nanmin(data) if vmax is None else vmax

        buf = io.BytesIO()
        canva = Canvas(extent=extent, grid=False, darkStyle=True, dpi=150)
        img = canva.imshow(data, extent, cmap=cmap, vmin=vmin, vmax=vmax)

        canva.save_img(buf)
        buf.seek(0)
        return Image.open(buf).convert("RGBA")
    
    # Generar imágenes en memoria
    img1 = render_band(data1, extent, cmap1)
    img2 = render_band(data2, extent, cmap2)

    # Ajustar la transparencia de la segunda imagen
    img2 = img2.copy()
    img2.putalpha(int(alpha * 255 / 100))

    # Fusionar imágenes
    blended = Image.alpha_composite(img1, img2)

    # Guardar imagen finalsave
    if save:
        Path(save).parent.mkdir(parents=True, exist_ok=True)
        blended.convert("RGB").save(save, format="JPEG", quality=90)

def process_format(canva, properties):
    def format_text(param):
        weight = param.get("weight", "normal")
        size = param.get("size", 1)
        fontname = param.get("fontname", "DejaVu Sans")
        align = param.get("align", "center")
        loc = param.get("loc", "c")
        canva.title(param.get("text"), weight=weight,
                    size=size, fontname=fontname,
                    align=align, loc=loc)
        
    # Añadiendo título
    if properties.get("title"):
        format_text(properties.get("title"))
    if properties.get("time"):
        format_text(properties.get("time"))
    
    # Añadiendo logo
    if properties.get("logo"):
        canva.add_logo(properties.get("logo"))


def process_shapes(canva, shapes):
    """
    Procesa y agrega shapes al canvas.

    Parameters:
    - canva (Canvas): Objeto de visualización.
    - shapes (dict): Diccionario con información de shapes:
        {
            "shapes": [list of shapes],
            "width": [list or scalar],
            "alpha": [list or scalar],
            "lcolor": [list or scalar]
        }
    """
    def get_value(param, idx, default):
        if isinstance(param, list):
            return param[idx] if idx < len(param) else default
        elif isinstance(param, (int, float, str)):
            return param
        return default

    if shapes.get("shapes"):
        for idx, shp in enumerate(shapes["shapes"]):
            factor = idx * 0.15

            # Ancho de línea
            width = get_value(shapes.get("width"), idx, 0.8)
            if not isinstance(width, (int, float)):
                width = max(0.1, 0.8 - factor)
            else:
                min_scl, max_scl = 2, 15
                width = canva.scalling_value(width)
                width = (width - min_scl) / (max_scl - min_scl)

            # Transparencia (alpha)
            alpha = get_value(shapes.get("alpha"), idx, 1 - factor * 2)
            alpha = max(0.2, alpha) if alpha <= 0.2 else alpha

            # Color de línea
            lcolor = get_value(shapes.get("lcolor"), idx, "black")

            # Añadiendo shapefile
            canva.add_shp(shp, lcolor=lcolor, width=width, alpha=alpha)

