"""
M-One Image Optimizer Service (services/image_optimizer_service.py)
------------------------------------------------------------------
Motor autônomo de otimização, redimensionamento e conversão de imagens para WebP.
Reduz o tráfego de saída (bandwidth) no Render em até 85-90% preservando nitidez.
Anti-monólito modular (< 500 linhas).
"""

import io
import os
import uuid
import logging
from pathlib import Path
from typing import Optional, Tuple, Union

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

logger = logging.getLogger("m_one.image_optimizer")

DEFAULT_QUALITY = 82
DEFAULT_MAX_DIM = 1920


def is_pillow_available() -> bool:
    """Verifica se o Pillow está disponível no ambiente."""
    return Image is not None


def optimize_image_bytes(
    raw_bytes: bytes,
    max_dim: int = DEFAULT_MAX_DIM,
    quality: int = DEFAULT_QUALITY,
) -> Tuple[bytes, str]:
    """
    Converte bytes de imagem bruta (JPEG/PNG/BMP/TIFF) para WebP otimizado.
    Corrige orientação EXIF e redimensiona caso exceda max_dim.
    Retorna (webp_bytes, 'image/webp').
    """
    if not is_pillow_available():
        return raw_bytes, "application/octet-stream"

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            # Corrige rotação automática de fotos tiradas por smartphone
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            # Preserva canal alfa (RGBA) para transparências, ou converte para RGB
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                img = img.convert("RGBA")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Redimensionamento proporcional se exceder a dimensão máxima
            width, height = img.size
            if max(width, height) > max_dim:
                ratio = min(max_dim / width, max_dim / height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            out_buf = io.BytesIO()
            img.save(out_buf, format="WEBP", quality=quality, method=6)
            return out_buf.getvalue(), "image/webp"
    except Exception as exc:
        logger.warning("Falha ao otimizar imagem para WebP: %s", exc)
        return raw_bytes, "application/octet-stream"


def optimize_file_to_webp(
    source_path: Union[str, Path],
    dest_path: Optional[Union[str, Path]] = None,
    max_dim: int = DEFAULT_MAX_DIM,
    quality: int = DEFAULT_QUALITY,
    remove_source_if_different: bool = False,
) -> Path:
    """
    Converte um arquivo existente no disco para WebP.
    Se dest_path for None, salva como <source_path_stem>.webp.
    """
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {src}")

    dst = Path(dest_path) if dest_path else src.with_suffix(".webp")

    with open(src, "rb") as fp:
        raw = fp.read()

    webp_data, _ = optimize_image_bytes(raw, max_dim=max_dim, quality=quality)

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as fp:
        fp.write(webp_data)

    if remove_source_if_different and src.resolve() != dst.resolve():
        try:
            src.unlink()
        except Exception as exc:
            logger.warning("Não foi possível excluir arquivo de origem %s: %s", src, exc)

    return dst


def optimize_uploaded_file(
    file_storage,
    target_dir: Union[str, Path],
    filename_prefix: str = "img",
    max_dim: int = DEFAULT_MAX_DIM,
    quality: int = DEFAULT_QUALITY,
) -> str:
    """
    Salva um upload (Werkzeug FileStorage) diretamente como .webp otimizado.
    Retorna o nome do arquivo salvo (ex: 'v20-ultra-9f3a12.webp').
    """
    t_dir = Path(target_dir)
    t_dir.mkdir(parents=True, exist_ok=True)

    orig_name = getattr(file_storage, "filename", "") or "upload"
    stem = Path(orig_name).stem.lower().replace(" ", "_")
    # Sanitiza caracteres
    safe_stem = "".join(c for c in stem if c.isalnum() or c in ("-", "_"))[:32] or filename_prefix
    unique_suffix = uuid.uuid4().hex[:8]
    final_filename = f"{safe_stem}_{unique_suffix}.webp"
    final_path = t_dir / final_filename

    raw_bytes = file_storage.read()
    webp_bytes, _ = optimize_image_bytes(raw_bytes, max_dim=max_dim, quality=quality)

    with open(final_path, "wb") as fp:
        fp.write(webp_bytes)

    return final_filename
