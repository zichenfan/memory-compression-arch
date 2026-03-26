# Arxiv AI Hardware Daily Digest

自动化抓取Arxiv上AI硬件加速相关论文，生成每日总结文档到飞书。

## 🎯 项目目标
- **自动化**: 每日自动抓取Arxiv最新论文
- **智能化**: 筛选高质量AI硬件加速论文
- **结构化**: 生成易读的飞书文档
- **持续化**: 建立长期的知识积累系统

## 📋 功能特性
### 数据抓取
- 每日抓取Arxiv上AI硬件相关论文
- 支持关键词过滤：量化、稀疏、LLM硬件、3D PIM等
- 自动去重和更新检测

### 质量筛选
- 基于引用量、下载量、作者声誉的筛选
- 顶会预印本优先
- 知名研究机构论文优先

### 文档生成
- 生成结构化的飞书文档
- 包含论文摘要、关键点、原文链接
- 支持分类标签和搜索

### 自动化调度
- GitHub Actions每日定时执行
- 错误处理和重试机制
- 执行结果通知

## 🏗️ 系统架构
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Arxiv API     │───▶│   筛选模块      │───▶│   分析模块      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                            │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   飞书文档      │◀───│  文档生成模块   │◀───│   总结模块      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 项目结构
```
arxiv-ai-hardware-daily-digest/
├── src/                    # 源代码
│   ├── arxiv_client.py    # Arxiv API客户端
│   ├── paper_filter.py    # 论文筛选逻辑
│   ├── summary_generator.py # 总结生成
│   ├── feishu_client.py   # 飞书API客户端
│   └── main.py           # 主程序
├── config/               # 配置文件
│   ├── keywords.yaml    # 关键词配置
│   └── settings.yaml    # 系统设置
├── tests/               # 测试文件
├── docs/               # 文档
└── requirements.txt    # Python依赖
```

## 🚀 快速开始
### 环境准备
```bash
# 克隆项目
git clone https://github.com/zichenfan/openclaw-jason-workspace.git
cd openclaw-jason-workspace/projects/arxiv-ai-hardware-daily-digest

# 安装依赖
pip install -r requirements.txt
```

### 配置设置
1. 复制配置文件模板：
   ```bash
   cp config/settings.example.yaml config/settings.yaml
   ```

2. 编辑配置文件：
   ```yaml
   arxiv:
     categories: ['cs.AR', 'cs.AI', 'cs.LG']
     max_results: 50
   
   feishu:
     app_id: 'your_app_id'
     app_secret: 'your_app_secret'
   
   schedule:
     cron: '0 8 * * *'  # 每天8点执行
   ```

### 运行测试
```bash
# 运行单元测试
pytest tests/

# 手动执行一次
python src/main.py --test
```

## 🔧 技术栈
- **Python 3.10+**: 主要开发语言
- **Arxiv API**: 论文数据源
- **飞书开放平台**: 文档生成和存储
- **GitHub Actions**: 自动化调度
- **Pytest**: 单元测试框架
- **YAML**: 配置文件格式

## 📊 数据流程
### 每日执行流程
1. **数据抓取** (08:00): 从Arxiv获取最新论文
2. **初步筛选**: 基于关键词和类别过滤
3. **质量评估**: 计算论文质量分数
4. **总结生成**: 提取关键信息生成摘要
5. **文档更新**: 更新飞书文档
6. **结果通知**: 发送执行结果通知

### 论文筛选算法
1. **关键词匹配**: 标题和摘要包含目标关键词
2. **质量评分**: 基于引用、作者、机构等
3. **去重处理**: 避免重复收录
4. **分类标签**: 自动添加相关标签

## 📈 输出格式
### 飞书文档结构
```
# AI硬件加速论文日报 - YYYY-MM-DD

## 📊 今日概览
- 抓取论文: XX篇
- 筛选通过: XX篇
- 重点推荐: XX篇

## 🏆 今日精选
### [论文标题]
- **作者**: 作者列表
- **摘要**: 论文摘要（精简版）
- **关键点**: 
  - 点1
  - 点2
- **原文链接**: [Arxiv链接]
- **标签**: #量化 #硬件加速

## 📁 分类汇总
### 量化相关 (X篇)
- [论文1标题](链接)
- [论文2标题](链接)

### 稀疏相关 (X篇)
- [论文1标题](链接)
- [论文2标题](链接)
```

## 🤝 贡献指南
1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 许可证
本项目采用 MIT 许可证 - 查看 [LICENSE](../LICENSE) 文件了解详情。

## 🆘 支持
- **问题反馈**: GitHub Issues
- **功能建议**: 通过Issues提出
- **技术咨询**: 联系项目维护者

---
**项目状态**: 开发中  
**最新更新**: 2026年3月16日  
**维护者**: Jason + OpenClaw AI助手  
**项目类型**: 自动化信息聚合工具