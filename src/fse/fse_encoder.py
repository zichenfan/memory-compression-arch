import math
from collections import Counter

# =========================================================================
# FSE (Finite State Entropy) 编码器核心模拟 (Python 版)
# ZSTD-Lite 引擎在 4KB 宏观页面上实现接近香农极限的高速压缩的核心算法
# =========================================================================

# 状态表大小 (通常是 2 的幂，真实 ZSTD 中可能是 2048 或 4096，此处用 64 简化展示)
TABLE_SIZE = 64

def normalize_frequencies(data):
    """
    第一步：频率统计与规范化 (Normalization)
    将实际符号的出现频率，等比例缩放，使得总和严格等于 TABLE_SIZE。
    """
    counts = Counter(data)
    total_elements = len(data)
    
    stats = {}
    current_sum = 0
    
    for sym, count in counts.items():
        # 线性缩放
        norm = round((count / total_elements) * TABLE_SIZE)
        if norm == 0 and count > 0:
            norm = 1  # 保证出现的符号至少占据 1 个状态
            
        stats[sym] = {'count': count, 'norm_freq': norm}
        current_sum += norm
        
    # 修正浮点数取整带来的误差，确保状态总数绝对等于 TABLE_SIZE
    if current_sum != TABLE_SIZE:
        diff = TABLE_SIZE - current_sum
        # 简单策略：把误差补偿给出现频率最高的符号
        max_sym = max(stats, key=lambda s: stats[s]['norm_freq'])
        stats[max_sym]['norm_freq'] += diff
        
    return stats

def build_fse_table(stats):
    """
    第二步：状态转换表构建 (Spread Symbols)
    这是 FSE 的灵魂！将规范化后的符号按特定步长均匀地打散到状态表中。
    均匀打散是为了让硬件解码/编码时产生的“分数位”更加平滑，从而压榨出极限压缩率。
    """
    fse_table = [None] * TABLE_SIZE
    
    # ZSTD 的经典 Spread 步长公式，保证步长与 TABLE_SIZE 互质
    step = (TABLE_SIZE >> 1) + (TABLE_SIZE >> 3) + 3
    position = 0
    
    # 遍历每个符号
    for sym in sorted(stats.keys()):
        norm_freq = stats[sym]['norm_freq']
        for _ in range(norm_freq):
            fse_table[position] = sym
            
            # 跳到下一个位置
            position = (position + step) % TABLE_SIZE
            
            # 防御性编程：如果该位置被占，线性探测寻找下个空位 (步长互质时极少发生)
            while fse_table[position] is not None and fse_table[position] != sym:
                position = (position + 1) % TABLE_SIZE
                
    return fse_table

def main():
    print("=== FSE (tANS) Encoder Simulation (Python Version) ===")
    
    # 模拟一段在 4KB 页面中偏斜的数据 (例如 60 个 A, 30 个 B, 10 个 C)
    data = ['A'] * 60 + ['B'] * 30 + ['C'] * 10
    print(f"1. Original Data Size: {len(data)} bytes")
    
    # 1. 规范化
    stats = normalize_frequencies(data)
    print(f"\n2. Normalized Frequencies (Target Table Size = {TABLE_SIZE}):")
    for sym in sorted(stats.keys()):
        print(f"   Symbol '{sym}': Count={stats[sym]['count']:>2}, NormFreq={stats[sym]['norm_freq']:>2}")
        
    # 2. 状态映射表构建
    fse_table = build_fse_table(stats)
    print("\n3. Built FSE State Table (Spread Symbols):")
    # 按 16 个一行打印，直观查看分布
    for i in range(0, TABLE_SIZE, 16):
        row = fse_table[i:i+16]
        print("  " + " ".join(f"{sym}" for sym in row))
        
    print("\n[Architecture Note]: ZSTD-Lite uses this uniformly spread table to encode")
    print("macro 4KB pages in our architecture, achieving theoretical compression limits")
    print("while hardware decoder only needs table lookups (extremely fast).")

if __name__ == "__main__":
    main()