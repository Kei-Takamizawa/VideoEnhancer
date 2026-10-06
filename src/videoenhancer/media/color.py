"""BT.601/709 conversion. Chroma stays on its original 2x2 sampling grid."""

import torch


def _coefficients(matrix: str) -> tuple[float, float]:
    if matrix == "bt709":
        return 0.2126, 0.0722
    if matrix in {"bt601", "smpte170m", "bt470bg"}:
        return 0.299, 0.114
    raise ValueError(f"Unsupported color matrix: {matrix}")


def nv12_to_rgb(
    frame: torch.Tensor,
    width: int,
    height: int,
    matrix: str = "bt709",
    full_range: bool = False,
    bit_depth: int = 8,
) -> torch.Tensor:
    packed = frame.reshape(-1, frame.shape[-1])
    values = packed[: height * 3 // 2, :width].to(torch.float32)
    factor = 1 << (bit_depth - 8)
    if bit_depth > 8:
        values = values / (1 << (16 - bit_depth))
    y = values[:height]
    uv = values[height:].reshape(height // 2, width // 2, 2)
    u = uv[..., 0].repeat_interleave(2, 0).repeat_interleave(2, 1)
    v = uv[..., 1].repeat_interleave(2, 0).repeat_interleave(2, 1)
    if full_range:
        y = y / ((1 << bit_depth) - 1)
        u = (u - 128 * factor) / ((1 << bit_depth) - 1)
        v = (v - 128 * factor) / ((1 << bit_depth) - 1)
    else:
        y = (y - 16 * factor) / (219 * factor)
        u = (u - 128 * factor) / (224 * factor)
        v = (v - 128 * factor) / (224 * factor)
    kr, kb = _coefficients(matrix)
    kg = 1 - kr - kb
    r = y + 2 * (1 - kr) * v
    b = y + 2 * (1 - kb) * u
    g = (y - kr * r - kb * b) / kg
    return torch.stack((r, g, b)).to(torch.float16)


def rgb_to_nv12(rgb: torch.Tensor, matrix: str = "bt709", bit_depth: int = 8) -> torch.Tensor:
    r, g, b = rgb.to(torch.float32).unbind(0)
    height, width = r.shape
    if height % 2 or width % 2:
        raise ValueError("4:2:0 encoding requires even frame dimensions.")
    kr, kb = _coefficients(matrix)
    y = kr * r + (1 - kr - kb) * g + kb * b
    u = (b - y) / (2 * (1 - kb))
    v = (r - y) / (2 * (1 - kr))
    u = u.reshape(height // 2, 2, width // 2, 2).mean((1, 3))
    v = v.reshape(height // 2, 2, width // 2, 2).mean((1, 3))
    factor = 1 << (bit_depth - 8)
    luma = (16 * factor + 219 * factor * y).round().clamp(0, (1 << bit_depth) - 1)
    chroma = (
        torch.stack((128 * factor + 224 * factor * u, 128 * factor + 224 * factor * v), -1)
        .round()
        .clamp(0, (1 << bit_depth) - 1)
        .reshape(height // 2, width)
    )
    packed = torch.cat((luma, chroma))
    if bit_depth > 8:
        return (packed * (1 << (16 - bit_depth))).to(torch.uint16).contiguous()
    return packed.to(torch.uint8).contiguous()
