# 异构压缩算法的硬件资源复用微架构 (Hardware Resource Reuse)

在 Adaptive Memory Compression 架构中，宏观的 ZSTD-Lite（基于 CAM/Hash 字典与熵编码）与微观的 FPC（静态模式匹配）/ BDI（基址差分）看似截然不同。如果物理上分离，面积（Area）将不可接受。

本设计的核心创新在于：**通过可重构数据通路 (Reconfigurable Datapath)，实现 CAM、Hash ALU 树、交叉开关网络在不同压缩语义下的深度物理复用。**

---

## 1. 压缩端 (TX Path) 的核心资源复用

### 1.1 CAM 的动态身份转换 (CAM to FPC Classifier)
在高性能 ZSTD-Lite 硬件中，近期滑动窗口通常采用 **TCAM/BCAM (内容可寻址存储器)** 实现单周期并发查找。
- **ZSTD 模式（动态滑动字典）**：数据作为 Search Key 广播给 CAM，匹配命中的 Entry 地址作为 `Offset` 输出。
- **FPC 模式（静态模式分类器）**：FPC 算法本质是匹配 8 种静态模式（如全0、符号扩展等）。在微观模式下，硬件将这 8 种静态 Pattern（配合 Don't Care 掩码）预载入到 CAM 的前 8 个 Entry 中。输入数据进入 CAM 后，**Matchline 直接输出 FPC 的 3-bit Prefix Code**。
- **复用收益**：完全复用极其昂贵的 CAM 阵列，将字典检索器瞬间变为单周期的 FPC 静态模式分类器。

### 1.2 Hash ALU 树重构为差分器 (Hash ALU to BDI Subtractor)
在处理 4KB 长距离字典时，ZSTD 会使用 SRAM 加上前端的 Hash 计算逻辑（乘法器、加法器、移位器树）来定位候选字典块。
- **BDI 的痛点**：BDI 压缩需要并行的减法器来计算 `Delta = Value - Base`。CAM 和普通比较器无法进行算术运算。
- **复用设计**：在微观模式下，ZSTD 前端用于计算 Hash 的 ALU 树，通过切换操作码（Opcode），直接重构为 BDI 的并行减法器网络。实现了算术逻辑单元的 100% 榨取。

### 1.3 验证比较器的降级 (Matcher to Zero-Detector)
ZSTD 从 SRAM 取出候选块后，需要进入一个短宽度的并行比较器阵列（如 16 Bytes）验证 Match Length。
- 在不需要长字典的微观场景中，通过参考端的 MUX 切换，切断 SRAM 连线并接入常量 `0` 或 `Sign Mask`，该阵列被降级复用为额外的零游程/符号扩展验证器。

### 1.4 FSE 熵编码器的时钟门控 (Clock Gating)
- **设计**：当检测到数据以微观模式流入时，硬件直接对 ZSTD 后端的 FSE 状态机发出 **Clock Gating (时钟门控)** 信号，彻底切断其翻转。大幅节省动态功耗。

---

## 2. 解压端 (RX Path) 的资源复用架构

### 2.1 交叉开关路由复用 (Crossbar / Xbar Sharing)
- **ZSTD 解压**：解析出指令后，从 History SRAM 读取字节，通过宽幅的 **Crossbar (交叉开关)** 路由到输出缓冲区。
- **FPC 解压**：解析出 `3-bit Prefix` 后，需要将短的 Payload 路由到 32-bit Word 的低位并高位补零。
- **复用设计**：在 FPC 模式下，Crossbar 的输入源切换为短 Payload 数据，高位输入端硬连线接地（补零）或接符号位，完全共享庞大的移位路由网络。

### 2.2 SRAM 存储资源的动态调配 (SRAM Reallocation)
ZSTD-Lite 引擎内部拥有 2KB ~ 4KB 的 SRAM 作为历史滑动字典（History Buffer）。
- **架构创新**：当硬件处理 64B 的 FPC/BDI 热数据时，这个长字典 SRAM 完全闲置。此时，我们将这块 4KB SRAM 动态重新映射为 **解压后数据行缓冲 (Decompressed Line Buffer)** 或 **Page Cache**（摊销宏观解压延迟的 L4 缓存）。实现了存储面积的不留死角复用。
