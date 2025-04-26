import base64
import io
from PIL import Image
import torch
from typing import Union

def load_image_from_base64(base64_string: str) -> Image.Image:
    """Convert base64 string to PIL Image"""
    try:
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data))
        return image
    except Exception as e:
        raise ValueError(f"Failed to load image from base64: {str(e)}")

def load_video_from_path(video_path: str) -> str:
    """Return video path for model processing"""
    # The model handles video paths directly
    return video_path

def process_image(image: Union[str, Image.Image]) -> Image.Image:
    """Process image input in various formats"""
    if isinstance(image, str):
        if image.startswith('data:image'):
            # Handle data URL
            base64_data = image.split(',')[1]
            return load_image_from_base64(base64_data)
        elif image.startswith('http'):
            # Handle URL (you might want to add URL image loading)
            raise NotImplementedError("URL image loading not implemented")
        else:
            # Assume it's base64
            return load_image_from_base64(image)
    elif isinstance(image, Image.Image):
        return image
    else:
        raise ValueError("Unsupported image format")