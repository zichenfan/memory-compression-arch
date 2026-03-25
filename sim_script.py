import argparse
import random

def simulate_decompression(temperature, chunk_size):
    """
    Simulate the decompression process based on data temperature and chunk size.
    Returns: Compression Ratio, Decompression Latency (ns), Area Utilization
    """
    if temperature == "cold":
        # Cold Data: Expect large chunks (e.g., 4KB) and complex algos (e.g., ZSTD)
        if chunk_size < 1024:
            ratio = random.uniform(1.2, 1.8) # Poor ratio on small blocks with complex algo overhead
            latency = random.randint(150, 250)
            area_util = "High (Unified Engine: Active)"
        else:
            ratio = random.uniform(2.5, 4.0) # High compression ratio
            latency = random.randint(300, 500) # High latency
            area_util = "High (Unified Engine: Active)"
    else:
        # Hot/Warm Data: Expect small chunks (e.g., 256B) and simple algos (e.g., FPC)
        if chunk_size >= 1024:
            ratio = random.uniform(1.1, 1.3) # Simple algos don't compress large blocks well
            latency = random.randint(20, 50)
            area_util = "Low (Unified Engine: Bypass)"
        else:
            ratio = random.uniform(1.3, 1.8) # Moderate compression ratio
            latency = random.randint(2, 10)  # Extremely low latency
            area_util = "Low (Unified Engine: Partial Power-down)"

    return ratio, latency, area_util

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate Unified Decompression Engine")
    parser.add_argument("--temperature", choices=["hot", "cold"], required=True, help="Data temperature")
    parser.add_argument("--chunk_size", type=int, required=True, help="Chunk size in bytes")
    args = parser.parse_args()

    ratio, latency, area = simulate_decompression(args.temperature, args.chunk_size)
    print(f"--- Simulation Results ---")
    print(f"Data Temp : {args.temperature.capitalize()}")
    print(f"Chunk Size: {args.chunk_size} Bytes")
    print(f"Comp. Ratio: {ratio:.2f}x")
    print(f"Latency   : {latency} ns")
    print(f"Engine Area: {area}")
