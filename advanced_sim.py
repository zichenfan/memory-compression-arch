import struct
import random

class BDISimulator:
    """Simulates Base-Delta-Immediate (BDI) Compression on 64B cachelines."""
    def compress(self, data: bytes):
        compressed_bits = 0
        for i in range(0, len(data), 64):
            chunk = data[i:i+64]
            if len(chunk) < 64: chunk = chunk.ljust(64, b'\0')
            words = [struct.unpack('<q', chunk[j:j+8])[0] for j in range(0, 64, 8)]
            base = words[0]
            
            max_delta_zero = 0
            for w in words:
                if w == 0: d = 0
                elif -128 <= w <= 127: d = 1
                elif -32768 <= w <= 32767: d = 2
                elif -2147483648 <= w <= 2147483647: d = 4
                else: d = 8
                max_delta_zero = max(max_delta_zero, d)

            max_delta_base0 = 0
            for w in words:
                diff = w - base
                if diff > 0x7FFFFFFFFFFFFFFF: diff -= 0x10000000000000000
                elif diff < -0x8000000000000000: diff += 0x10000000000000000
                
                if diff == 0: d = 0
                elif -128 <= diff <= 127: d = 1
                elif -32768 <= diff <= 32767: d = 2
                elif -2147483648 <= diff <= 2147483647: d = 4
                else: d = 8
                max_delta_base0 = max(max_delta_base0, d)
            
            best_delta = min(max_delta_zero, max_delta_base0)
            
            if best_delta == max_delta_zero:
                chunk_bits = 4 + (8 * best_delta * 8)
            else:
                chunk_bits = 4 + 64 + (8 * best_delta * 8)
            
            if chunk_bits > 512:
                chunk_bits = 512 + 4
            
            compressed_bits += chunk_bits
        return compressed_bits / 8.0

class FPCSimulator:
    """Simulates Frequent Pattern Compression (FPC) on 32-bit words."""
    def compress(self, data: bytes):
        compressed_bits = 0
        words = [struct.unpack('<i', data[i:i+4])[0] for i in range(0, len(data), 4)]
        for w in words:
            compressed_bits += 3
            if w == 0: pass
            elif -128 <= w <= 127: compressed_bits += 8
            elif -32768 <= w <= 32767: compressed_bits += 16
            elif (w & 0xFFFF) == 0: compressed_bits += 16
            else: compressed_bits += 32
        return compressed_bits / 8.0

class LZSimulator:
    """Simulates LZ77 Dictionary Compression."""
    def compress(self, data: bytes, window_size: int, use_fse=True):
        compressed_size = 0
        i = 0
        n = len(data)
        literals = 0
        matches = 0
        while i < n:
            match_len = 0
            start_window = max(0, i - window_size)
            for j in range(start_window, i):
                length = 0
                while i + length < n and data[j + length] == data[i + length] and length < 255:
                    length += 1
                if length > match_len:
                    match_len = length
            
            if match_len >= 3:
                compressed_size += 2 # Offset + Length token
                i += match_len
                matches += 1
            else:
                compressed_size += 1 # Literal byte
                literals += 1
                i += 1
                
        # Metadata overhead
        if use_fse:
            compressed_size += 32 # Heavy FSE table overhead for ZSTD
        else:
            compressed_size += 2  # Light token overhead for simple LZ
            
        return compressed_size

def generate_datasets():
    random.seed(42)
    # 1. Pointer-Heavy (Object arrays)
    base_ptr = 0x00007FFF00000000
    pointers = b"".join(struct.pack('<q', base_ptr + random.randint(0, 100)*8) for _ in range(512))
    
    # 2. Text-Heavy (Strings)
    text = (b"AdaptiveMemComp: Analyzing unified decompression datapath. " * 80)[:4096]
    
    # 3. Sparse Data (Zero initialized buffers)
    sparse = b"\x00" * 3000 + b"".join(struct.pack('<q', random.randint(0, 100)) for _ in range(137))
    
    # 4. Dense Random Data (Encrypted / Media)
    dense = bytes(random.getrandbits(8) for _ in range(4096))
    
    return {"Pointer-Heavy": pointers, "Text-Heavy": text, "Sparse/Zeroes": sparse, "Dense/Random": dense}

def run_tests():
    datasets = generate_datasets()
    bdi = BDISimulator()
    fpc = FPCSimulator()
    lz = LZSimulator()
    
    print(f"{'Dataset':<15} | {'4KB LZ(ZSTD)':<15} | {'256B LZ(Simple)':<15} | {'256B BDI':<15} | {'256B FPC':<15}")
    print("-" * 85)
    
    for name, data in datasets.items():
        # 4KB ZSTD (Window=4096, FSE=True)
        lz_4k = lz.compress(data, 4096, True)
        cr_4k = len(data) / lz_4k if lz_4k > 0 else 99.9
        
        # 256B chunks
        lz_256_total = 0
        bdi_total = 0
        fpc_total = 0
        for i in range(0, len(data), 256):
            chunk = data[i:i+256]
            lz_256_total += lz.compress(chunk, 256, False)
            bdi_total += bdi.compress(chunk)
            fpc_total += fpc.compress(chunk)
            
        cr_lz256 = len(data) / lz_256_total
        cr_bdi = len(data) / bdi_total
        cr_fpc = len(data) / fpc_total
        
        print(f"{name:<15} | {cr_4k:>14.2f}x | {cr_lz256:>14.2f}x | {cr_bdi:>14.2f}x | {cr_fpc:>14.2f}x")

if __name__ == '__main__':
    run_tests()
