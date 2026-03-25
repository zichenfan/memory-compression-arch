# Unified Hardware Decompression Architecture

## Overview
This document details the unified hardware decompression engine designed to efficiently support both large-granularity complex compression (e.g., ZSTD for 4KB pages) and small-granularity simple compression (e.g., FPC for 256B chunks).

## The Dual-Granularity Challenge
Memory compression faces an inherent trade-off:
1. **Cold Data (4KB + Complex Algorithm):**
   - High compression ratio via long history windows.
   - High decompression latency and read amplification on random access.
2. **Hot/Warm Data (256B + Simple Algorithm):**
   - Low latency, cache-line-friendly access.
   - Poor compression ratio due to limited context.

## Core Innovation: Unified Reconfigurable Engine
To avoid the area overhead of two separate decompression units, our architecture reuses key datapath components:

### 1. Multi-mode Fetch & Decode Front-end
- **Metadata Parser:** Reads the chunk header to determine the compression type (Simple/Complex).
- **Fetch Unit:** Configurable fetch width based on the compression type to optimize memory bandwidth.
- **Decoder:**
  - *Complex Mode:* Activates Huffman/FSE decoders for literal and match lengths.
  - *Simple Mode:* Activates simple 3-bit prefix selectors (e.g., FPC patterns like zero-run, sign-extension). The complex decoders are clock-gated.

### 2. Reconfigurable Processing Elements (PE) Array
The datapath consists of multiple parallel 64-Byte PEs:
- **Small Granularity (Simple Mode):** The PEs operate in parallel. Four PEs independently decompress a 256B chunk in a single or few cycles, executing simple pattern expansions.
- **Large Granularity (Complex Mode):** The PEs form a pipelined ring structure. They handle the execution of literal copies and match copies (dictionary lookups) required by LZ-based algorithms.

### 3. Hybrid History Buffer (SRAM)
- **Complex Mode:** Functions as the sliding window dictionary (e.g., 2KB-4KB) for match copies.
- **Simple Mode:** The SRAM is repurposed as a write-back buffer for decompressed data to hide memory write latency, or partially powered off to save energy.

## System Integration (OS & Memory Controller)
### Temperature Management
- Access counters in the Memory Controller or OS Page Table monitor data temperature.

### Dynamic Migration (Re-compression)
- **Hot to Cold:** A background hardware engine or OS daemon collects multiple 256B hot chunks and re-compresses them into a 4KB cold chunk.
- **Cold to Hot:** When a 4KB cold chunk becomes frequently accessed, it is decompressed and stored as 256B chunks.

### Address Mapping
A lightweight Compression Metadata Table is required to manage the variable-length chunks and their respective physical locations.
