import struct
import random
import zstandard as zstd
import lz4.block
import requests
import os
import gzip

# --- DATASET DOWNLOADER ---
def download_enwik8():
    if not os.path.exists('enwik8.zip'):
        print("Downloading enwik8 (100MB wikipedia slice)...")
        r = requests.get('http://mattmahoney.net/dc/enwik8.zip')
        with open('enwik8.zip', 'wb') as f:
            f.write(r.content)
    import zipfile
    with zipfile.ZipFile('enwik8.zip', 'r') as z:
        return z.read('enwik8')[:10*1024*1024] # Use first 10MB for speed

def generate_spec_synthetic():
    """Generates synthetic data that mimics a pointer-chasing SPEC CPU benchmark."""
    random.seed(42)
    data = bytearray()
    base_addr = 0x00007FFF00000000
    for _ in range(10*1024*1024 // 8): # 10MB
        data.extend(struct.pack('<q', base_addr + random.randint(0, 1024)*64))
    return bytes(data)

def generate_db_synthetic():
    """Generates synthetic database rows (mixed integers, shorts, short strings)."""
    random.seed(42)
    data = bytearray()
    for i in range(10*1024*1024 // 64): # 10MB of 64B rows
        data.extend(struct.pack('<I', i)) # ID
        data.extend(struct.pack('<f', random.uniform(10.0, 1000.0))) # Balance
        status = b"ACTIVE" if random.random() > 0.1 else b"CLOSED"
        data.extend(status.ljust(8, b'\0'))
        data.extend(b"".join(struct.pack('<I', random.randint(0, 100)) for _ in range(12))) # Padding/metrics
    return bytes(data)

# --- ALGORITHM WRAPPERS ---
class ZSTDWrapper:
    def __init__(self, level=1):
        self.cctx = zstd.ZstdCompressor(level=level)
    def compress_chunk(self, chunk):
        return len(self.cctx.compress(chunk))

class LZ4Wrapper:
    def compress_chunk(self, chunk):
        try:
            return len(lz4.block.compress(chunk, mode='fast'))
        except:
            return len(chunk) # Uncompressible fallback

class FPCWrapper:
    """Simulates FPC strictly based on the ISCA'04 paper (3-bit prefix + 32-bit words)."""
    def compress_chunk(self, chunk):
        compressed_bits = 0
        words = [struct.unpack('<i', chunk[i:i+4])[0] for i in range(0, len(chunk), 4)]
        for w in words:
            compressed_bits += 3
            if w == 0: pass
            elif -128 <= w <= 127: compressed_bits += 8
            elif -32768 <= w <= 32767: compressed_bits += 16
            elif (w & 0xFFFF) == 0: compressed_bits += 16
            else: compressed_bits += 32
        return compressed_bits / 8.0

class BDIWrapper:
    """Simulates Base-Delta-Immediate (PACT'12)."""
    def compress_chunk(self, chunk):
        if len(chunk) != 64: return len(chunk) # BDI operates strictly on cachelines
        words = [struct.unpack('<q', chunk[j:j+8])[0] for j in range(0, 64, 8)]
        base = words[0]
        max_d_zero = 0
        for w in words:
            if w == 0: d = 0
            elif -128 <= w <= 127: d = 1
            elif -32768 <= w <= 32767: d = 2
            elif -2147483648 <= w <= 2147483647: d = 4
            else: d = 8
            max_d_zero = max(max_d_zero, d)
            
        max_d_base = 0
        for w in words:
            diff = w - base
            if diff > 0x7FFFFFFFFFFFFFFF: diff -= 0x10000000000000000
            elif diff < -0x8000000000000000: diff += 0x10000000000000000
            if diff == 0: d = 0
            elif -128 <= diff <= 127: d = 1
            elif -32768 <= diff <= 32767: d = 2
            elif -2147483648 <= diff <= 2147483647: d = 4
            else: d = 8
            max_d_base = max(max_d_base, d)
            
        best_delta = min(max_d_zero, max_d_base)
        chunk_bits = 4 + (8 * best_delta * 8) if best_delta == max_d_zero else 4 + 64 + (8 * best_delta * 8)
        return min(chunk_bits / 8.0, 64)

# --- RUNNER ---
def run_evaluation():
    print("Loading datasets (10MB each)...")
    datasets = {
        "enwik8 (Text/Web)": download_enwik8(),
        "SPEC_PTR (Pointer Chasing)": generate_spec_synthetic(),
        "DB_ROWS (Mixed Structs)": generate_db_synthetic()
    }
    
    algos = {
        "ZSTD_4KB (Macro)": (ZSTDWrapper(), 4096),
        "ZSTD_256B (Micro)": (ZSTDWrapper(), 256),
        "LZ4_4KB (Macro)": (LZ4Wrapper(), 4096),
        "LZ4_256B (Micro)": (LZ4Wrapper(), 256),
        "FPC_256B (Micro)": (FPCWrapper(), 256),
        "BDI_64B (Micro)": (BDIWrapper(), 64)
    }
    
    print(f"\n{'Dataset':<25} | {'Algorithm':<18} | {'Chunk Size':<10} | {'Comp. Ratio':<10}")
    print("-" * 70)
    
    for ds_name, data in datasets.items():
        # Trim data slightly to be a clean multiple of 4096
        data = data[:(len(data)//4096)*4096] 
        original_size = len(data)
        
        for alg_name, (wrapper, chunk_size) in algos.items():
            compressed_size = 0
            # Chunking loop
            for i in range(0, original_size, chunk_size):
                chunk = data[i:i+chunk_size]
                compressed_size += wrapper.compress_chunk(chunk)
                
            cr = original_size / compressed_size
            print(f"{ds_name:<25} | {alg_name:<18} | {chunk_size:<10} | {cr:>9.2f}x")

if __name__ == '__main__':
    run_evaluation()
