import struct
import math
import sys
import os
from PIL import Image

# BLP Encodings
BLP_JPEG = 0
BLP_PALETTE = 1
BLP_DXT = 2
BLP_ARGB8888 = 3

# BLP Formats
BLP_DXT1 = 0
BLP_DXT3 = 1
BLP_ARGB8888 = 2
BLP_ARGB1555 = 3
BLP_ARGB4444 = 4
BLP_RGB565 = 5
BLP_A8 = 6
BLP_DXT5 = 7
BLP_BC5 = 11

class BlpConverter:
    BLP0Magic = 0x30504c42
    BLP1Magic = 0x31504c42
    BLP2Magic = 0x32504c42

    def __init__(self, filename):
        self.filename = filename
        self.file = open(filename, "rb")
        self.color_encoding = 0
        self.alpha_size = 0
        self.preferred_format = 0
        self.has_mips = 0
        self.width = 0
        self.height = 0
        self.mip_offsets = [0] * 16
        self.mip_sizes = [0] * 16
        self.palette_bgra = []
        self.jpeg_header = b""
        self._parse_header()

    def _parse_header(self):
        magic = struct.unpack("<I", self.file.read(4))[0]
        
        if magic in (self.BLP0Magic, self.BLP1Magic):
            self.color_encoding = struct.unpack("<I", self.file.read(4))[0]
            self.alpha_size = struct.unpack("<I", self.file.read(4))[0]
            self.width = struct.unpack("<I", self.file.read(4))[0]
            self.height = struct.unpack("<I", self.file.read(4))[0]
            self.preferred_format = struct.unpack("<I", self.file.read(4))[0]
            self.has_mips = struct.unpack("<B", self.file.read(1))[0]
        elif magic == self.BLP2Magic:
            version = struct.unpack("<I", self.file.read(4))[0]
            if version != 1:
                raise ValueError(f"Invalid BLP-Type! Should be 1 but {version} found")
            self.color_encoding = struct.unpack("<B", self.file.read(1))[0]
            self.alpha_size = struct.unpack("<B", self.file.read(1))[0]
            self.preferred_format = struct.unpack("<B", self.file.read(1))[0]
            self.has_mips = struct.unpack("<B", self.file.read(1))[0]
            self.width = struct.unpack("<I", self.file.read(4))[0]
            self.height = struct.unpack("<I", self.file.read(4))[0]
        else:
            raise ValueError("Invalid BLP Format")

        for i in range(16):
            self.mip_offsets[i] = struct.unpack("<I", self.file.read(4))[0]
        for i in range(16):
            self.mip_sizes[i] = struct.unpack("<I", self.file.read(4))[0]

        if self.color_encoding == BLP_PALETTE:
            for i in range(256):
                color = struct.unpack("<I", self.file.read(4))[0]
                self.palette_bgra.append((
                    (color >> 16) & 0xFF, # R
                    (color >> 8) & 0xFF,  # G
                    (color >> 0) & 0xFF,  # B
                    (color >> 24) & 0xFF  # A
                ))
        elif self.color_encoding == BLP_JPEG:
            header_size = struct.unpack("<I", self.file.read(4))[0]
            self.jpeg_header = self.file.read(header_size)

    def get_mip_count(self):
        count = 0
        while count < 16 and self.mip_offsets[count] != 0:
            count += 1
        return count

    def get_picture_data(self, level):
        if level >= self.get_mip_count():
            level = self.get_mip_count() - 1
        if level < 0:
            level = 0
        if self.mip_offsets[level] != 0:
            return self.file.read(self.mip_sizes[level])
        return None

    def decompress_dxt(self, width, height, data):
        flags = 0
        if self.alpha_size > 1:
            if self.preferred_format == BLP_DXT5:
                flags |= 4
            else:
                flags |= 2
        else:
            flags |= 1

        rgba = bytearray(width * height * 4)
        source_block_pos = 0
        bytes_per_block = 8 if (flags & 1) else 16
        
        for y in range(0, height, 4):
            for x in range(0, width, 4):
                if source_block_pos >= len(data): break
                block = data[source_block_pos : source_block_pos + bytes_per_block]
                target_rgba = bytearray(4 * 16)
                
                color_block_idx = source_block_pos // bytes_per_block
                if (flags & (4 | 2)) != 0:
                    color_block_idx += 8
                
                self._decompress_color(target_rgba, block, color_block_idx, (flags & 1) != 0)
                
                if (flags & 2) != 0: # DXT3
                    self._decompress_alpha_dxt3(target_rgba, block, color_block_idx)
                elif (flags & 4) != 0: # DXT5
                    self._decompress_alpha_dxt5(target_rgba, block, color_block_idx)

                for py in range(4):
                    for px in range(4):
                        sx, sy = x + px, y + py
                        if sx < width and sy < height:
                            idx = 4 * (width * sy + sx)
                            rgba[idx : idx + 4] = target_rgba[py * 16 + px * 4 : py * 16 + px * 4 + 4]
                
                source_block_pos += bytes_per_block
        return bytes(rgba)

    def _decompress_color(self, target_rgba, block, block_index, is_dxt1):
        codes = [0] * 16
        a_val = self._unpack_565(block, block_index, 0, codes, 0)
        b_val = self._unpack_565(block, block_index, 2, codes, 4)
        
        for i in range(3):
            c = codes[i]
            d = codes[4 + i]
            if is_dxt1 and a_val <= b_val:
                codes[8 + i] = (c + d) // 2
                codes[12 + i] = 0
            else:
                codes[8 + i] = (2 * c + d) // 3
                codes[12 + i] = (c + 2 * d) // 3
        
        codes[8 + 3] = 255
        codes[12 + 3] = (byte_or_0(0x00) if (is_dxt1 and a_val <= b_val) else (byte_or_0(0xFF)))

        indices = [0] * 16
        for i in range(4):
            packed = block[block_index + 4 + i]
            indices[0 + i * 4] = packed & 0x3
            indices[1 + i * 4] = (packed >> 2) & 0x3
            indices[2 + i * 4] = (packed >> 4) & 0x3
            indices[3 + i * 4] = (packed >> 6) & 0x3
            
        for i in range(16):
            offset = 4 * indices[i]
            target_rgba[4 * i] = codes[offset]
            target_rgba[4 * i + 1] = codes[offset + 1]
            target_rgba[4 * i + 2] = codes[offset + 2]
            target_rgba[4 * i + 3] = codes[offset + 3]

    def _unpack_565(self, block, block_index, packed_offset, colour, colour_offset):
        value = block[block_index + packed_offset] | (block[block_index + 1 + packed_offset] << 8)
        red = (value >> 11) & 0x1F
        green = (value >> 5) & 0x3F
        blue = value & 0x1F
        
        colour[colour_offset] = ((red << 3) | (red >> 2))
        colour[colour_offset + 1] = ((green << 2) | (green >> 4))
        colour[colour_offset + 2] = ((blue << 3) | (blue >> 2))
        colour[colour_offset + 3] = 255
        return value

    def _decompress_alpha_dxt3(self, target_rgba, block, block_index):
        for i in range(8):
            quant = block[block_index + i]
            lo = quant & 0x0F
            hi = (quant & 0xF0)
            target_rgba[8 * i + 3] = (lo | (lo << 4))
            target_rgba[8 * i + 7] = (hi | (hi >> 4))

    def _decompress_alpha_dxt5(self, target_rgba, block, block_index):
        alpha0 = block[block_index]
        alpha1 = block[block_index + 1]
        
        codes = [0] * 8
        if alpha0 <= alpha1:
            for i in range(1, 5):
                codes[1 + i] = ((5 - i) * alpha0 + i * alpha1) // 5
            codes[6] = 0
            codes[7] = 255
        else:
            for i in range(1, 7):
                codes[i + 1] = ((7 - i) * alpha0 + i * alpha1) // 7
        
        indices = [0] * 16
        block_src_pos = 2
        indices_pos = 0
        for i in range(2):
            value = 0
            for j in range(3):
                value |= (block[block_index + block_src_pos] << (8 * j))
                block_src_pos += 1
            for j in range(8):
                indices[indices_pos] = (value >> (3 * j)) & 0x07
                indices_pos += 1
        
        for i in range(16):
            target_rgba[4 * i + 3] = codes[indices[i]]

    def convert(self, output_path):
        mipmap_level = 0
        w = self.width // (2 ** mipmap_level)
        h = self.height // (2 ** mipmap_level)
        
        data = self.get_picture_data(mipmap_level)
        if not data:
            print("Error: No data found.")
            return

        if self.color_encoding == BLP_PALETTE:
            pic = bytearray(w * h * 4)
            for i in range(w * h):
                pixel = self.palette_bgra[data[i]]
                pic[i * 4] = pixel[0]
                pic[i * 4 + 1] = pixel[1]
                pic[i * 4 + 2] = pixel[2]
                pic[i * 4 + 3] = pixel[3]
            self._save_as_png(pic, w, h, output_path)
        elif self.color_encoding == BLP_DXT:
            rgba = self.decompress_dxt(w, h, data)
            self._save_as_png(rgba, w, h, output_path)
        elif self.color_encoding == BLP_ARGB8888:
            self._save_as_png(data, w, h, output_path)
        else:
            print(f"Unsupported encoding: {self.color_encoding}")

    def _save_as_png(self, pic, w, h, path):
        try:
            img = Image.frombytes("RGBA", (w, h), bytes(pic))
            img.save(path)
            print(f"Saved to {path}")
        except ImportError:
            # Fallback to PPM only if Pillow is actually missing
            ppm_path = path.replace(".png", ".ppm")
            with open(ppm_path, "wb") as f:
                f.write(f"P6\n{w} {h}\n255\n".encode('ascii'))
                f.write(pic[:w * h * 3])
            print(f"Pillow not found. Saved fallback {ppm_path}")

def byte_or_0(val):
    return val & 0xFF

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 blp2png.py <input_file.blp>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = os.path.splitext(input_file)[0] + ".png"
    
    try:
        converter = BlpConverter(input_file)
        converter.convert(output_file)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
