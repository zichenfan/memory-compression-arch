"""
总结生成模块 - 生成论文总结和飞书文档内容
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Tuple
from .arxiv_client import Paper

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """总结生成器"""
    
    def __init__(self, config: Dict):
        """初始化总结生成器"""
        self.config = config
        self.feishu_template = config.get('feishu', {}).get('template', {})
        
        logger.info("summary_generator_initialized")
    
    def generate_summary(self, paper: Paper) -> Paper:
        """
        为单篇论文生成总结
        
        Args:
            paper: 论文对象
            
        Returns:
            更新了summary属性的论文对象
        """
        try:
            # 提取关键信息
            key_points = self._extract_key_points(paper.abstract)
            summary = self._generate_concise_summary(paper, key_points)
            
            # 更新论文对象
            paper.summary = summary
            paper.tags.extend(self._extract_tags(paper))
            
            logger.debug("summary_generated", 
                       paper_id=paper.arxiv_id,
                       summary_length=len(summary))
            
            return paper
            
        except Exception as e:
            logger.error("failed_to_generate_summary", 
                       paper_id=paper.arxiv_id,
                       error=str(e))
            # 返回基础信息
            paper.summary = f"标题: {paper.title}\n作者: {', '.join(paper.authors[:3])}"
            return paper
    
    def _extract_key_points(self, abstract: str, max_points: int = 5) -> List[str]:
        """从摘要中提取关键点"""
        if not abstract:
            return ["摘要不可用"]
        
        # 简化版本：按句子分割并选择重要句子
        sentences = abstract.split('. ')
        
        # 过滤空句子
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 选择包含关键词的句子
        key_sentences = []
        important_keywords = ['propose', 'introduce', 'present', 'achieve', 'improve', 
                             'novel', 'new', 'efficient', 'scalable', 'optimized']
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in important_keywords):
                key_sentences.append(sentence)
        
        # 如果没找到关键词句子，取前几个句子
        if not key_sentences and sentences:
            key_sentences = sentences[:min(3, len(sentences))]
        
        # 限制数量并清理
        key_points = []
        for sentence in key_sentences[:max_points]:
            # 清理句子
            sentence = sentence.strip()
            if sentence and not sentence.endswith('.'):
                sentence += '.'
            key_points.append(sentence)
        
        return key_points if key_points else ["关键信息提取失败"]
    
    def _generate_concise_summary(self, paper: Paper, key_points: List[str]) -> str:
        """生成简洁的论文总结"""
        # 限制作者显示数量
        authors_display = ', '.join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors_display += f" 等{len(paper.authors)}位作者"
        
        # 生成总结
        summary_parts = []
        
        # 标题和作者
        summary_parts.append(f"**{paper.title}**")
        summary_parts.append(f"*作者: {authors_display}*")
        summary_parts.append("")
        
        # 关键点
        if key_points:
            summary_parts.append("**关键贡献:**")
            for i, point in enumerate(key_points, 1):
                summary_parts.append(f"{i}. {point}")
            summary_parts.append("")
        
        # 分类和标签
        if paper.categories:
            summary_parts.append(f"**分类:** {', '.join(paper.categories[:3])}")
        
        if paper.tags:
            summary_parts.append(f"**标签:** {', '.join(paper.tags)}")
        
        summary_parts.append("")
        summary_parts.append(f"**原文链接:** {paper.pdf_url}")
        
        return '\n'.join(summary_parts)
    
    def _extract_tags(self, paper: Paper) -> List[str]:
        """从论文中提取标签"""
        tags = []
        text = f"{paper.title} {paper.abstract}".lower()
        
        # 技术标签
        if any(kw in text for kw in ['quantization', 'low-precision', 'mixed-precision']):
            tags.append('量化')
        
        if any(kw in text for kw in ['sparsity', 'sparse', 'pruning']):
            tags.append('稀疏')
        
        if any(kw in text for kw in ['llm', 'large language model', 'transformer']):
            tags.append('LLM')
        
        if any(kw in text for kw in ['pim', 'processing-in-memory', 'in-memory computing']):
            tags.append('PIM')
        
        if any(kw in text for kw in ['accelerator', 'hardware architecture']):
            tags.append('硬件加速')
        
        if any(kw in text for kw in ['edge', 'mobile', 'embedded']):
            tags.append('边缘计算')
        
        # 质量标签
        if paper.quality_score >= 0.8:
            tags.append('高质量')
        elif paper.quality_score >= 0.6:
            tags.append('中等质量')
        
        return tags
    
    def generate_document(self, papers: List[Paper], target_date: date) -> str:
        """
        生成完整的飞书文档内容
        
        Args:
            papers: 论文列表
            target_date: 目标日期
            
        Returns:
            Markdown格式的文档内容
        """
        try:
            # 按分类分组
            from .paper_filter import PaperFilter
            filter_config = self.config.get('filter', {})
            paper_filter = PaperFilter(filter_config)
            categories = paper_filter.categorize_papers(papers)
            
            # 生成文档各部分
            document_parts = []
            
            # 1. 标题
            title = self.feishu_template.get('title', 'AI硬件加速论文日报 - {date}').format(
                date=target_date.strftime('%Y-%m-%d')
            )
            document_parts.append(f"# {title}")
            document_parts.append("")
            
            # 2. 今日概览
            document_parts.append("## 📊 今日概览")
            document_parts.append("")
            
            overview_stats = self._generate_overview_stats(papers, categories)
            document_parts.append(overview_stats)
            document_parts.append("")
            
            # 3. 今日精选（质量最高的3篇）
            if papers:
                document_parts.append("## 🏆 今日精选")
                document_parts.append("")
                
                # 按质量排序
                sorted_papers = sorted(papers, key=lambda p: p.quality_score, reverse=True)
                for i, paper in enumerate(sorted_papers[:3]):
                    paper_summary = self.generate_summary(paper)
                    document_parts.append(f"### {i+1}. {paper.title}")
                    document_parts.append("")
                    document_parts.append(paper_summary.summary)
                    document_parts.append("")
            
            # 4. 分类汇总
            document_parts.append("## 📁 分类汇总")
            document_parts.append("")
            
            for category_name, category_papers in categories.items():
                if category_papers:
                    # 翻译分类名称
                    category_display = {
                        'quantization': '量化相关',
                        'sparsity': '稀疏相关',
                        'llm_hardware': 'LLM硬件',
                        'pim': '3D PIM',
                        'other': '其他'
                    }.get(category_name, category_name)
                    
                    document_parts.append(f"### {category_display} ({len(category_papers)}篇)")
                    document_parts.append("")
                    
                    for paper in category_papers[:5]:  # 每个分类最多显示5篇
                        document_parts.append(f"- **{paper.title}**")
                        document_parts.append(f"  - 作者: {', '.join(paper.authors[:2])}")
                        document_parts.append(f"  - 质量分数: {paper.quality_score:.2f}")
                        document_parts.append(f"  - [原文链接]({paper.pdf_url})")
                        document_parts.append("")
            
            # 5. 趋势分析（如果有历史数据）
            document_parts.append("## 📈 趋势分析")
            document_parts.append("")
            document_parts.append("今日AI硬件加速领域的研究热点集中在：")
            
            # 分析热门关键词
            keyword_counts = {}
            for paper in papers:
                for tag in paper.tags:
                    keyword_counts[tag] = keyword_counts.get(tag, 0) + 1
            
            if keyword_counts:
                sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
                for keyword, count in sorted_keywords[:5]:
                    document_parts.append(f"- **{keyword}**: {count}篇论文")
            
            document_parts.append("")
            
            # 6. 脚注
            document_parts.append("---")
            document_parts.append("")
            document_parts.append("**数据来源**: Arxiv")
            document_parts.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            document_parts.append("**生成工具**: Arxiv AI Hardware Daily Digest")
            document_parts.append("")
            document_parts.append("*本日报由自动化系统生成，仅供参考*")
            
            # 合并所有部分
            document_content = '\n'.join(document_parts)
            
            logger.info("document_generated", 
                       date=target_date.isoformat(),
                       total_papers=len(papers),
                       document_length=len(document_content))
            
            return document_content
            
        except Exception as e:
            logger.error("failed_to_generate_document", 
                       date=target_date.isoformat(),
                       error=str(e))
            
            # 返回错误信息文档
            return f"""# AI硬件加速论文日报 - {target_date}

## ❌ 生成失败

抱歉，今日的论文日报生成失败。

**错误信息**: {str(e)}

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

请检查系统日志或联系管理员。"""
    
    def _generate_overview_stats(self, papers: List[Paper], categories: Dict[str, List[Paper]]) -> str:
        """生成概览统计信息"""
        if not papers:
            return "今日未找到相关论文。"
        
        total_papers = len(papers)
        avg_quality = sum(p.quality_score for p in papers) / total_papers if papers else 0
        
        # 各分类数量
        category_counts = {}
        for category_name, category_papers in categories.items():
            if category_papers:
                category_display = {
                    'quantization': '量化',
                    'sparsity': '稀疏',
                    'llm_hardware': 'LLM硬件',
                    'pim': '3D PIM',
                    'other': '其他'
                }.get(category_name, category_name)
                category_counts[category_display] = len(category_papers)
        
        # 构建统计文本
        stats_parts = []
        stats_parts.append(f"今日共筛选出 **{total_papers}** 篇高质量论文，平均质量分数 **{avg_quality:.2f}**。")
        stats_parts.append("")
        stats_parts.append("**分类统计**:")
        
        for category, count in category_counts.items():
            stats_parts.append(f"- {category}: {count}篇")
        
        # 质量分布
        quality_distribution = {
            '高质量 (≥0.8)': len([p for p in papers if p.quality_score >= 0.8]),
            '中等质量 (0.6-0.8)': len([p for p in papers if 0.6 <= p.quality_score < 0.8]),
            '基础质量 (<0.6)': len([p for p in papers if p.quality_score < 0.6])
        }
        
        stats_parts.append("")
        stats_parts.append("**质量分布**:")
        for quality_level, count in quality_distribution.items():
            if count > 0:
                stats_parts.append(f"- {quality_level}: {count}篇")
        
        return '\n'.join(stats_parts)
    
    def generate_document_for_feishu(self, papers: List[Paper], target_date: date) -> Dict:
        """
        生成飞书文档格式的内容
        
        Args:
            papers: 论文列表
            target_date: 目标日期
            
        Returns:
            飞书文档格式的字典
        """
        markdown_content = self.generate_document(papers, target_date)
        
        # 转换为飞书文档格式
        # 注意：这是一个简化版本，实际需要根据飞书API格式调整
        return {
            "title": f"AI硬件加速论文日报 - {target_date.strftime('%Y-%m-%d')}",
            "content": markdown_content,
            "format": "markdown"
        }


# 测试函数
if __name__ == "__main__":
    # 测试配置
    config = {
        'feishu': {
            'template': {
                'title': 'AI硬件加速论文日报 - {date}'
            }
        },
        'filter': {}
    }
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建测试论文
    from datetime import datetime, timedelta
    from .arxiv_client import Paper
    
    test_papers = [
        Paper(
            arxiv_id='2401.12345',
            title='Efficient Quantization for Large Language Models',
            authors=['John Smith (MIT)', 'Jane Doe (Google)'],
            abstract='We propose a novel quantization method for LLMs. Our approach achieves 4-bit precision with minimal accuracy loss. The method is efficient and scalable.',
            categories=['cs.AR', 'cs.AI'],
            published=datetime.now() - timedelta(days=1),
            updated=datetime.now() - timedelta(days=1),
            pdf_url='https://arxiv.org/pdf/2401.12345.pdf',
            primary_category='cs.AR',
            quality_score=0.85
        ),
        Paper(
            arxiv_id='2401.67890',
            title='3D PIM Architecture for Sparse Neural Networks',
            authors=['Bob Johnson (Stanford)'],
            abstract='This paper presents a new 3D PIM architecture optimized for sparse neural networks. The design improves energy efficiency by 40%.',
            categories=['cs.AR'],
            published=datetime.now() - timedelta(days=2),
            updated=datetime.now() - timedelta(days=2),
            pdf_url='https://arxiv.org/pdf/2401.67890.pdf',
            primary_category='cs.AR',
            quality_score=0.75
        )
    ]
    
    print("测试总结生成器...")
    generator = SummaryGenerator(config)
    
    # 测试单篇论文总结
    print("\n1. 单篇论文总结:")
    for i, paper in enumerate(test_papers):
        summarized = generator.generate_summary(paper)
        print(f"\n论文 {i+1}:")
        print(summarized.summary[:200] + "...")
    
    # 测试完整文档生成
    print("\n2. 完整文档生成:")
    document = generator.generate_document(test_papers, date.today())
    
    # 显示文档前几行
    lines = document.split('\n')[:20]
    print("\n文档预览 (前20行):")
    for line in lines:
        print(line)
    
    print(f"\n文档总长度: {len(document)} 字符")