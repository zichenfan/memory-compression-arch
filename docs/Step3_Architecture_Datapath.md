# 混合粒度并发竞猜主存压缩架构 (V4 Final)

## 1. 架构背景与核心思想
基于真实数据集的压测结论，真实数据中心的内存负载极度多样化。单一的压缩算法（如纯 LZ 或纯 FPC）无法覆盖全场景。
- **ZSTD 的霸权**：在文本、网页、列存数据上，4KB 宏观粒度的 ZSTD 压缩率无敌。
- **FPC / BDI 的局部高光**：在行存数据库、AI 稀疏激活值上，64B 微观粒度的 FPC/BDI 依靠零游程和差分编码大幅领先。
- **FP32 稠密数据的死区**：高熵的大模型 Embeddings 几乎完全不可压。

**核心架构决策**：**“宏观 ZSTD (4KB) 保底 + 微观并发竞猜 (64B FPC/BDI) + 早期拒止”**。为了让 OS 对这一切无感，我们将所有地址转换和硬件逻辑下沉至内存控制器 (Memory Controller, MC)。

---

## 2. 统一地址管理方案：多态元数据 (Polymorphic Metadata)
由于 4KB 的宏观压缩和 64B 的微观压缩在寻址机制上存在根本冲突，我们设计了 **160-bit (20 Bytes) 的多态元数据项**。通过最高位 `Page_Mode_Flag` 动态定义物理页的压缩状态。

### 2.1 模式 0：微观模式 (Micro Mode，FPC/BDI 胜出)
当页面以 64B 为粒度碎片化压缩时（16B/32B/48B/64B）：
- `Bit [159]`: 0 (Micro Mode)
- `Bit [158:127]`: **Base CPA** (压缩物理基址)
- `Bit [124:0]`: **Size Codes Array** (64 个 2-bit 状态码)
- **寻址方式**：通过 **并行前缀和加法器 (PPA)** 计算前缀和，1~2 个 cycle 即可算出第 K 个 Cache Line 的精确偏移。

### 2.2 模式 1：宏观模式 (Macro Mode，ZSTD 胜出)
当页面被 ZSTD 整体打包压缩时（例如整个 4KB 压成了 1.2KB）：
- `Bit [159]`: 1 (Macro Mode)
- `Bit [158:157]`: Algo_ID (标记为 ZSTD)
- `Bit [156:125]`: **Base CPA**
- `Bit [124:115]`: **Total Compressed Size** (记录打包后的总块大小)
- **寻址方式**：抓取整个块并解压，配合 **Page Cache** 摊销解压延迟。

---

## 3. 数据通路 (Datapath) 深度设计

### 3.1 智能写入通路 (Write Datapath)
当 LLC 发生 Write-back 时：
1. **Stage 1: 早期拒止 (Early Abort)**
   数据进入 **硬件熵评估器**。若判断为高熵（如 FP32 稠密向量），直接触发 Bypass，放弃压缩，消除不可压数据带来的写入延迟和功耗浪费。
2. **Stage 2: 并发竞速 (Parallel Racing)**
   通过评估的数据同时广播给三个硬件引擎：ZSTD-Lite、FPC、BDI。在 5-10 cycles 内并发执行压缩。
3. **Stage 3: 仲裁与打包 (Arbiter)**
   仲裁器选出体积最小的胜者。生成 `Algo_ID` 和 `Size_Code`，并更新多态元数据。若压缩率不足 85%，回退为未压缩。

### 3.2 极速读取通路 (Read Datapath)
当 CPU 发生 Read Request 时：
1. **元数据读取**：从片上 Metadata Cache (M-Cache) 极速读取 20 Bytes。
2. **动态路由 (Dynamic Routing)**：
   - 若 `Flag == 0` (微观)：PPA 算出绝对地址，抓取变长数据，路由至 FPC/BDI 硬件，1~2 cycles 极速解压送回 LLC。
   - 若 `Flag == 1` (宏观)：抓取整个 ZSTD 压缩页，ZSTD 引擎解压后存入 MC 旁置的 **Page Cache (如 32KB SRAM)**。提取目标 Cache Line 送回 CPU。后续该页的访问将 0-cycle 命中 Page Cache。

---

## 4. 边缘情况处理：动态降级与数据膨胀

### 4.1 微观模式的体积膨胀
当 16B 膨胀为 32B 时，优先消耗在分配 CPA 时预留的 **Slack（缓冲缝隙）**。若 Slack 耗尽，硬件将触发 Overflow 异常，通过预留的全局溢出表重新分配块空间。

### 4.2 宏观模式的动态降级 (Dynamic Downgrade)
**痛点**：若 CPU 只修改了 ZSTD 页面中的 1 个 64B 行，重压整个 4KB 页面代价极大。
**解决机制**：
1. 引入 **异常行缓冲 (Exception Line Buffer, ELB)**，修改的行先写入 SRAM 缓冲。
2. 当一个 4KB 页面中被修改的行数超过阈值（例如 4 行），硬件触发后台任务。
3. 将该 4KB 页面彻底解压，交由 FPC/BDI 重新在 64B 粒度下并发压缩。
4. 将该页元数据的 `Page_Mode_Flag` 置 0。**完成从“宏观 4KB”向“微观 64B”的平滑降级。**