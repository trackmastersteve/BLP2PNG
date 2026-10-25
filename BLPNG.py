import struct
import sys
import os
from PIL import Image

BLP2_MAGIC = 0x32504c42
BLP_PALETTE = 1

class BlpExtractor:
    """Handles extracting BLP to PNG"""
    def __init__(self, filename):
        self.filename = filename
        self.file = open(filename, "rb")
        self.mip_offsets, self.mip_sizes = [0]*16, [0]*16
        self.palette_bgra = []
        self._parse_header()

    def _parse_header(self):
        magic, version, self.enc, self.alpha_sz, self.pref, self.mips, self.w, self.h = struct.unpack("<IIBBBBII", self.file.read(20))
        for i in range(16): self.mip_offsets[i] = struct.unpack("<I", self.file.read(4))[0]
        for i in range(16): self.mip_sizes[i] = struct.unpack("<I", self.file.read(4))[0]

        if self.enc == BLP_PALETTE:
            for i in range(256):
                color = struct.unpack("<I", self.file.read(4))[0]
                self.palette_bgra.append(((color >> 16) & 0xFF, (color >> 8) & 0xFF, (color >> 0) & 0xFF, (color >> 24) & 0xFF))

    def extract_to_png(self, output_path):
        if self.mip_offsets[0] == 0: return
        self.file.seek(self.mip_offsets[0])
        data = self.file.read(self.mip_sizes[0])

        if self.enc == BLP_PALETTE:
            pic = bytearray(self.w * self.h * 4)
            # Fetch color indices
            for i in range(self.w * self.h):
                pic[i*4 : i*4+3] = self.palette_bgra[data[i]][0:3]
                
            # Fetch alpha channel (stored sequentially AFTER colors in PAL_A8)
            if self.alpha_sz == 8:
                alpha_offset = self.w * self.h
                for i in range(self.w * self.h):
                    pic[i*4 + 3] = data[alpha_offset + i]
            else:
                for i in range(self.w * self.h): pic[i*4 + 3] = 255
                    
            img = Image.frombytes("RGBA", (self.w, self.h), bytes(pic))
            img.save(output_path)
            print(f"Extracted to: {output_path}")

def png_to_blp_pal_a8(input_path, output_path):
    """Handles packaging HD PNG to PAL_A8 BLP properly sequentially"""
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size

    rgb_img = img.convert("RGB")
    alpha_img = img.split()[3]

    # 1. Generate 256-Color Master Palette
    q_img = rgb_img.quantize(colors=256)
    raw_palette = q_img.getpalette() or []
    raw_palette += [0] * (768 - len(raw_palette))
    
    bgra_palette = bytearray(1024)
    for i in range(256):
        bgra_palette[i*4] = raw_palette[i*3 + 2]     # B
        bgra_palette[i*4 + 1] = raw_palette[i*3 + 1] # G
        bgra_palette[i*4 + 2] = raw_palette[i*3]     # R
        bgra_palette[i*4 + 3] = 255                  # A

    mips_data = []
    current_w, current_h = width, height
    current_rgb, current_alpha = rgb_img, alpha_img
    
    print("Quantizing colors and packing as sequential PAL_A8...")
    while current_w >= 1 and current_h >= 1:
        if current_w == width and current_h == height:
            mip_q = q_img
        else:
            mip_q = current_rgb.quantize(colors=256, palette=q_img)
            
        # SEQUENTIAL FIX: Write ALL color indices, then ALL alpha bytes
        indices = bytearray(mip_q.getdata())
        alphas = bytearray(current_alpha.getdata())
        mips_data.append(bytes(indices) + bytes(alphas))
        
        if current_w == 1 and current_h == 1: break
        
        current_w = max(1, current_w // 2)
        current_h = max(1, current_h // 2)
        current_rgb = rgb_img.resize((current_w, current_h), Image.Resampling.LANCZOS)
        current_alpha = alpha_img.resize((current_w, current_h), Image.Resampling.LANCZOS)

    with open(output_path, "wb") as f:
        # Header: Magic, Version, Encoding 1 (Palette), Alpha 8, Format 8, HasMips 1
        f.write(struct.pack("<IIBBBBII", BLP2_MAGIC, 1, BLP_PALETTE, 8, 8, 1, width, height))
        
        # 20 header + 128 tables + 1024 palette = 1172 start offset
        header_size = 20 + 128 + 1024 
        offsets, sizes = [0] * 16, [0] * 16
        current_offset = header_size
        
        for i in range(len(mips_data)):
            size = len(mips_data[i])
            offsets[i], sizes[i] = current_offset, size
            current_offset += size
            
        for off in offsets: f.write(struct.pack("<I", off))
        for size in sizes: f.write(struct.pack("<I", size))
        
        f.write(bgra_palette)
        for data in mips_data: f.write(data)
        
    print(f"Packaged to: {output_path} (Flawless PAL_A8)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python BLPNG.py <input_file>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    ext = os.path.splitext(input_file)[1].lower()
    
    if ext == ".blp":
        out_file = os.path.splitext(input_file)[0] + ".png"
        extractor = BlpExtractor(input_file)
        extractor.extract_to_png(out_file)
    elif ext == ".png":
        out_file = os.path.splitext(input_file)[0] + ".blp"
        png_to_blp_pal_a8(input_file, out_file)
