# Arxiv AI硬件加速论文日报系统 - 快速部署指南

## 🚀 5分钟快速部署

### 1. 环境准备
```bash
# 克隆仓库
git clone https://github.com/zichenfan/openclaw-jason-workspace.git
cd openclaw-jason-workspace/projects/arxiv-ai-hardware-daily-digest

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置飞书应用
1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 `app_id` 和 `app_secret`
4. 开通权限：`获取访问凭证`、`以应用身份读取通讯录`

### 3. 创建配置文件
```bash
cp config/settings.example.yaml config/settings.yaml
```

编辑 `config/settings.yaml`：
```yaml
feishu:
  app_id: "你的app_id"
  app_secret: "你的app_secret"
  document_folder: "AI论文日报"
```

### 4. 测试运行
```bash
# 测试模式运行
python -m src.main --dry-run

# 生产模式运行
python -m src.main
```

## ⚙️ GitHub Actions自动化部署

### 1. 配置GitHub Secrets
在GitHub仓库设置中添加：
- `FEISHU_APP_ID`: 你的飞书app_id
- `FEISHU_APP_SECRET`: 你的飞书app_secret

### 2. 工作流已配置
系统已包含 `.github/workflows/daily-digest.yml`，每天UTC 0点（北京时间8点）自动执行。

### 3. 手动触发
在GitHub仓库的Actions标签页，可以手动触发工作流。

## 📊 监控和日志

### 日志位置
- 本地运行：`logs/arxiv_digest.log`
- GitHub Actions：工作流日志和Artifacts

### 关键指标监控
1. **执行成功率**: 每日任务是否成功
2. **论文数量**: 每日筛选的论文数量
3. **文档创建**: 飞书文档是否成功创建
4. **API健康**: Arxiv和飞书API可用性

## 🔧 故障排除

### 常见问题
1. **飞书认证失败**
   - 检查app_id和app_secret是否正确
   - 确认应用权限已开通
   - 检查网络连接

2. **Arxiv API无响应**
   - 检查网络连接
   - 确认Arxiv服务状态
   - 调整查询参数（减少max_results）

3. **无论文输出**
   - 调整质量阈值（quality_threshold）
   - 扩展关键词列表
   - 增加查询天数（days_back）

### 调试模式
```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
python -m src.main --dry-run

# 查看日志
tail -f logs/arxiv_digest.log
```

## 📈 性能优化

### 建议配置
```yaml
arxiv:
  max_results: 50      # 平衡性能和覆盖范围
  days_back: 2         # 关注最新论文

filter:
  quality_threshold: 0.7  # 质量门槛
  max_papers_per_day: 10  # 输出限制
```

### 资源使用
- **内存**: < 100MB
- **执行时间**: 1-3分钟
- **网络请求**: 2-5个API调用

## 🔄 维护和更新

### 定期检查
1. **依赖更新**: 每月检查requirements.txt
2. **配置优化**: 根据使用反馈调整参数
3. **日志清理**: 定期清理日志文件

### 备份策略
- 配置文件备份
- 重要日志归档
- GitHub Actions Artifacts保留7天

## 📞 支持

### 问题反馈
1. 查看日志文件获取详细错误信息
2. 检查GitHub Issues是否有类似问题
3. 联系开发团队

### 紧急恢复
```bash
# 停止当前任务
Ctrl+C

# 清理临时文件
rm -rf __pycache__ logs/*.log

# 重新运行
python -m src.main --dry-run
```

## 🎯 生产部署检查清单

- [ ] 飞书应用配置完成
- [ ] 配置文件正确设置
- [ ] 依赖包安装完成
- [ ] 测试运行通过
- [ ] GitHub Secrets配置
- [ ] 监控设置完成
- [ ] 备份策略就绪
- [ ] 团队培训完成

---

**部署完成时间**: 约15分钟  
**维护需求**: 低（每月检查一次）  
**可靠性**: 高（自动化错误处理）  
**扩展性**: 良好（模块化设计）