"""Tiny PNG writer (RGBA, 8 bit) so textures can be looked at without an image library."""
import zlib, struct

def write_png(path, w, h, rgba):
    raw = b''.join(b'\x00' + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))

def bgra_to_rgba(d):
    b = bytearray(d); b[0::4], b[2::4] = b[2::4], b[0::4]; return b
