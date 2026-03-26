---
marp: true
theme: default
paginate: true
header: 'Adaptive Memory Compression Architecture'
footer: 'Memory Compression Benchmark & Analysis'
style: |
  section {
    font-family: 'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  h1, h2 {
    color: #0366d6;
  }
---

# 主存压缩算法全景解析
## 从宏观字典 (Dictionary) 到微观模式 (Pattern) 的演进

**演讲人**: Jason
**项目**: 混合粒度并发竞猜主存压缩架构

---

## 目录 (Agenda)

1. **主存压缩的根本矛盾**: 压缩率 vs 解压延迟
2. **宏观字典类算法**: Lempel-Ziv 家族 (LZ4 / ZSTD)
3. **微观模式类算法**: FPC (Frequent Pattern Compression)
4. **微观差分类算法**: BDI (Base-Delta-Immediate)
5. **架构总结**: 走向异构融合 (Heterogeneous Fusion)

---

## 1. 主存压缩的根本矛盾
在真实的 CPU 内存体系中，我们面临着不可调和的 Trade-off：

- **大粒度 (如 4KB Page) + 复杂算法**：
  - ✅ **优势**：压缩率极高（>2.0x），充分挖掘全局冗余。
  - ❌ **痛点**：延迟极高（数十 cycles）。若 CPU 仅需读取 64B，会导致严重的“读放大 (Read Amplification)”。
- **小粒度 (如 64B Cache Line) + 简单算法**：
  - ✅ **优势**：极速解压（1~2 cycles），不拖累 Load-to-Use 关键路径。
  - ❌ **痛点**：字典范围太小，遇到高熵数据毫无压缩能力，整体压缩率低。

---

## 2. 宏观字典类算法：LZ4 & ZSTD
**核心思想**：寻找历史滑动窗口中的“重复字节串 (Match Copy)”。

- **LZ4**：
  - 牺牲长距离字典以换取速度。但在 256B 小窗口下面对离散数据（如数据库行），压缩率骤降（仅 1.09x）。
- **ZSTD (Zstandard)**：
  - 现代压缩的巅峰。除了寻找重复字符串，还结合了 **FSE (Finite State Entropy)** 熵编码。
  - **高光时刻**：在长文本或 4KB 冷数据页面上压缩率处于统治地位（最高 4.5x）。
  - **致命弱点**：全流水线解压延迟高，强依赖长历史窗口 (History Buffer)。

---

## 3. 微观模式类算法：FPC
**FPC (Frequent Pattern Compression)** 专为 64B 缓存行级压缩设计。
**核心思想**：不找历史重复字符串，只匹配 32-bit Word 内的静态模式。

**8种常见高频模式 (Frequent Patterns)**：
1. 零值 (Zero Run)
2. 4-bit / 8-bit / 16-bit 符号位扩展 (Sign-Extended)
3. 高位一半全零 / 低位一半全零
4. 两个 16-bit 组合字...

**表现**：在数据库行存结构（大量 Padding 补零和短整形）中，凭借简单的 3-bit Prefix + Payload，反杀 ZSTD，单周期即可硬件解码！

---

## 4. 微观差分类算法：BDI
**BDI (Base-Delta-Immediate)** 同样专攻 64B 热数据，但思路与 FPC 完全不同。
**核心思想**：利用同一 Cache Line 中数据的“空间数值局部性”。

- **工作机制**：
  - 提取数据中的某个字作为 **Base（基址）**（甚至默认 Base=0）。
  - 计算其余所有字与 Base 的差值 **Delta**。
  - 只要 Delta 足够小（例如只需要 1 byte 或 2 bytes 即可表示），就能将整个 64B 压缩！
- **高光时刻**：在密集的对象指针数组 (SPEC_PTR) 和色彩像素矩阵中，BDI 的多路减法器阵列展现出了极强的压缩能力。

---

## 5. 架构总结：走向异构融合
单一算法无法统治数据中心的多样化负载 (Text, DB, Pointer, FP32)。

**解决方案：Unified Datapath (统一数据通路)**
1. **并发竞猜**：将 ZSTD 的比较器降级重构为 FPC 分类器，将 Hash ALU 重构为 BDI 减法器。硬件并行运行，赢者通吃！
2. **早期拒止 (Early Abort)**：通过硬件熵评估，直接 Bypass 不可压的稠密浮点张量（FP32 Embeddings），消除无用功耗。

**结论**：在宏观用 ZSTD 兜底，微观用 FPC/BDI 猎杀高频局部性，这是主存压缩架构的终极形态。