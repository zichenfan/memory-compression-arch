#include <iostream>
#include <vector>
#include <map>
#include <cmath>
#include <algorithm>
#include <iomanip>

using namespace std;

// === FSE 编码的核心步骤模拟 ===
// FSE (Finite State Entropy) 是基于 tANS (Tabled Asymmetric Numeral Systems) 的。
// 它能够达到接近香农熵极限的压缩率，支持分数位的理论长度。

// 假设我们有 256 个符号 (0~255)，状态表大小为 N (通常是 2 的幂，如 4096，这里用 64 简化演示)
const int TABLE_SIZE = 64; 

struct SymbolStat {
    uint8_t symbol;
    int count;        // 原始频率
    int norm_freq;    // 规范化后的频率 (总和等于 TABLE_SIZE)
};

// 1. 频率统计与规范化 (Normalization)
// 保证所有符号的 norm_freq 加起来等于 TABLE_SIZE
vector<SymbolStat> normalizeFrequencies(const vector<uint8_t>& data) {
    map<uint8_t, int> counts;
    for (uint8_t val : data) {
        counts[val]++;
    }

    vector<SymbolStat> stats;
    int total_elements = data.size();
    int current_sum = 0;

    for (auto const& [sym, count] : counts) {
        // 简单的线性缩放，实际 ZSTD 的 FSE 有更复杂的误差分摊算法保证高频符号精度
        int norm = round((double)count / total_elements * TABLE_SIZE);
        if (norm == 0 && count > 0) norm = 1; // 至少保留 1 个状态
        stats.push_back({sym, count, norm});
        current_sum += norm;
    }

    // 简单修正误差，确保总和严格等于 TABLE_SIZE
    if (current_sum != TABLE_SIZE) {
        int diff = TABLE_SIZE - current_sum;
        // 把误差加到最高频的符号上 (简化处理)
        auto max_it = max_element(stats.begin(), stats.end(), [](const SymbolStat& a, const SymbolStat& b){
            return a.norm_freq < b.norm_freq;
        });
        max_it->norm_freq += diff;
    }

    return stats;
}

// 2. 构建状态转换表 (Spread Symbols)
// 将符号分散放置到大小为 TABLE_SIZE 的状态数组中
// 核心思想：步长 (Step) 选择必须与 TABLE_SIZE 互质，保证遍历所有位置
vector<uint8_t> buildFSETable(const vector<SymbolStat>& stats) {
    vector<uint8_t> fse_table(TABLE_SIZE, 0);
    // ZSTD 的经典 Spread 步长算法：(TABLE_SIZE >> 1) + (TABLE_SIZE >> 3) + 3
    int step = (TABLE_SIZE >> 1) + (TABLE_SIZE >> 3) + 3; 
    int position = 0;

    for (const auto& stat : stats) {
        for (int i = 0; i < stat.norm_freq; ++i) {
            fse_table[position] = stat.symbol;
            position = (position + step) % TABLE_SIZE;
            
            // 如果该位置已被占用，线性探测找下一个空位 (实际算法步长互质时不会冲突，此处为防御性编程)
            while(fse_table[position] != 0 && fse_table[position] != stat.symbol) {
                position = (position + 1) % TABLE_SIZE;
            }
        }
    }
    return fse_table;
}

int main() {
    cout << "=== FSE (tANS) Encoder Simulation ===" << endl;
    
    // 模拟一段数据：假设是在 ZSTD 宏观 4KB 压缩中的一部分，存在偏斜的字节分布
    // 比如 65 ('A') 出现极多，66 ('B') 其次，67 ('C') 最少
    vector<uint8_t> data;
    for(int i=0; i<60; i++) data.push_back(65); // 60个 'A'
    for(int i=0; i<30; i++) data.push_back(66); // 30个 'B'
    for(int i=0; i<10; i++) data.push_back(67); // 10个 'C'

    cout << "1. Original Data Size: " << data.size() << " bytes" << endl;

    // 步骤1: 计算规范化频率
    vector<SymbolStat> stats = normalizeFrequencies(data);
    cout << "\n2. Normalized Frequencies (Target Table Size = " << TABLE_SIZE << "):" << endl;
    for (const auto& s : stats) {
        cout << "   Symbol '" << (char)s.symbol << "' (ASCII " << (int)s.symbol << "): " 
             << "Count=" << s.count << ", NormFreq=" << s.norm_freq << endl;
    }

    // 步骤2: 构建散布状态表
    vector<uint8_t> fse_table = buildFSETable(stats);
    cout << "\n3. Built FSE State Table (Spread Symbols):" << endl;
    for (int i = 0; i < TABLE_SIZE; ++i) {
        cout << (char)fse_table[i] << " ";
        if ((i+1) % 16 == 0) cout << endl;
    }
    
    cout << "\n[Note]: FSE encoding uses this state table to transition between states" << endl;
    cout << "        and emits fractional bits. This is why ZSTD-Lite achieves such" << endl;
    cout << "        high compression ratio on 4KB pages in our architecture." << endl;

    return 0;
}
