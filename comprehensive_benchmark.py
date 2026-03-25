import struct
import random
import zstandard as zstd
import lz4.block
import requests
import os
import numpy as np

# --- REAL DATASET DOWNLOADERS ---
def download_enwik8():
    """Text/Web: Wikipedia corpus (standard compression benchmark)"""
    if not os.path.exists('enwik8.zip'):
        print("Downloading enwik8 (100MB wikipedia)...")
        r = requests.get('http://mattmahoney.net/dc/enwik8.zip', timeout=60)
        with open('enwik8.zip', 'wb') as f:
            f.write(r.content)
    import zipfile
    with zipfile.ZipFile('enwik8.zip', 'r') as z:
        return z.read('enwik8')[:20*1024*1024]

def download_silesia():
    """Mixed: Silesia corpus (documents, images, executables)"""
    if not os.path.exists('silesia.zip'):
        print("Downloading Silesia corpus (200MB mixed data)...")
        r = requests.get('http://sun.aei.polsl.pl/~sdeor/corpus/silesia.zip', timeout=120)
        with open('silesia.zip', 'wb') as f:
            f.write(r.content)
    import zipfile
    with zipfile.ZipFile('silesia.zip', 'r') as z:
        # Combine multiple files
        data = b""
        for name in ['dickens', 'mozilla', 'mr', 'nci']:
            try:
                data += z.read(name)[:5*1024*1024]
            except:
                pass
        return data[:20*1024*1024]

# --- SYNTHETIC REALISTIC DATASETS ---
def generate_bigdata_parquet():
    """Big Data: Columnar storage (Parquet-like) with high compression potential"""
    random.seed(42)
    data = bytearray()
    # Column 1: Timestamps (high locality)
    base_ts = 1700000000
    for i in range(2*1024*1024):
        data.extend(struct.pack('<Q', base_ts + i))
    # Column 2: User IDs (Zipf distribution - hot users)
    for _ in range(2*1024*1024):
        uid = int(random.paretovariate(1.5)) % 10000
        data.extend(struct.pack('<I', uid))
    # Column 3: Event types (categorical, high repetition)
    events = [b'CLICK', b'VIEW_', b'PURCH', b'CART_']
    for _ in range(2*1024*1024):
        data.extend(random.choice(events))
    # Column 4: Metrics (floats with noise)
    for _ in range(2*1024*1024):
        data.extend(struct.pack('<f', 100.0 + random.gauss(0, 5)))
    return bytes(data[:20*1024*1024])

def generate_database_oltp():
    """Database OLTP: Row-oriented with mixed types (MySQL/PostgreSQL-like)"""
    random.seed(42)
    data = bytearray()
    for i in range(20*1024*1024 // 128):  # 128B rows
        # Primary key
        data.extend(struct.pack('<Q', i))
        # Varchar(32) - names with high prefix similarity
        name = f"User_{i % 1000:04d}".encode().ljust(32, b'\0')
        data.extend(name)
        # Timestamps (clustered)
        data.extend(struct.pack('<Q', 1700000000 + (i // 100)))
        # Status enum (4 bytes)
        status = random.choice([1, 1, 1, 2, 3])  # Skewed distribution
        data.extend(struct.pack('<I', status))
        # Balance (decimal as int64)
        data.extend(struct.pack('<q', random.randint(0, 1000000)))
        # Padding/reserved
        data.extend(b'\0' * 48)
    return bytes(data)

def generate_vm_memory():
    """Virtualization: Guest OS memory pages (high zero content + page tables)"""
    random.seed(42)
    data = bytearray()
    # 50% zero pages (unallocated/CoW)
    for _ in range(5*1024*1024 // 4096):
        if random.random() < 0.5:
            data.extend(b'\0' * 4096)
        else:
            # Page table entries (pointer-heavy)
            base = 0x00007F0000000000
            for _ in range(4096 // 8):
                data.extend(struct.pack('<Q', base + random.randint(0, 1024)*4096))
    return bytes(data[:20*1024*1024])

def generate_ai_embeddings():
    """AI/ML: FP32 embeddings (BERT/GPT-like, 768-dim vectors)"""
    random.seed(42)
    np.random.seed(42)
    # Generate embeddings with structure (clustered in semantic space)
    num_vectors = 20*1024*1024 // (768 * 4)
    embeddings = []
    for cluster in range(10):
        center = np.random.randn(768).astype(np.float32)
        for _ in range(num_vectors // 10):
            vec = center + np.random.randn(768).astype(np.float32) * 0.1
            embeddings.append(vec.tobytes())
    return b"".join(embeddings[:num_vectors])

def generate_ai_activations():
    """AI/ML: Sparse activations (ReLU output, many zeros)"""
    random.seed(42)
    np.random.seed(42)
    data = bytearray()
    for _ in range(20*1024*1024 // 4):
        val = max(0.0, random.gauss(0, 1))  # ReLU
        data.extend(struct.pack('<f', val))
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
            return len(chunk)

class FPCWrapper:
    def compress_chunk(self, chunk):
        compressed_bits = 0
        for i in range(0, len(chunk), 4):
            if i+4 > len(chunk): break
            w = struct.unpack('<i', chunk[i:i+4])[0]
            compressed_bits += 3
            if w == 0: pass
            elif -128 <= w <= 127: compressed_bits += 8
            elif -32768 <= w <= 32767: compressed_bits += 16
            elif (w & 0xFFFF) == 0: compressed_bits += 16
            else: compressed_bits += 32
        return compressed_bits / 8.0

class BDIWrapper:
    def compress_chunk(self, chunk):
        if len(chunk) != 64: return len(chunk)
        words = [struct.unpack('<q', chunk[j:j+8])[0] for j in range(0, 64, 8)]
        base = words[0]
        max_d = 8
        for w in words:
            diff = w - base
            if diff == 0: d = 0
            elif -128 <= diff <= 127: d = 1
            elif -32768 <= diff <= 32767: d = 2
            elif -2147483648 <= diff <= 2147483647: d = 4
            else: d = 8
            max_d = min(max_d, d) if d > 0 else max_d
        chunk_bits = 4 + 64 + (8 * max_d * 8)
        return min(chunk_bits / 8.0, 64)

# --- COMPREHENSIVE BENCHMARK ---
def run_comprehensive_benchmark():
    print("=== COMPREHENSIVE MEMORY COMPRESSION BENCHMARK ===\n")
    print("Loading datasets (20MB each, may take a few minutes)...\n")
    
    datasets = {
        "Text/Web (enwik8)": download_enwik8(),
        "Mixed (Silesia)": download_silesia(),
        "BigData Columnar": generate_bigdata_parquet(),
        "DB OLTP Rows": generate_database_oltp(),
        "VM Memory Pages": generate_vm_memory(),
        "AI Embeddings (FP32)": generate_ai_embeddings(),
        "AI Activations (Sparse)": generate_ai_activations()
    }
    
    algos = {
        "ZSTD_4KB": (ZSTDWrapper(), 4096),
        "ZSTD_256B": (ZSTDWrapper(), 256),
        "LZ4_4KB": (LZ4Wrapper(), 4096),
        "LZ4_256B": (LZ4Wrapper(), 256),
        "FPC_256B": (FPCWrapper(), 256),
        "BDI_64B": (BDIWrapper(), 64)
    }
    
    print(f"{'Dataset':<25} | {'ZSTD_4KB':<10} | {'ZSTD_256B':<10} | {'LZ4_4KB':<10} | {'LZ4_256B':<10} | {'FPC_256B':<10} | {'BDI_64B':<10}")
    print("-" * 110)
    
    for ds_name, data in datasets.items():
        data = data[:(len(data)//4096)*4096]
        original_size = len(data)
        results = {}
        
        for alg_name, (wrapper, chunk_size) in algos.items():
            compressed_size = 0
            for i in range(0, original_size, chunk_size):
                chunk = data[i:i+chunk_size]
                compressed_size += wrapper.compress_chunk(chunk)
            results[alg_name] = original_size / compressed_size
        
        print(f"{ds_name:<25} | {results['ZSTD_4KB']:>9.2f}x | {results['ZSTD_256B']:>9.2f}x | {results['LZ4_4KB']:>9.2f}x | {results['LZ4_256B']:>9.2f}x | {results['FPC_256B']:>9.2f}x | {results['BDI_64B']:>9.2f}x")

if __name__ == '__main__':
    run_comprehensive_benchmark()
