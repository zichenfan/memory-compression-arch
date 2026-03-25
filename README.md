# Adaptive Memory Compression Architecture

A unified hardware acceleration architecture for adaptive memory compression, balancing compression ratio and decompression latency across different data temperatures.

## Overview
This project explores a hybrid memory compression approach:
- **Cold Data**: Large granularity (e.g., 4KB page) + Complex algorithms (e.g., ZSTD) -> High compression ratio
- **Warm/Hot Data**: Small granularity (e.g., 256B cache line) + Simple algorithms (e.g., FPC/BDI) -> Low decompression latency

The core innovation is designing a **Unified Hardware Decompression Engine** that reuses datapath components to support both paradigms efficiently.
