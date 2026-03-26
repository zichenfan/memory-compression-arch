# 整体硬件微架构详细设计 (Hardware Microarchitecture)

本文档完整呈现了**混合粒度并发竞猜主存压缩架构 (Adaptive Memory Compression Architecture)** 在 RTL 级别的顶层硬件设计。该硬件位于 CPU 的**内存控制器 (Memory Controller, MC)** 内，介于末级缓存 (LLC) 与 DDR PHY 之间。

整体硬件被划分为三大核心模块：**压缩单元 (Compression Unit)**、**解压单元 (Decompression Unit)** 以及 **地址管理模块 (Address Management Module)**。

---

## 1. 压缩单元 (Compression Unit - TX Path)
负责处理从 LLC 写回到主存的数据 (Write-back)。其设计目标是：**在极短的时钟周期内找出最高压缩率的方案，同时避免不可压数据浪费功耗。**

### 1.1 硬件熵评估器 (Hardware Entropy Estimator)
- **功能**：早期拒止 (Early Abort)。
- **硬件实现**：通过一个单周期 (1-cycle) 的位翻转计数器 (Bit-flip Counter) 或非零字节统计树。
- **逻辑**：当数据块（如 64B 或 256B）的熵值超过阈值（如大模型 FP32 稠密张量），直接触发 Bypass 信号，关闭后续所有压缩引擎的时钟 (Clock Gating)，数据原样写入主存。

### 1.2 并发竞猜引擎阵列 (Parallel Speculative Engines)
当数据通过熵评估后，数据总线将其广播给三个硬件引擎进行**并发压缩**：
1. **ZSTD-Lite 引擎 (宏观 4KB 级)**：
   - **硬件构成**：基于多体 SRAM 的滑动历史字典 + FSE (有限状态熵) 硬件编码器。
   - **工作模式**：将连续的 64 个 64B Cache Line 汇聚后进行宏观流式压缩。
2. **FPC 引擎 (微观 64B 级)**：
   - **硬件构成**：纯组合逻辑。包含 16 个并行的 32-bit 前缀模式比较器（零游程、符号扩展等）。
   - **延迟**：1~2 cycles。没有任何复杂状态机。
3. **BDI 引擎 (微观 64B 级)**：
   - **硬件构成**：基址提取器 (Base Extractor) + 减法器阵列 (Subtractor Array)。计算 Base 与各字的 Delta 差值。

### 1.3 仲裁与打包器 (Arbiter & Packer)
- **功能**：在设定的 Cycle 预算内，比较三个引擎输出的 `Compressed_Size`。
- **逻辑**：选择 Size 最小的胜出者。如果胜出者的压缩率低于 85%，则降级为 Uncompressed (不压缩)。
- **输出**：生成 `Algo_ID` (2-bit) 和 `Size_Code` (2-bit)，并将其发送给地址管理模块更新元数据。

---

## 2. 解压单元 (Decompression Unit - RX Path)
负责处理从主存读入 LLC 的数据 (Read Request)。其设计目标是：**极速解压，不能让解压延迟成为 Load-to-Use 关键路径的瓶颈。**

### 2.1 动态解压路由 (Dynamic De-MUX)
- 硬件通过读取元数据中的 `Algo_ID`，控制数据流向：
  - `00` -> **Bypass 通路**：0 cycles 延迟，直接送回 LLC。
  - `10 / 11` -> **FPC/BDI 解压通路**。
  - `01` -> **ZSTD-Lite 解压通路**。

### 2.2 微观解压器 (FPC / BDI Decompressor)
- **硬件构成**：移位寄存器 (Shift Registers) + 加法器树。
- **性能**：只需根据 Header 中的 3-bit 前缀将数据还原，1~2 个 cycles 即可完成 64B 数据的解压。

### 2.3 宏观解压器与影子页表缓存 (ZSTD Decompressor & Page Cache)
- **痛点解决**：ZSTD 必须解压整个 4KB 数据块，延迟高达 10~20 cycles。若 CPU 只请求其中 64B，会导致严重的读放大和时延。
- **Page Cache 硬件 (核心创新)**：
  - 在 MC 内部旁置一块 **32KB 的高速 SRAM**（可容纳 8 个解压后的完整 4KB 明文页）。
  - 当 ZSTD 解压完整个 4KB 页面后，数据全部存入 Page Cache。
  - 随后直接从 Page Cache 中将 CPU 请求的那 64B 送回 LLC。
- **收益**：由于极强的空间局部性，CPU 接下来对该 4KB 页面内其他 Cache Line 的读取将 **100% 在 Page Cache 中命中 (0-cycle 解压延迟)**，完美摊销了 ZSTD 的初始解压代价。

---

## 3. 地址管理模块 (Address Management Module)
负责连接 OS 的物理地址 (PA) 与 DRAM 真实的压缩物理地址 (CPA)，彻底对 OS 屏蔽变长压缩的物理碎片。

### 3.1 片上元数据缓存 (Metadata Cache, M-Cache)
- **硬件构成**：128KB 的 SRAM 阵列，组织形式类似 TLB。
- **内容**：缓存 20 Bytes 的**多态元数据项 (Polymorphic Metadata)**。
  - 包含 `Page_Mode_Flag`、`Base CPA (32-bit)`、`Size_Codes (64 x 2-bit)` 或 `Total Compressed Size (10-bit)`。
- **覆盖率**：可覆盖约 25MB 的活跃物理内存集，命中率 > 98%。

### 3.2 64 路并行前缀和加法器 (Parallel Prefix Adder, PPA)
- **功能**：解决微观模式下 16B/32B/48B/64B 变长数据块的绝对地址计算。
- **硬件拓扑**：6 层的 **Kogge-Stone 并行加法树**。
- **输入**：64 个 2-bit 的 Size Code。
- **性能**：在 3GHz 时钟下，只需 **< 0.5ns (单周期内)** 即可计算出目标 Cache Line 之前的总段数，进而得出确切的 CPA。这是整个变长架构能在硬件落地的基石。

### 3.3 异常行缓冲与溢出遍历器 (ELB & Overflow Walker)
- **异常行缓冲 (Exception Line Buffer, ELB)**：针对 ZSTD (宏观) 模式下，单行写回导致的“写放大”问题。少量修改的行暂存在此 SRAM 缓冲中。超过阈值时触发硬件状态机的“动态降级 (Dynamic Downgrade)”。
- **溢出遍历器 (Overflow Table Walker)**：当 Cache Line 从 16B 膨胀到 32B 且耗尽了预留的 Slack 时，硬件状态机挂起当前操作，查阅隐藏内存区中的溢出表，重新分配新的物理块空间并更新 Base CPA。

---

## 4. 硬件代价总结 (Overhead Analysis)
1. **面积 (Area)**：
   - 最大的组件是 M-Cache (128KB) 和 Page Cache (32KB)。总计 160KB SRAM 在现代 7nm/5nm CPU Die 上占用面积不到 0.2 mm²。
   - PPA、熵评估器、FPC/BDI 纯组合逻辑面积可忽略。
   - ZSTD 硬件引擎约占用 0.05 mm²。
2. **时延 (Latency)**：
   - 寻址计算完全隐藏在 M-Cache 读取的 1-cycle 中。
   - FPC/BDI 热数据解压增加 1~2 cycles，ZSTD 冷数据解压由 Page Cache 摊销。
3. **OS 修改**：**0 行代码修改**。OS 依然以 4KB 为粒度分配内存，底层变长魔法由 MC 硬件全权包办。