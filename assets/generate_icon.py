"""Gerador de ícones PNG e ICO em Python puro (sem dependências externas)."""

import math
import os
import struct
import zlib


def create_png_rgba(width: int, height: int, pixels: bytes) -> bytes:
    """Cria um arquivo PNG válido com canal alfa (RGBA)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xffffffff
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))

    # Adiciona byte de filtro 0 no início de cada scanline
    scanlines = bytearray()
    row_bytes = width * 4
    for y in range(height):
        scanlines.append(0)  # Filtro: None
        scanlines.extend(pixels[y * row_bytes : (y + 1) * row_bytes])

    idat = chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
    iend = chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


def create_ico(png_data: bytes, width: int, height: int) -> bytes:
    """Empacota dados PNG em um container ICO padrão do Windows."""
    # Header: 2 bytes reserva (0), 2 bytes tipo (1=ICO), 2 bytes num_imagens (1)
    header = struct.pack("<HHH", 0, 1, 1)
    # Directory entry (16 bytes):
    # bWidth, bHeight, bColorCount, bReserved, wPlanes, wBitCount, dwBytesInRes, dwImageOffset
    entry = struct.pack(
        "<BBBBHHII",
        width if width < 256 else 0,
        height if height < 256 else 0,
        0,  # cores
        0,  # reservado
        1,  # planos de cor
        32, # bits por pixel
        len(png_data),
        6 + 16, # offset dos dados
    )
    return header + entry + png_data


def generate_f1_icon(size: int = 64) -> bytes:
    """Gera a imagem de um carro de corrida F1 estilizado sobre um badge circular escuro."""
    pixels = bytearray(size * size * 4)
    cx, cy = size / 2.0, size / 2.0
    r_outer = size * 0.46
    r_inner = size * 0.43

    for y in range(size):
        for x in range(size):
            idx = (y * size + x) * 4
            dx = x - cx
            dy = y - cy
            dist = math.sqrt(dx * dx + dy * dy)

            # Fora do círculo -> Transparente
            if dist > r_outer + 1.0:
                pixels[idx : idx + 4] = b"\x00\x00\x00\x00"
                continue

            # Borda Vermelha F1 (#e10600)
            if dist > r_inner:
                alpha = max(0.0, min(1.0, r_outer + 1.0 - dist))
                pixels[idx : idx + 4] = bytes([225, 6, 0, int(255 * alpha)])
                continue

            # Fundo interno: Preto asfalto degradê (#171717)
            grad = int(24 + (y / size) * 12)
            pixels[idx : idx + 4] = bytes([grad, grad, grad, 255])

            # Desenho do Carro F1 (Perfil Esportivo Vermelho)
            # Normaliza coordenadas dentro do círculo [-1, 1]
            nx = (x - cx) / (size * 0.4)
            ny = (y - cy) / (size * 0.4)

            # 1. Bico / Chassi Principal F1
            # Bico vai de x = -0.7 até x = 0.8, y em torno de 0.0 a 0.25
            if -0.7 <= nx <= 0.8 and 0.05 <= ny <= 0.28:
                # Perfil em cunha
                wedge_top = 0.25 - (nx + 0.7) * 0.15
                if ny >= wedge_top:
                    pixels[idx : idx + 4] = bytes([230, 20, 20, 255]) # Vermelho F1

            # 2. Cobertura do Motor / Shark Fin
            if -0.55 <= nx <= -0.15 and -0.25 <= ny <= 0.12:
                if ny >= -0.25 + (nx + 0.55) * 0.8:
                    pixels[idx : idx + 4] = bytes([185, 10, 10, 255])

            # 3. Cockpit / Capacete Amarelo
            cdx = nx - (-0.1)
            cdy = ny - (-0.05)
            if math.sqrt(cdx * cdx + cdy * cdy) < 0.12:
                pixels[idx : idx + 4] = bytes([250, 204, 21, 255]) # Amarelo Ayrton Senna

            # 4. Asa Traseira
            if -0.85 <= nx <= -0.65 and -0.28 <= ny <= 0.05:
                if -0.28 <= ny <= -0.18 or -0.85 <= nx <= -0.78:
                    pixels[idx : idx + 4] = bytes([255, 255, 255, 255]) # Branco

            # 5. Asa Dianteira
            if 0.70 <= nx <= 0.92 and 0.15 <= ny <= 0.28:
                pixels[idx : idx + 4] = bytes([255, 255, 255, 255])

            # 6. Pneu Traseiro (Roda Grande)
            tdx = nx - (-0.48)
            tdy = ny - (0.22)
            tdist = math.sqrt(tdx * tdx + tdy * tdy)
            if tdist < 0.24:
                if tdist > 0.16:
                    pixels[idx : idx + 4] = bytes([15, 15, 15, 255]) # Pneu preto
                elif tdist > 0.13:
                    pixels[idx : idx + 4] = bytes([225, 29, 72, 255]) # Faixa Pirelli Soft (Vermelha)
                elif tdist > 0.06:
                    pixels[idx : idx + 4] = bytes([50, 50, 50, 255]) # Roda
                else:
                    pixels[idx : idx + 4] = bytes([255, 255, 255, 255]) # Miolo

            # 7. Pneu Dianteiro
            fdx = nx - (0.48)
            fdy = ny - (0.22)
            fdist = math.sqrt(fdx * fdx + fdy * fdy)
            if fdist < 0.22:
                if fdist > 0.15:
                    pixels[idx : idx + 4] = bytes([15, 15, 15, 255])
                elif fdist > 0.12:
                    pixels[idx : idx + 4] = bytes([225, 29, 72, 255])
                elif fdist > 0.05:
                    pixels[idx : idx + 4] = bytes([50, 50, 50, 255])
                else:
                    pixels[idx : idx + 4] = bytes([255, 255, 255, 255])

    return create_png_rgba(size, size, bytes(pixels))


def main():
    assets_dir = os.path.dirname(os.path.abspath(__file__))
    png_data = generate_f1_icon(size=64)
    png_path = os.path.join(assets_dir, "icon.png")
    with open(png_path, "wb") as f:
        f.write(png_data)

    ico_data = create_ico(png_data, 64, 64)
    ico_path = os.path.join(assets_dir, "icon.ico")
    with open(ico_path, "wb") as f:
        f.write(ico_data)

    print(f"✅ Ícones gerados com sucesso!")
    print(f"📁 PNG: {png_path} ({len(png_data)} bytes)")
    print(f"📁 ICO: {ico_path} ({len(ico_data)} bytes)")


if __name__ == "__main__":
    main()
