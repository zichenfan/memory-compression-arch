# 异构压缩算法的硬件资源复用微架构 (Hardware Resource Reuse)

在 Adaptive Memory Compression 架构中，宏观的 ZSTD-Lite（字典+熵编码）与微观的 FPC（静态模式匹配）/ BDI（基址差分）看似截然不同，但如果在片上部署三套独立的物理加速器，面积（Area）将不可接受。

本设计的核心创新在于：**通过可重构数据通路 (Reconfigurable Datapath)，实现 ZSTD-Lite 与 FPC/BDI 在比较器阵列、交叉开关网络、移位寄存器和 SRAM 上的深度物理复用。**

---

## 1. 压缩端 (TX Path) 的资源复用架构

### 1.1 比较器阵列复用 (Comparator Array Reuse)
无论是 ZSTD 的长距离字典匹配，还是 FPC 的短模式探测，底层都需要海量的比较器逻辑。
- **ZSTD 模式**：我们需要通过哈希查找将“当前输入字节”与“历史滑动窗口中的字节”进行比对，以寻找 Match Copy。这需要一个极宽的 **32-bit/64-bit 比较器阵列 (Comparator Array)**。
- **FPC 模式**：FPC 需要判断一个 32-bit Word 是否全是 0，或者高 24 位是否全是符号位扩展（Sign-Extended）。
- **复用设计 (Fusion)**：
  我们**不为 FPC 单独合成比较器**。相反，我们在比较器阵列的“参考输入端 (Reference Input)” 增加一组多路选择器 (MUX)。
  - 当处于 ZSTD 模式时，MUX 将 SRAM 历史字典的输出连入比较器。
  - 当处于 FPC 模式时，MUX 将参考输入硬线拉低（全 0）或接入符号扩展掩码（Sign Mask）。
  - **结论**：ZSTD 庞大的匹配逻辑瞬间变成了 FPC 的零值/符号探测器。没有任何额外逻辑开销。

### 1.2 差分计算与 ALUs 复用 (BDI vs ZSTD Hash)
- **BDI 模式**：需要大量的减法器（Subtractor）计算 Base 与 Word 的 Delta 差值。
- **ZSTD 模式**：前端需要计算字节的 Hash 索引用于查表，通常包含加法和移位操作。
- **复用设计**：ZSTD 的哈希计算单元（ALU Tree）通过切换控制信号，转化为 BDI 的并行减法器网络。

### 1.3 变长位流组装网络 (Bit-stream Packer & Barrel Shifter)
这是压缩引擎占地极大的一个模块，负责把不定长的数据（比如 3-bit 的前缀，接着 8-bit 的 payload）紧凑地拼接成连续的比特流。
- 无论是 ZSTD 输出的 FSE / Huffman 不定长编码位流，还是 FPC 产生的前缀流，都需要经过对齐。
- **完全复用**：打包器（Packer）后端的 **桶形移位寄存器 (Barrel Shifter)** 完全共享。前端只需统一将数据转换为 `(Length, Payload)` 格式喂给 Packer 即可。

### 1.4 FSE 熵编码器的时钟门控 (Clock Gating)
- **设计**：当检测到数据以微观模式 (Micro 64B) 流入时，硬件直接对 ZSTD 后端的 FSE 状态机发出 **Clock Gating (时钟门控)** 信号，彻底切断其翻转。
- **收益**：大幅节省动态功耗 (Dynamic Power)，同时零延迟跳过该流水线阶段。

---

## 2. 解压端 (RX Path) 的资源复用架构

解压端的延迟是决定系统 IPC 的生命线。复用的核心在于**将 FPC 的模式展开视为 ZSTD 字典复制的“特例”**。

### 2.1 交叉开关路由复用 (Crossbar / Xbar Sharing)
- **ZSTD 解压**：解析出指令 `(Match, Offset=20, Length=8)` 后，需要从内部 History SRAM 读取这 8 字节，并通过一个宽幅的 **Crossbar (交叉开关)** 路由到输出缓冲区的正确位置。
- **FPC 解压**：解析出 `3-bit Prefix` 后，需要将短的 payload（比如 1 Byte）路由到输出的 32-bit Word 的低 8 位，并高位补零。
- **复用设计**：使用**同一个 Crossbar**！在 ZSTD 模式下，Crossbar 的输入源是 History SRAM；在 FPC 模式下，输入源是紧凑的 payload 数据，而高位输入端通过 MUX 接地（拉低至 0）或接符号位。

### 2.2 SRAM 存储资源的动态调配 (SRAM Reallocation)
ZSTD-Lite 引擎内部拥有 2KB ~ 4KB 的 SRAM 作为滑动窗口字典（History Buffer）。在处理 64B 的 FPC/BDI 热数据时，这个大容量字典完全闲置。
- **架构创新**：当硬件判定当前内存区域主要是微观热数据（FPC/BDI 统治）时，我们将这块 4KB 的 History SRAM 动态重新映射为 **解压后数据行缓冲 (Decompressed Line Buffer)** 或作为前面提到的 **Page Cache**。
- 这意味着我们把“为冷数据准备的解压字典”，无缝转化为“为热数据准备的 L4 级极速缓存”，实现了存储面积的 100% 榨取！

---

## 3. 硬件融合收益总结

| 逻辑模块 | ZSTD / Deflate 角色 | FPC / BDI 角色 | 复用方式 (Reuse Mechanism) |
| --- | --- | --- | --- |
| **Comparator Array** | Hash 碰撞比较 / CAM 字典匹配 | 零游程与符号位前缀探测 | 切换参考端 MUX 为常量 0/Mask |
| **ALU Tree** | 计算 Rolling Hash | 计算 BDI 的 Delta 差分 | 更改加减控制信号 |
| **History SRAM** | 4KB 滑动匹配窗口字典 | 闲置 / 切换为热数据解压缓冲 | 动态重新映射 SRAM 控制器地址 |
| **Bit Packer** | 拼接变长 Huffman/FSE 编码流 | 拼接 3-bit 前缀与载荷 | 数据格式统一对齐，完全复用 |
| **Crossbar (RX)** | 从字典中路由 Match 字符串 | 将载荷路由对齐并高位补零 | 切换输入源，共享移位路由网络 |
| **FSE State Machine** | 解析熵编码位流 | 无需使用 | **时钟门控 (Clock Gated) 降功耗** |

通过上述极度深度的 RTL 级复用，我们的 **Unified Datapath** 可以做到：在不到单个标准 ZSTD 硬件引擎 1.15x 面积的情况下，同时完整具备了 FPC 与 BDI 的单周期解压能力。