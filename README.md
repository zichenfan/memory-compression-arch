# Adaptive Memory Compression Architecture (混合粒度并发竞猜主存压缩架构)

A high-performance, OS-transparent memory compression architecture designed for modern data center workloads, bridging the gap between compression ratio and decompression latency.

## 🌟 Key Innovations

1. **Heterogeneous Datapath Fusion (异构数据通路融合)**
   - **Macro Mode (4KB)**: ZSTD-Lite engine for maximum compression ratio on cold/bulk data (e.g., Columnar DBs, Text).
   - **Micro Mode (64B/256B)**: Parallel speculation with FPC and BDI for ultra-low latency on hot/granular data (e.g., Row DBs, AI Sparse Activations).
2. **Early Abort & Bypass (早期拒止机制)**
   - Hardware entropy estimator to quickly bypass incompressible high-entropy data (e.g., FP32 Dense Embeddings), saving power and write latency.
3. **Polymorphic Metadata & Unified Addressing (多态元数据与统一寻址)**
   - A 160-bit (20 Bytes) metadata entry per 4KB physical page.
   - Uses a Parallel Prefix Adder (PPA) for 1~2 cycle absolute address calculation of variable-length compressed blocks.
   - 100% OS-transparent.

## 📂 Repository Structure

- `docs/`: Architecture specifications, design documents, and benchmark reports.
  - `Step1_Architecture_Plan.md`: Core architecture and hardware reuse planning.
  - `Step2_Benchmark_Simulation.md`: V3 production-level benchmark report across diverse datasets.
  - `Step3_Architecture_Datapath.md`: Datapath design, early abort, and polymorphic metadata specifications.
- `src/`: Algorithm simulations and RTL prototypes.
  - `fse/`: Finite State Entropy (FSE) encoder simulation (C++ and Python) used in the ZSTD-Lite engine.

## 🚀 Project Status
- [x] Step 1: Literature Review & Architecture Route
- [x] Step 2: V3 Production-level Benchmark & Simulation
- [x] Step 3: Hardware Datapath & OS-Transparent Memory Management Design
- [ ] Step 4: RTL Implementation & gem5 Integration
