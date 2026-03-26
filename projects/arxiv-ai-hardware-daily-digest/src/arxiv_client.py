"""
Arxiv API客户端 - 抓取AI硬件加速相关论文
"""

import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from dataclasses import dataclass, field
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """论文数据模型"""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    published: datetime
    updated: datetime
    pdf_url: str
    primary_category: str
    
    # 计算属性
    quality_score: float = 0.0
    keywords: List[str] = field(default_factory=list)
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract[:500] + "..." if len(self.abstract) > 500 else self.abstract,
            "categories": self.categories,
            "published": self.published.isoformat(),
            "updated": self.updated.isoformat(),
            "pdf_url": self.pdf_url,
            "primary_category": self.primary_category,
            "quality_score": self.quality_score,
            "keywords": self.keywords,
            "tags": self.tags
        }


class ArxivClient:
    """Arxiv API客户端"""
    
    def __init__(self, config: Dict):
        """初始化Arxiv客户端"""
        self.base_url = config.get('base_url', 'http://export.arxiv.org/api/query')
        self.categories = config.get('categories', ['cs.AR', 'cs.AI', 'cs.LG'])
        self.keywords = config.get('keywords', {})
        self.max_results = config.get('max_results', 100)
        self.days_back = config.get('days_back', 7)
        
        # 合并所有关键词
        self.all_keywords = []
        for category, words in self.keywords.items():
            self.all_keywords.extend(words)
        
        logger.info("arxiv_client_initialized", 
                   categories=self.categories,
                   keyword_count=len(self.all_keywords))
    
    def fetch_recent_papers(self, days: int = None, max_results: int = None) -> List[Paper]:
        """
        获取最近N天的论文
        
        Args:
            days: 查询最近多少天的论文，默认使用配置
            max_results: 最大结果数，默认使用配置
            
        Returns:
            论文列表
        """
        if days is None:
            days = self.days_back
        if max_results is None:
            max_results = self.max_results
        
        # 计算查询日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.info("fetching_recent_papers", 
                   start_date=start_date.date().isoformat(),
                   end_date=end_date.date().isoformat(),
                   max_results=max_results)
        
        papers = []
        
        # 按类别分批查询，避免查询过长
        for category in self.categories:
            try:
                category_papers = self._fetch_papers_by_category(
                    category, start_date, end_date, max_results // len(self.categories)
                )
                papers.extend(category_papers)
                logger.info("category_papers_fetched", 
                          category=category, 
                          count=len(category_papers))
                
                # 避免请求频率过高
                time.sleep(1)
                
            except Exception as e:
                logger.error("failed_to_fetch_category", 
                           category=category, 
                           error=str(e))
        
        # 去重（按arxiv_id）
        unique_papers = {}
        for paper in papers:
            if paper.arxiv_id not in unique_papers:
                unique_papers[paper.arxiv_id] = paper
        
        papers = list(unique_papers.values())
        logger.info("papers_fetched_total", 
                   total=len(papers),
                   unique=len(unique_papers))
        
        return papers
    
    def _fetch_papers_by_category(self, category: str, start_date: datetime, 
                                 end_date: datetime, max_results: int) -> List[Paper]:
        """按类别查询论文"""
        # 构建查询参数
        query_parts = []
        
        # 类别过滤
        query_parts.append(f"cat:{category}")
        
        # 日期范围过滤
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        query_parts.append(f"submittedDate:[{start_str} TO {end_str}]")
        
        # 关键词过滤（可选）
        if self.all_keywords:
            # 使用OR连接关键词
            keyword_query = " OR ".join([f'all:"{kw}"' for kw in self.all_keywords[:5]])  # 限制前5个关键词
            query_parts.append(f"({keyword_query})")
        
        query = " AND ".join(query_parts)
        
        # 构建请求URL
        params = {
            'search_query': query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        
        logger.debug("arxiv_query", category=category, query=query)
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            papers = self._parse_response(response.content)
            return papers
            
        except requests.exceptions.RequestException as e:
            logger.error("arxiv_api_request_failed", 
                       category=category,
                       error=str(e))
            return []
    
    def _parse_response(self, xml_content: bytes) -> List[Paper]:
        """解析Arxiv API返回的XML数据"""
        try:
            root = ET.fromstring(xml_content)
            
            # Arxiv使用Atom格式，命名空间
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            papers = []
            for entry in root.findall('atom:entry', ns):
                try:
                    paper = self._parse_entry(entry, ns)
                    if paper:
                        papers.append(paper)
                except Exception as e:
                    logger.warning("failed_to_parse_entry", error=str(e))
            
            return papers
            
        except ET.ParseError as e:
            logger.error("failed_to_parse_xml", error=str(e))
            return []
    
    def _parse_entry(self, entry, ns) -> Optional[Paper]:
        """解析单个entry元素"""
        try:
            # 提取arxiv_id
            arxiv_id_elem = entry.find('atom:id', ns)
            if arxiv_id_elem is None:
                return None
            
            arxiv_id = arxiv_id_elem.text
            if not arxiv_id:
                return None
            
            # 提取标题
            title_elem = entry.find('atom:title', ns)
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else "No Title"
            
            # 提取作者
            authors = []
            author_elems = entry.findall('atom:author/atom:name', ns)
            for author_elem in author_elems:
                if author_elem.text:
                    authors.append(author_elem.text.strip())
            
            # 提取摘要
            summary_elem = entry.find('atom:summary', ns)
            abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ""
            
            # 提取分类
            categories = []
            primary_category = ""
            category_elems = entry.findall('atom:category', ns)
            for category_elem in category_elems:
                term = category_elem.get('term')
                if term:
                    categories.append(term)
                    if category_elem.get('scheme') == 'http://arxiv.org/schemas/atom':
                        primary_category = term
            
            # 提取发布时间
            published_elem = entry.find('atom:published', ns)
            published_str = published_elem.text if published_elem is not None else None
            
            updated_elem = entry.find('atom:updated', ns)
            updated_str = updated_elem.text if updated_elem is not None else published_str
            
            # 解析时间
            try:
                published = datetime.fromisoformat(published_str.replace('Z', '+00:00')) if published_str else datetime.now()
                updated = datetime.fromisoformat(updated_str.replace('Z', '+00:00')) if updated_str else published
            except (ValueError, AttributeError):
                published = updated = datetime.now()
            
            # 构建PDF链接
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id.split('/')[-1]}.pdf"
            
            # 创建Paper对象
            paper = Paper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                categories=categories,
                published=published,
                updated=updated,
                pdf_url=pdf_url,
                primary_category=primary_category
            )
            
            return paper
            
        except Exception as e:
            logger.error("entry_parsing_error", error=str(e))
            return None
    
    def filter_by_keywords(self, papers: List[Paper], keywords: List[str] = None) -> List[Paper]:
        """
        基于关键词筛选论文
        
        Args:
            papers: 论文列表
            keywords: 关键词列表，默认使用配置的关键词
            
        Returns:
            筛选后的论文列表
        """
        if keywords is None:
            keywords = self.all_keywords
        
        if not keywords:
            return papers
        
        filtered_papers = []
        
        for paper in papers:
            # 检查标题和摘要是否包含关键词
            text_to_check = f"{paper.title} {paper.abstract}".lower()
            
            for keyword in keywords:
                if keyword.lower() in text_to_check:
                    paper.keywords.append(keyword)
                    filtered_papers.append(paper)
                    break  # 找到一个关键词就足够
        
        logger.info("papers_filtered_by_keywords", 
                   total=len(papers),
                   filtered=len(filtered_papers),
                   keywords=keywords[:5])  # 只记录前5个关键词
        
        return filtered_papers
    
    def get_paper_details(self, arxiv_id: str) -> Optional[Paper]:
        """
        获取单篇论文的详细信息
        
        Args:
            arxiv_id: Arxiv论文ID
            
        Returns:
            论文详细信息，如果获取失败则返回None
        """
        try:
            params = {
                'id_list': arxiv_id,
                'max_results': 1
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            papers = self._parse_response(response.content)
            return papers[0] if papers else None
            
        except Exception as e:
            logger.error("failed_to_get_paper_details", 
                       arxiv_id=arxiv_id,
                       error=str(e))
            return None


# 测试函数
if __name__ == "__main__":
    # 基本配置
    config = {
        'categories': ['cs.AR', 'cs.AI'],
        'keywords': {
            'hardware': ['quantization', 'sparsity', 'LLM hardware', 'AI accelerator'],
            'techniques': ['model compression', 'pruning']
        },
        'max_results': 10,
        'days_back': 3
    }
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 测试客户端
    client = ArxivClient(config)
    
    print("测试Arxiv客户端...")
    papers = client.fetch_recent_papers(days=3, max_results=5)
    
    print(f"\n获取到 {len(papers)} 篇论文:")
    for i, paper in enumerate(papers[:3]):  # 只显示前3篇
        print(f"\n{i+1}. {paper.title}")
        print(f"   作者: {', '.join(paper.authors[:3])}")
        print(f"   摘要: {paper.abstract[:200]}...")
        print(f"   链接: {paper.pdf_url}")
    
    # 测试关键词筛选
    if papers:
        filtered = client.filter_by_keywords(papers)
        print(f"\n关键词筛选后: {len(filtered)} 篇")