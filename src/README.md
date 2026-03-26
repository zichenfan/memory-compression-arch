# Memory Compression Architecture - Source Code

This directory contains the core simulation components of the **Adaptive Memory Compression Architecture** (Step 3).

## Directory Structure

*   `fse/`: Contains a reference implementation of the **Finite State Entropy (FSE / tANS)** encoder. 
    *   This is the core algorithm that allows ZSTD-Lite to achieve theoretical Shannon limits with high speed on 4KB macroscopic pages.
    *   `fse_encoder.cpp`: Demonstrates how symbols are normalized and spread across states to build the fast transition table.

## Build and Run

Inside `fse/`, simply run:
```bash
make
./fse_encoder
```

*(Note: Requires a standard C++17 compiler like g++ or clang++)*