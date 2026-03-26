"""
配置加载器 - 加载和管理配置文件
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器"""
    
    DEFAULT_CONFIG = {
        'arxiv': {
            'base_url': 'http://export.arxiv.org/api/query',
            'categories': ['cs.AR', 'cs.AI', 'cs.LG'],
            'keywords': {
                'hardware': ['quantization', 'sparsity', 'LLM hardware', 'AI accelerator'],
                'techniques': ['model compression', 'pruning']
            },
            'max_results': 100,
            'days_back': 7
        },
        'filter': {
            'quality_threshold': 0.7,
            'min_papers_per_day': 5,
            'max_papers_per_day': 15,
            'scoring_weights': {
                'keyword_match': 0.4,
                'author_reputation': 0.3,
                'recency': 0.2,
                'content_quality': 0.1
            }
        },
        'feishu': {
            'app_id': '',
            'app_secret': '',
            'document_folder': 'AI论文日报',
            'document_title': 'AI硬件加速论文日报 - {date}'
        },
        'schedule': {
            'cron': '0 8 * * *',
            'timezone': 'Asia/Shanghai',
            'notifications': {
                'on_success': True,
                'on_failure': True
            }
        },
        'logging': {
            'level': 'INFO',
            'format': 'json',
            'file': 'logs/arxiv_digest.log'
        },
        'debug': {
            'enabled': False,
            'dry_run': False
        }
    }
    
    @staticmethod
    def load(config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认配置
            
        Returns:
            配置字典
        """
        config = ConfigLoader.DEFAULT_CONFIG.copy()
        
        # 尝试从多个位置加载配置文件
        config_files = []
        
        if config_path:
            config_files.append(Path(config_path))
        
        # 默认配置文件位置
        project_root = Path(__file__).parent.parent
        config_files.extend([
            project_root / 'config' / 'settings.yaml',
            project_root / 'config' / 'settings.yml',
            Path('config/settings.yaml'),
            Path('config/settings.yml'),
            Path('settings.yaml'),
            Path('settings.yml')
        ])
        
        # 查找并加载配置文件
        loaded_config = None
        for config_file in config_files:
            if config_file.exists():
                try:
                    loaded_config = ConfigLoader._load_yaml_file(config_file)
                    logger.info("config_file_loaded", path=str(config_file))
                    break
                except Exception as e:
                    logger.warning("failed_to_load_config_file", 
                                 path=str(config_file),
                                 error=str(e))
        
        # 合并配置
        if loaded_config:
            config = ConfigLoader._deep_merge(config, loaded_config)
        
        # 加载环境变量
        config = ConfigLoader._load_from_env(config)
        
        # 验证配置
        ConfigLoader._validate_config(config)
        
        logger.info("configuration_loaded", 
                   config_source="file" if loaded_config else "default",
                   config_keys=list(config.keys()))
        
        return config
    
    @staticmethod
    def _load_yaml_file(file_path: Path) -> Dict[str, Any]:
        """加载YAML配置文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 处理环境变量替换
        content = ConfigLoader._replace_env_vars(content)
        
        return yaml.safe_load(content) or {}
    
    @staticmethod
    def _replace_env_vars(content: str) -> str:
        """替换内容中的环境变量"""
        import re
        
        def replace_match(match):
            env_var = match.group(1)
            return os.getenv(env_var, match.group(0))
        
        # 匹配 ${VAR_NAME} 格式
        pattern = r'\$\{([A-Za-z0-9_]+)\}'
        return re.sub(pattern, replace_match, content)
    
    @staticmethod
    def _load_from_env(config: Dict[str, Any]) -> Dict[str, Any]:
        """从环境变量加载配置"""
        # 飞书配置
        if not config['feishu'].get('app_id'):
            config['feishu']['app_id'] = os.getenv('FEISHU_APP_ID', '')
        
        if not config['feishu'].get('app_secret'):
            config['feishu']['app_secret'] = os.getenv('FEISHU_APP_SECRET', '')
        
        # 调试模式
        debug_env = os.getenv('DEBUG', '').lower()
        if debug_env in ('true', '1', 'yes'):
            config['debug']['enabled'] = True
        
        dry_run_env = os.getenv('DRY_RUN', '').lower()
        if dry_run_env in ('true', '1', 'yes'):
            config['debug']['dry_run'] = True
        
        # 日志级别
        log_level = os.getenv('LOG_LEVEL', '').upper()
        if log_level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            config['logging']['level'] = log_level
        
        return config
    
    @staticmethod
    def _deep_merge(base: Dict, update: Dict) -> Dict:
        """深度合并两个字典"""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def _validate_config(config: Dict[str, Any]) -> None:
        """验证配置"""
        errors = []
        
        # 验证Arxiv配置
        if not config['arxiv'].get('categories'):
            errors.append("Arxiv categories不能为空")
        
        if config['arxiv'].get('max_results', 0) <= 0:
            errors.append("Arxiv max_results必须大于0")
        
        if config['arxiv'].get('days_back', 0) <= 0:
            errors.append("Arxiv days_back必须大于0")
        
        # 验证筛选配置
        if not 0 <= config['filter'].get('quality_threshold', 0) <= 1:
            errors.append("quality_threshold必须在0-1之间")
        
        if config['filter'].get('min_papers_per_day', 0) < 0:
            errors.append("min_papers_per_day不能为负数")
        
        if config['filter'].get('max_papers_per_day', 0) < config['filter'].get('min_papers_per_day', 0):
            errors.append("max_papers_per_day不能小于min_papers_per_day")
        
        # 验证权重配置
        weights = config['filter'].get('scoring_weights', {})
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.01:  # 允许微小误差
            errors.append(f"scoring_weights权重总和应为1.0，当前为{weight_sum}")
        
        # 验证飞书配置（仅在非调试模式下）
        if not config['debug'].get('dry_run', False):
            if not config['feishu'].get('app_id'):
                errors.append("飞书app_id未设置")
            
            if not config['feishu'].get('app_secret'):
                errors.append("飞书app_secret未设置")
        
        # 如果有错误，记录并抛出异常
        if errors:
            error_msg = "配置验证失败:\n" + "\n".join(f"  - {error}" for error in errors)
            logger.error("config_validation_failed", errors=errors)
            raise ValueError(error_msg)
        
        logger.info("config_validation_passed")
    
    @staticmethod
    def save_default_config(output_path: str) -> None:
        """
        保存默认配置到文件
        
        Args:
            output_path: 输出文件路径
        """
        config_dir = Path(output_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(ConfigLoader.DEFAULT_CONFIG, f, 
                     default_flow_style=False, 
                     allow_unicode=True,
                     sort_keys=False)
        
        logger.info("default_config_saved", path=output_path)
    
    @staticmethod
    def print_config_summary(config: Dict[str, Any]) -> None:
        """打印配置摘要"""
        summary = {
            'arxiv': {
                'categories': config['arxiv'].get('categories', []),
                'max_results': config['arxiv'].get('max_results'),
                'days_back': config['arxiv'].get('days_back')
            },
            'filter': {
                'quality_threshold': config['filter'].get('quality_threshold'),
                'min_papers': config['filter'].get('min_papers_per_day'),
                'max_papers': config['filter'].get('max_papers_per_day')
            },
            'feishu': {
                'app_id_set': bool(config['feishu'].get('app_id')),
                'document_folder': config['feishu'].get('document_folder')
            },
            'debug': config.get('debug', {})
        }
        
        print("配置摘要:")
        print(json.dumps(summary, indent=2, ensure_ascii=False))


# 测试函数
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    print("测试配置加载器...")
    
    # 测试1: 加载默认配置
    print("\n1. 加载默认配置:")
    default_config = ConfigLoader.load()
    ConfigLoader.print_config_summary(default_config)
    
    # 测试2: 保存默认配置
    print("\n2. 保存默认配置到文件:")
    test_config_path = "/tmp/test_config.yaml"
    ConfigLoader.save_default_config(test_config_path)
    print(f"配置文件已保存到: {test_config_path}")
    
    # 测试3: 从文件加载配置
    print("\n3. 从文件加载配置:")
    if os.path.exists(test_config_path):
        file_config = ConfigLoader.load(test_config_path)
        ConfigLoader.print_config_summary(file_config)
    
    # 测试4: 环境变量配置
    print("\n4. 测试环境变量配置:")
    os.environ['FEISHU_APP_ID'] = 'test_app_id_from_env'
    os.environ['FEISHU_APP_SECRET'] = 'test_secret_from_env'
    os.environ['DEBUG'] = 'true'
    
    env_config = ConfigLoader.load()
    print(f"飞书app_id: {env_config['feishu']['app_id'][:10]}...")
    print(f"调试模式: {env_config['debug']['enabled']}")
    
    # 清理环境变量
    del os.environ['FEISHU_APP_ID']
    del os.environ['FEISHU_APP_SECRET']
    del os.environ['DEBUG']
    
    print("\n配置加载器测试完成!")