#!/usr/bin/env python3
"""
Arxiv AI Hardware Daily Digest - 主程序入口
自动化抓取Arxiv上AI硬件加速相关论文，生成每日总结文档到飞书
"""

import argparse
import logging
import sys
from datetime import datetime, date
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.arxiv_client import ArxivClient
from src.paper_filter import PaperFilter
from src.summary_generator import SummaryGenerator
from src.feishu_client import FeishuClient
from src.config_loader import ConfigLoader
from src.logger import setup_logging


class ArxivAIDailyDigest:
    """Arxiv AI硬件日报主程序"""
    
    def __init__(self, config_path=None, debug=False):
        """初始化程序"""
        self.debug = debug
        self.logger = setup_logging(__name__, debug=debug)
        
        # 加载配置
        self.config = ConfigLoader.load(config_path)
        self.logger.info("config_loaded", config_path=config_path)
        
        # 初始化组件
        self.arxiv_client = ArxivClient(self.config['arxiv'])
        self.paper_filter = PaperFilter(self.config['filter'])
        self.summary_generator = SummaryGenerator(self.config)
        
        # 只有在非调试模式下才初始化飞书客户端
        if not debug and not self.config.get('debug', {}).get('dry_run', False):
            self.feishu_client = FeishuClient(self.config['feishu'])
        else:
            self.feishu_client = None
            self.logger.info("running_in_debug_mode", dry_run=True)
    
    def run(self, target_date=None):
        """执行每日摘要生成流程"""
        try:
            # 确定目标日期
            if target_date:
                target_date = date.fromisoformat(target_date)
            else:
                target_date = date.today()
            
            self.logger.info("daily_digest_started", date=target_date.isoformat())
            
            # 步骤1: 抓取Arxiv论文
            self.logger.info("step_1_fetching_papers")
            papers = self.arxiv_client.fetch_recent_papers(
                days=self.config['arxiv']['days_back'],
                max_results=self.config['arxiv']['max_results']
            )
            self.logger.info("papers_fetched", count=len(papers))
            
            if not papers:
                self.logger.warning("no_papers_found")
                return {"status": "warning", "message": "未找到相关论文"}
            
            # 步骤2: 筛选高质量论文
            self.logger.info("step_2_filtering_papers")
            filtered_papers = self.paper_filter.filter_papers(
                papers,
                min_papers=self.config['filter']['min_papers_per_day'],
                max_papers=self.config['filter']['max_papers_per_day']
            )
            self.logger.info("papers_filtered", 
                           total=len(papers), 
                           filtered=len(filtered_papers))
            
            if len(filtered_papers) < self.config['filter']['min_papers_per_day']:
                self.logger.warning("insufficient_high_quality_papers", 
                                  count=len(filtered_papers),
                                  min_required=self.config['filter']['min_papers_per_day'])
            
            # 步骤3: 生成论文总结
            self.logger.info("step_3_generating_summaries")
            summarized_papers = []
            for paper in filtered_papers:
                try:
                    summarized = self.summary_generator.generate_summary(paper)
                    summarized_papers.append(summarized)
                except Exception as e:
                    self.logger.error("summary_generation_failed", 
                                    paper_id=paper.arxiv_id, 
                                    error=str(e))
            
            # 步骤4: 生成飞书文档
            if self.feishu_client and summarized_papers:
                self.logger.info("step_4_creating_feishu_document")
                
                # 生成文档内容
                document_content = self.summary_generator.generate_document(
                    summarized_papers, 
                    target_date
                )
                
                # 创建飞书文档
                document_info = self.feishu_client.create_daily_digest(
                    title=self.config['feishu']['document_title'].format(date=target_date),
                    content=document_content,
                    folder=self.config['feishu']['document_folder']
                )
                
                self.logger.info("feishu_document_created", 
                               document_id=document_info.get('document_id'),
                               document_url=document_info.get('url'))
                
                # 发送成功通知
                if self.config['schedule']['notifications']['on_success']:
                    self._send_success_notification(
                        target_date, 
                        len(papers), 
                        len(summarized_papers),
                        document_info.get('url')
                    )
                
                result = {
                    "status": "success",
                    "date": target_date.isoformat(),
                    "total_papers": len(papers),
                    "filtered_papers": len(summarized_papers),
                    "document_url": document_info.get('url'),
                    "execution_time": datetime.now().isoformat()
                }
            
            else:
                # 调试模式或干跑模式
                self.logger.info("dry_run_completed", 
                               papers_processed=len(summarized_papers))
                result = {
                    "status": "dry_run",
                    "date": target_date.isoformat(),
                    "total_papers": len(papers),
                    "filtered_papers": len(summarized_papers),
                    "document_url": None,
                    "execution_time": datetime.now().isoformat()
                }
            
            self.logger.info("daily_digest_completed", result=result)
            return result
            
        except Exception as e:
            self.logger.error("daily_digest_failed", error=str(e), exc_info=True)
            
            # 发送失败通知
            if (self.feishu_client and 
                self.config['schedule']['notifications']['on_failure']):
                self._send_failure_notification(target_date, str(e))
            
            return {
                "status": "error",
                "date": target_date.isoformat() if target_date else "unknown",
                "error": str(e),
                "execution_time": datetime.now().isoformat()
            }
    
    def _send_success_notification(self, date, total_papers, filtered_papers, document_url):
        """发送成功通知"""
        try:
            message = f"✅ AI硬件论文日报生成成功\n\n"
            message += f"📅 日期: {date}\n"
            message += f"📊 抓取论文: {total_papers}篇\n"
            message += f"🎯 筛选通过: {filtered_papers}篇\n"
            
            if document_url:
                message += f"📄 文档链接: {document_url}\n"
            
            if self.feishu_client:
                self.feishu_client.send_notification(message)
                self.logger.info("success_notification_sent")
        
        except Exception as e:
            self.logger.error("failed_to_send_success_notification", error=str(e))
    
    def _send_failure_notification(self, date, error_message):
        """发送失败通知"""
        try:
            message = f"❌ AI硬件论文日报生成失败\n\n"
            message += f"📅 日期: {date}\n"
            message += f"💥 错误: {error_message}\n"
            message += f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            if self.feishu_client:
                self.feishu_client.send_notification(message)
                self.logger.info("failure_notification_sent")
        
        except Exception as e:
            self.logger.error("failed_to_send_failure_notification", error=str(e))


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Arxiv AI硬件加速论文每日摘要生成工具"
    )
    
    parser.add_argument(
        "--date",
        type=str,
        help="指定日期 (格式: YYYY-MM-DD)，默认为今天"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.yaml",
        help="配置文件路径"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式（不实际创建飞书文档）"
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="运行测试模式（使用示例数据）"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别"
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_arguments()
    
    try:
        # 创建并运行日报生成器
        digest = ArxivAIDailyDigest(
            config_path=args.config,
            debug=args.debug or args.test
        )
        
        # 运行日报生成
        result = digest.run(target_date=args.date)
        
        # 输出结果
        print("\n" + "="*50)
        print("Arxiv AI硬件日报生成结果")
        print("="*50)
        
        for key, value in result.items():
            print(f"{key}: {value}")
        
        print("="*50)
        
        # 根据结果状态返回适当的退出码
        if result.get("status") == "error":
            sys.exit(1)
        elif result.get("status") == "warning":
            sys.exit(2)
        else:
            sys.exit(0)
    
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"程序执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()