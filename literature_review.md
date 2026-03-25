# Step 1.1: Literature Review & Architectural Pathfinding

## 1. State-of-the-Art in Memory Compression
Memory compression algorithms generally fall into two extremes based on the latency vs. ratio trade-off.

### 1.1 Low-Latency / Small-Granularity (Hot Data Friendly)
Algorithms designed for L2/L3 caches or fast memory tiers.
- **FPC (Frequent Pattern Compression) [ISCA 2004]:** Exploits data predictability (e.g., zero runs, small integers, sign-extended words). Decompression is heavily parallelized using 3-bit prefixes.
- **BDI (Base-Delta-Immediate) [PACT 2012]:** Exploits spatial value locality (e.g., pointers or arrays of similar structures). Stores a "Base" value and small "Deltas". Extremely fast decompression (just an addition operation: Base + Delta).
- **Hardware Profile:** Shallow pipeline, parallel ALUs (adders/comparators), extremely low latency (1-5 cycles), but poor compression on complex data types like strings or mixed structs.

### 1.2 High-Ratio / Large-Granularity (Cold Data Friendly)
Algorithms designed for Main Memory (Page level) or Storage.
- **LZ-family (LZ4, ZSTD):** Uses Lempel-Ziv dictionary matching. ZSTD adds FSE (Finite State Entropy) coding.
- **Hardware Profile:** Sequential dependency in decompression (a match might depend on a previously decoded match). Requires large SRAM for the sliding window and complex state machines for FSE. High latency (100+ cycles for 4KB), but excellent compression (often 3x - 4x).

## 2. The User's Insight: Algorithm Scaling vs. Heterogeneous Fusion
Can we achieve hardware reuse by scaling ZSTD down, rather than forcing FPC/BDI into the same engine?

### Path A: Homogeneous Algorithm Scaling (Simplified ZSTD <-> Full ZSTD)
- **Concept:** Use a stripped-down ZSTD for 256B chunks. Disable FSE (use fixed tables) and restrict the dictionary window to the 256B chunk itself.
- **Pros:** Near 100% hardware reuse. The datapath is identical; we just power-gate the FSE decoder and the large history SRAM.
- **Cons:** 
  1. *Latency Floor:* Even simplified LZ has a sequential decode loop. It might take 10-20 cycles for 256B, missing the ultra-low latency target (<5 cycles) of hot data.
  2. *Data Characteristics:* Memory data (especially at 256B granularity) is dominated by pointers and integers. LZ relies on exact byte-sequence matches. BDI (Base+Delta) handles numerical variance much better than LZ. A 256B LZ might yield near 1.0x (no compression) for pointer arrays, whereas BDI could yield 1.5x.

### Path B: Heterogeneous Datapath Fusion (FPC/BDI + ZSTD)
- **Concept:** The "Holy Grail" of this project. Design a unified Processing Element (PE) where the ALU used for *Match Copy Address Calculation* in ZSTD is repurposed for *Base + Delta Addition* in BDI.
- **Pros:** Captures the true optimal compression for both data types. ultra-low latency for hot data, max capacity for cold data.
- **Cons:** High control complexity. Muxing the datapath requires careful RTL design to avoid increasing the critical path delay (which would hurt maximum clock frequency).

## 3. Next Steps & Recommendation
We will explore both paths in the software simulation phase (Step 2). We will model:
1. 4KB ZSTD
2. 256B Simplified ZSTD (LZ4-like)
3. 256B BDI/FPC
By running real memory traces, we will definitively answer whether "Simplified ZSTD" provides enough compression on 256B to justify its hardware simplicity, or if we must pursue the "Datapath Fusion" (Path B) to achieve acceptable hot-data compression ratios.
