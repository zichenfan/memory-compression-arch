"""
论文筛选模块 - 基于质量指标筛选高质量论文
"""

import re
import logging
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from .arxiv_client import Paper

logger = logging.getLogger(__name__)


class PaperFilter:
    """论文筛选器"""
    
    def __init__(self, config: Dict):
        """初始化论文筛选器"""
        self.quality_threshold = config.get('quality_threshold', 0.7)
        self.min_papers_per_day = config.get('min_papers_per_day', 5)
        self.max_papers_per_day = config.get('max_papers_per_day', 15)
        
        # 评分权重配置
        self.scoring_weights = config.get('scoring_weights', {
            'keyword_match': 0.4,
            'author_reputation': 0.3,
            'recency': 0.2,
            'content_quality': 0.1
        })
        
        # 知名机构列表
        self.reputable_institutions = config.get('reputable_institutions', [
            'MIT', 'Stanford', 'UC Berkeley', 'CMU', 
            'Google', 'Microsoft', 'Meta', 'NVIDIA', 'Intel', 'AMD'
        ])
        
        # 知名会议列表
        self.top_conferences = config.get('top_conferences', [
            'ISCA', 'MICRO', 'HPCA', 'ASPLOS',
            'NeurIPS', 'ICML', 'ICLR', 'CVPR', 'ACL'
        ])
        
        logger.info("paper_filter_initialized", 
                   threshold=self.quality_threshold,
                   min_papers=self.min_papers_per_day,
                   max_papers=self.max_papers_per_day)
    
    def filter_papers(self, papers: List[Paper], 
                     min_papers: int = None, 
                     max_papers: int = None) -> List[Paper]:
        """
        筛选高质量论文
        
        Args:
            papers: 待筛选的论文列表
            min_papers: 最小论文数量，默认使用配置
            max_papers: 最大论文数量，默认使用配置
            
        Returns:
            筛选后的高质量论文列表
        """
        if min_papers is None:
            min_papers = self.min_papers_per_day
        if max_papers is None:
            max_papers = self.max_papers_per_day
        
        if not papers:
            logger.warning("no_papers_to_filter")
            return []
        
        logger.info("starting_paper_filtering", 
                   total_papers=len(papers),
                   min_required=min_papers,
                   max_allowed=max_papers)
        
        # 步骤1: 计算每篇论文的质量分数
        scored_papers = []
        for paper in papers:
            try:
                quality_score = self.calculate_quality_score(paper)
                paper.quality_score = quality_score
                scored_papers.append(paper)
                
                logger.debug("paper_scored", 
                           paper_id=paper.arxiv_id,
                           score=quality_score,
                           title=paper.title[:50])
                
            except Exception as e:
                logger.error("failed_to_score_paper", 
                           paper_id=paper.arxiv_id,
                           error=str(e))
        
        # 步骤2: 按质量分数排序
        scored_papers.sort(key=lambda p: p.quality_score, reverse=True)
        
        # 步骤3: 应用质量阈值
        filtered_papers = [
            paper for paper in scored_papers 
            if paper.quality_score >= self.quality_threshold
        ]
        
        # 步骤4: 确保论文数量在范围内
        if len(filtered_papers) < min_papers:
            # 如果高质量论文不足，放宽标准
            logger.warning("insufficient_high_quality_papers", 
                         high_quality=len(filtered_papers),
                         min_required=min_papers)
            
            # 取前min_papers篇，即使质量分数低于阈值
            filtered_papers = scored_papers[:min_papers]
        
        elif len(filtered_papers) > max_papers:
            # 如果高质量论文太多，只取前max_papers篇
            logger.info("too_many_high_quality_papers", 
                       high_quality=len(filtered_papers),
                       max_allowed=max_papers)
            filtered_papers = filtered_papers[:max_papers]
        
        # 步骤5: 记录筛选结果
        if filtered_papers:
            avg_score = sum(p.quality_score for p in filtered_papers) / len(filtered_papers)
            logger.info("paper_filtering_completed", 
                       total_scored=len(scored_papers),
                       filtered=len(filtered_papers),
                       avg_score=avg_score,
                       min_score=filtered_papers[-1].quality_score,
                       max_score=filtered_papers[0].quality_score)
        else:
            logger.warning("no_papers_passed_filtering")
        
        return filtered_papers
    
    def calculate_quality_score(self, paper: Paper) -> float:
        """
        计算论文质量分数
        
        Args:
            paper: 论文对象
            
        Returns:
            质量分数 (0-1)
        """
        scores = {}
        
        # 1. 关键词匹配分数
        scores['keyword_match'] = self._calculate_keyword_match_score(paper)
        
        # 2. 作者声誉分数
        scores['author_reputation'] = self._calculate_author_reputation_score(paper)
        
        # 3. 新鲜度分数
        scores['recency'] = self._calculate_recency_score(paper)
        
        # 4. 内容质量分数
        scores['content_quality'] = self._calculate_content_quality_score(paper)
        
        # 5. 会议/期刊分数（额外加分）
        scores['conference_bonus'] = self._calculate_conference_bonus(paper)
        
        # 计算加权总分
        total_score = 0.0
        weight_sum = 0.0
        
        for factor, weight in self.scoring_weights.items():
            if factor in scores:
                total_score += scores[factor] * weight
                weight_sum += weight
        
        # 添加会议加分（作为额外加分，不超过0.1）
        total_score += min(scores['conference_bonus'], 0.1)
        
        # 确保分数在0-1范围内
        total_score = max(0.0, min(1.0, total_score))
        
        # 记录详细分数（调试用）
        logger.debug("paper_score_details", 
                   paper_id=paper.arxiv_id,
                   scores=scores,
                   total_score=total_score)
        
        return total_score
    
    def _calculate_keyword_match_score(self, paper: Paper) -> float:
        """计算关键词匹配分数"""
        # 检查标题和摘要中的关键词密度
        text = f"{paper.title} {paper.abstract}".lower()
        
        # 定义硬件加速相关关键词
        hardware_keywords = [
            'quantization', 'sparsity', 'sparse', 'llm hardware',
            '3d pim', 'ai accelerator', 'neural processor',
            'in-memory computing', 'processing-in-memory',
            'hardware architecture', 'model compression',
            'pruning', 'knowledge distillation', 'efficient inference',
            'low-precision', 'mixed-precision', 'sparse attention',
            'transformer optimization', 'large language model',
            'llm inference', 'edge ai', 'mobile ai'
        ]
        
        # 计算匹配的关键词数量
        matched_keywords = 0
        for keyword in hardware_keywords:
            if keyword.lower() in text:
                matched_keywords += 1
        
        # 分数基于匹配的关键词比例
        max_keywords = min(len(hardware_keywords), 10)  # 最多考虑10个关键词
        score = min(matched_keywords / max_keywords, 1.0)
        
        return score
    
    def _calculate_author_reputation_score(self, paper: Paper) -> float:
        """计算作者声誉分数"""
        if not paper.authors:
            return 0.3  # 默认分数
        
        # 检查作者是否来自知名机构
        author_text = ' '.join(paper.authors).lower()
        
        institution_score = 0.0
        for institution in self.reputable_institutions:
            if institution.lower() in author_text:
                institution_score = 0.8  # 来自知名机构
                break
        
        # 检查作者数量（合作者多通常表示合作广泛）
        author_count_score = min(len(paper.authors) / 10, 0.5)  # 最多0.5分
        
        # 综合分数
        score = institution_score + author_count_score
        
        return min(score, 1.0)
    
    def _calculate_recency_score(self, paper: Paper) -> float:
        """计算新鲜度分数"""
        try:
            # 计算论文发布时间距离现在的天数
            now = datetime.now()
            days_old = (now - paper.published).days
            
            # 新鲜度分数：越新分数越高
            if days_old <= 1:
                return 1.0  # 24小时内
            elif days_old <= 3:
                return 0.8  # 3天内
            elif days_old <= 7:
                return 0.6  # 一周内
            elif days_old <= 30:
                return 0.4  # 一个月内
            else:
                return 0.2  # 超过一个月
            
        except Exception:
            return 0.5  # 默认分数
    
    def _calculate_content_quality_score(self, paper: Paper) -> float:
        """计算内容质量分数"""
        score = 0.5  # 基础分数
        
        # 1. 摘要长度（适中的摘要通常质量更高）
        abstract_length = len(paper.abstract)
        if 200 <= abstract_length <= 1000:
            score += 0.2
        elif abstract_length > 1000:
            score += 0.1
        
        # 2. 标题质量（包含关键信息的标题）
        title = paper.title.lower()
        if any(word in title for word in ['novel', 'new', 'efficient', 'scalable', 'optimized']):
            score += 0.1
        
        # 3. 分类数量（多分类可能表示跨学科）
        if len(paper.categories) > 1:
            score += 0.1
        
        # 4. 是否有PDF链接
        if paper.pdf_url and 'arxiv.org/pdf' in paper.pdf_url:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_conference_bonus(self, paper: Paper) -> float:
        """计算会议/期刊加分"""
        # 检查标题或摘要中是否包含知名会议名称
        text = f"{paper.title} {paper.abstract}".lower()
        
        for conference in self.top_conferences:
            if conference.lower() in text:
                return 0.2  # 顶会论文加分
        
        # 检查Arxiv分类（某些分类与顶会相关）
        top_conference_categories = ['cs.AR', 'cs.AI', 'cs.LG', 'cs.CV', 'cs.CL']
        if any(cat in paper.categories for cat in top_conference_categories):
            return 0.1  # 顶会相关分类加分
        
        return 0.0
    
    def categorize_papers(self, papers: List[Paper]) -> Dict[str, List[Paper]]:
        """
        将论文按主题分类
        
        Args:
            papers: 论文列表
            
        Returns:
            按主题分类的论文字典
        """
        categories = {
            'quantization': [],
            'sparsity': [],
            'llm_hardware': [],
            'pim': [],
            'other': []
        }
        
        for paper in papers:
            text = f"{paper.title} {paper.abstract}".lower()
            
            # 检查量化相关
            quantization_keywords = ['quantization', 'low-precision', 'mixed-precision', '8-bit', '4-bit']
            if any(kw in text for kw in quantization_keywords):
                categories['quantization'].append(paper)
                paper.tags.append('quantization')
                continue
            
            # 检查稀疏相关
            sparsity_keywords = ['sparsity', 'sparse', 'pruning', 'model compression']
            if any(kw in text for kw in sparsity_keywords):
                categories['sparsity'].append(paper)
                paper.tags.append('sparsity')
                continue
            
            # 检查LLM硬件相关
            llm_keywords = ['llm hardware', 'large language model', 'transformer', 'attention']
            if any(kw in text for kw in llm_keywords):
                categories['llm_hardware'].append(paper)
                paper.tags.append('llm_hardware')
                continue
            
            # 检查PIM相关
            pim_keywords = ['3d pim', 'processing-in-memory', 'in-memory computing', 'pim']
            if any(kw in text for kw in pim_keywords):
                categories['pim'].append(paper)
                paper.tags.append('pim')
                continue
            
            # 其他
            categories['other'].append(paper)
        
        # 记录分类结果
        for category, papers_in_category in categories.items():
            if papers_in_category:
                logger.info("papers_categorized", 
                          category=category,
                          count=len(papers_in_category))
        
        return categories


# 测试函数
if __name__ == "__main__":
    # 测试配置
    config = {
        'quality_threshold': 0.7,
        'min_papers_per_day': 3,
        'max_papers_per_day': 10,
        'scoring_weights': {
            'keyword_match': 0.4,
            'author_reputation': 0.3,
            'recency': 0.2,
            'content_quality': 0.1
        }
    }
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建测试论文
    from datetime import datetime, timedelta
    
    test_papers = []
    
    # 高质量论文
    test_papers.append(Paper(
        arxiv_id='2401.12345',
        title='Efficient Quantization for Large Language Models on Edge Devices',
        authors=['John Smith (MIT)', 'Jane Doe (Google)'],
        abstract='We propose a novel quantization method for LLMs that achieves 4-bit precision with minimal accuracy loss. Our method combines mixed-precision quantization with sparse attention mechanisms.',
        categories=['cs.AR', 'cs.AI'],
        published=datetime.now() - timedelta(days=1),
        updated=datetime.now() - timedelta(days=1),
        pdf_url='https://arxiv.org/pdf/2401.12345.pdf',
        primary_category='cs.AR'
    ))
    
    # 中等质量论文
    test_papers.append(Paper(
        arxiv_id='2401.67890',
        title='A Survey of 3D PIM Architectures for AI Workloads',
        authors=['Bob Johnson'],
        abstract='This paper surveys recent advances in 3D Processing-in-Memory architectures for AI acceleration.',
        categories=['cs.AR'],
        published=datetime.now() - timedelta(days=10),
        updated=datetime.now() - timedelta(days=10),
        pdf_url='https://arxiv.org/pdf/2401.67890.pdf',
        primary_category='cs.AR'
    ))
    
    # 低质量论文
    test_papers.append(Paper(
        arxiv_id='2401.11111',
        title='General Computer Architecture Paper',
        authors=['Unknown Author'],
        abstract='This is a general paper about computer architecture.',
        categories=['cs.AR'],
        published=datetime.now() - timedelta(days=100),
        updated=datetime.now() - timedelta(days=100),
        pdf_url='https://arxiv.org/pdf/2401.11111.pdf',
        primary_category='cs.AR'
    ))
    
    print("测试论文筛选器...")
    filter = PaperFilter(config)
    
    # 计算单篇论文分数
    print("\n单篇论文质量分数:")
    for i, paper in enumerate(test_papers):
        score = filter.calculate_quality_score(paper)
        print(f"{i+1}. {paper.title[:50]}...")
        print(f"   分数: {score:.3f}")
    
    # 测试批量筛选
    print(f"\n批量筛选测试 (共{len(test_papers)}篇论文):")
    filtered = filter.filter_papers(test_papers, min_papers=2, max_papers=5)
    
    print(f"\n筛选结果: {len(filtered)}篇通过")
    for i, paper in enumerate(filtered):
        print(f"{i+1}. {paper.title[:50]}... (分数: {paper.quality_score:.3f})")
    
    # 测试分类
    print("\n论文分类测试:")
    categories = filter.categorize_papers(test_papers)
    for category, papers_in_category in categories.items():
        if papers_in_category:
            print(f"{category}: {len(papers_in_category)}篇")