"""Image converter — handles PNG, JPG, WEBP, BMP, TIFF, GIF, SVG, HEIC."""

from __future__ import annotations

import time
from pathlib import Path

from app.converters import backends
from app.converters.base import BaseConverter, ConversionEdge
from app.converters.options import ConversionOptions
from app.converters.result import ConversionResult


class ImageConverter(BaseConverter):
    name = "image-converter"
    backend = "pillow+cairosvg"
    category = "image"

    def supported_edges(self) -> list[ConversionEdge]:
        targets = ["png", "jpg", "webp", "bmp", "tiff", "pdf", "gif"]
        sources = ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif"]
        edges: list[ConversionEdge] = []
        for s in sources:
            for t in targets:
                if s != t:
                    edges.append(ConversionEdge(s, t, 5, "pillow", 1.0))
        # SVG → raster / PDF
        for t in ("png", "jpg", "pdf", "webp"):
            edges.append(ConversionEdge("svg", t, 4, "cairosvg", 2.0))
        # HEIC → JPG/PNG
        for t in ("jpg", "png"):
            edges.append(ConversionEdge("heic", t, 4, "pillow-heif", 2.0))
            edges.append(ConversionEdge("heif", t, 4, "pillow-heif", 2.0))
        return edges

    async def convert(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
    ) -> ConversionResult:
        started = time.monotonic()
        target = options.target_format.lower()
        ext = input_path.suffix.lower().lstrip(".")

        try:
            if ext == "svg":
                return await self._from_svg(input_path, output_dir, target, started)
            if ext in {"heic", "heif"}:
                return await self._from_heif(input_path, output_dir, target, started)

            if target == "pdf":
                return await self._to_pdf(input_path, output_dir, options, started)

            fmt = {
                "jpg": "JPEG",
                "jpeg": "JPEG",
                "png": "PNG",
                "webp": "WEBP",
                "bmp": "BMP",
                "tiff": "TIFF",
                "tif": "TIFF",
                "gif": "GIF",
            }.get(target)
            if fmt is None:
                return self._build_result(
                    None, backend="pillow", started=started,
                    error=ValueError(f"Unsupported image target: {target}"),
                )

            output = self.make_output_path(output_dir, target)
            backends.pillow.convert_image(
                input_path, output,
                target_format=fmt,
                quality=_quality_to_int(options.quality),
            )
            return self._build_result(output, backend="pillow", started=started)
        except Exception as exc:
            return self._build_result(None, backend=self.backend, started=started, error=exc)

    async def _to_pdf(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConversionOptions,
        started: float,
    ) -> ConversionResult:
        from PIL import Image

        output = self.make_output_path(output_dir, "pdf")
        with Image.open(input_path) as img:
            if img.mode in {"RGBA", "P", "LA"}:
                img = img.convert("RGB")
            img.save(output, "PDF", resolution=100.0)
        return self._build_result(output, backend="pillow", started=started)

    async def _from_svg(
        self,
        input_path: Path,
        output_dir: Path,
        target: str,
        started: float,
    ) -> ConversionResult:
        try:
            import cairosvg
        except ImportError as exc:
            return self._build_result(
                None, backend="cairosvg", started=started,
                error=RuntimeError(f"cairosvg required: {exc}"),
            )

        output = self.make_output_path(output_dir, target)
        if target == "pdf":
            cairosvg.svg2pdf(url=str(input_path), write_to=str(output))
        elif target == "png":
            cairosvg.svg2png(url=str(input_path), write_to=str(output))
        elif target in {"jpg", "jpeg"}:
            import io
            png = cairosvg.svg2png(url=str(input_path))
            from PIL import Image
            Image.open(io.BytesIO(png)).convert("RGB").save(output, "JPEG")
        elif target == "webp":
            import io
            png = cairosvg.svg2png(url=str(input_path))
            from PIL import Image
            Image.open(io.BytesIO(png)).save(output, "WEBP")
        else:
            return self._build_result(
                None, backend="cairosvg", started=started,
                error=ValueError(f"Unsupported svg→{target}"),
            )
        return self._build_result(output, backend="cairosvg", started=started)

    async def _from_heif(
        self,
        input_path: Path,
        output_dir: Path,
        target: str,
        started: float,
    ) -> ConversionResult:
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError as exc:
            return self._build_result(
                None, backend="pillow-heif", started=started,
                error=RuntimeError(f"pillow-heif required: {exc}"),
            )
        from PIL import Image

        with Image.open(input_path) as img:
            if target in {"jpg", "jpeg"}:
                img = img.convert("RGB")
                output = self.make_output_path(output_dir, "jpg")
                img.save(output, "JPEG", quality=90)
            elif target == "png":
                output = self.make_output_path(output_dir, "png")
                img.save(output, "PNG")
            else:
                return self._build_result(
                    None, backend="pillow-heif", started=started,
                    error=ValueError(f"Unsupported heic→{target}"),
                )
        return self._build_result(output, backend="pillow-heif", started=started)


def _quality_to_int(q) -> int:
    return {
        "low": 60,
        "medium": 80,
        "high": 92,
        "lossless": 100,
    }.get(q.value if hasattr(q, "value") else q, 90)
