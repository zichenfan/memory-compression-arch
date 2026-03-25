import struct
import random

class FPC_Simulator:
    """Simulates Frequent Pattern Compression (FPC) on 256B chunks."""
    def compress(self, data: bytes):
        assert len(data) == 256
        words = [struct.unpack('<I', data[i:i+4])[0] for i in range(0, 256, 4)]
        compressed_bits = 0
        for w in words:
            compressed_bits += 3  # 3-bit prefix overhead
            if w == 0:
                pass  # 000: Zero run (0 extra bits)
            elif 0 <= w <= 0xFF:
                compressed_bits += 8  # 001: 8-bit sign extended
            elif 0 <= w <= 0xFFFF:
                compressed_bits += 16 # 010: 16-bit sign extended
            elif (w & 0xFFFF) == 0:
                compressed_bits += 16 # 011: Half-word zero padded
            else:
                compressed_bits += 32 # 111: Uncompressed
        return compressed_bits / 8.0

class LZ_Simulator:
    """Simulates LZ77 Dictionary Compression (Core of LZ4/ZSTD)."""
    def compress(self, data: bytes, window_size: int):
        compressed_size = 0
        i = 0
        n = len(data)
        while i < n:
            match_len = 0
            start_window = max(0, i - window_size)
            # Brute-force longest match search
            for j in range(start_window, i):
                length = 0
                while i + length < n and data[j + length] == data[i + length] and length < 255:
                    length += 1
                if length > match_len:
                    match_len = length
            
            if match_len >= 3:
                compressed_size += 2 # (offset, length) encoding approx 2 bytes
                i += match_len
            else:
                compressed_size += 1 # literal
                i += 1
        return compressed_size * 1.05 # Add 5% overhead for FSE/Huffman entropy metadata

def generate_synthetic_data():
    random.seed(42)
    # 1. Pointer-heavy (Array of pointers, high locality, upper 16-bits identical)
    base_ptr = 0x7FFF0000
    pointers = b"".join(struct.pack('<I', base_ptr + random.randint(0, 20)*8) for _ in range(1024))
    
    # 2. Text-Heavy (Repeated patterns, good for LZ)
    text_base = b"AdaptiveMemComp: Analyzing unified decompression datapath. " * 80
    text = text_base[:4096]
    
    return {"Pointer-Heavy (Heap/Arrays)": pointers, "Text-Heavy (Pages/Strings)": text}

def run_simulation():
    datasets = generate_synthetic_data()
    fpc = FPC_Simulator()
    lz = LZ_Simulator()
    
    print("=== Step 2.1: Compression Ratio Simulation ===")
    for name, data in datasets.items():
        print(f"\nDataset: {name} (Size: 4KB)")
        
        # 1. 4KB Full LZ (ZSTD-like)
        lz_4k_size = lz.compress(data, window_size=4096)
        cr_4k = 4096 / lz_4k_size
        print(f"  [Cold] 4KB Full LZ (ZSTD-like)  CR: {cr_4k:.2f}x")
        
        # 2. 256B Chunked Simulation
        fpc_total_size = 0
        lz_256_total_size = 0
        for i in range(0, 4096, 256):
            chunk = data[i:i+256]
            fpc_total_size += fpc.compress(chunk)
            lz_256_total_size += lz.compress(chunk, window_size=256)
            
        cr_fpc = 4096 / fpc_total_size
        cr_lz256 = 4096 / lz_256_total_size
        
        print(f"  [Hot ] 256B FPC (Pattern)       CR: {cr_fpc:.2f}x")
        print(f"  [Hot ] 256B Simplified LZ       CR: {cr_lz256:.2f}x")

if __name__ == '__main__':
    run_simulation()
