"""
飞书API客户端 - 创建和管理飞书文档
"""

import os
import json
import logging
import time
from typing import Dict, List, Optional, Any
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class FeishuClient:
    """飞书API客户端"""
    
    def __init__(self, config: Dict):
        """初始化飞书客户端"""
        self.app_id = os.getenv('FEISHU_APP_ID') or config.get('app_id')
        self.app_secret = os.getenv('FEISHU_APP_SECRET') or config.get('app_secret')
        self.document_folder = config.get('document_folder', 'AI论文日报')
        self.document_title_template = config.get('document_title', 'AI硬件加速论文日报 - {date}')
        
        # 飞书API端点
        self.base_url = "https://open.feishu.cn/open-apis"
        
        # 访问令牌
        self.access_token = None
        self.token_expires_at = 0
        
        # 文件夹token缓存
        self.folder_tokens = {}
        
        logger.info("feishu_client_initialized", 
                   app_id=self.app_id[:10] + "..." if self.app_id else "not_set",
                   folder=self.document_folder)
        
        # 验证配置
        if not self.app_id or not self.app_secret:
            logger.warning("feishu_credentials_not_set")
    
    def _get_access_token(self) -> Optional[str]:
        """获取飞书访问令牌"""
        # 如果令牌有效且未过期，直接返回
        current_time = time.time()
        if self.access_token and current_time < self.token_expires_at - 60:  # 提前60秒刷新
            return self.access_token
        
        try:
            url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
            data = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }
            
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('code') == 0:
                self.access_token = result['tenant_access_token']
                self.token_expires_at = current_time + result['expire']
                logger.info("feishu_token_obtained", expires_in=result['expire'])
                return self.access_token
            else:
                logger.error("failed_to_get_feishu_token", error=result.get('msg'))
                return None
                
        except Exception as e:
            logger.error("feishu_token_request_failed", error=str(e))
            return None
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """发送飞书API请求"""
        token = self._get_access_token()
        if not token:
            return None
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=30,
                **kwargs
            )
            
            # 记录请求详情（调试用）
            logger.debug("feishu_api_request", 
                       method=method,
                       endpoint=endpoint,
                       status_code=response.status_code)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    return result.get('data')
                else:
                    logger.error("feishu_api_error", 
                               code=result.get('code'),
                               msg=result.get('msg'),
                               endpoint=endpoint)
            else:
                logger.error("feishu_http_error", 
                           status_code=response.status_code,
                           response=response.text[:200],
                           endpoint=endpoint)
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error("feishu_request_failed", 
                       endpoint=endpoint,
                       error=str(e))
            return None
    
    def create_document(self, title: str, content: str, folder_token: str = None) -> Optional[Dict]:
        """
        创建飞书文档
        
        Args:
            title: 文档标题
            content: 文档内容（Markdown格式）
            folder_token: 文件夹token，如果为None则创建在根目录
            
        Returns:
            文档信息字典，包含document_id和url
        """
        try:
            # 构建文档创建请求
            request_data = {
                "folder_token": folder_token or "",
                "title": title,
                "content": self._format_content(content)
            }
            
            result = self._make_request('POST', '/drive/v1/files', json=request_data)
            
            if result:
                document_id = result.get('token')
                document_url = f"https://example.feishu.cn/docs/{document_id}"  # 实际URL需要从API获取
                
                logger.info("feishu_document_created", 
                          title=title,
                          document_id=document_id)
                
                return {
                    'document_id': document_id,
                    'url': document_url,
                    'title': title,
                    'created_time': datetime.now().isoformat()
                }
            else:
                logger.error("failed_to_create_feishu_document", title=title)
                return None
                
        except Exception as e:
            logger.error("document_creation_failed", title=title, error=str(e))
            return None
    
    def _format_content(self, markdown_content: str) -> str:
        """
        将Markdown内容转换为飞书文档格式
        
        注意: 这是一个简化版本，实际需要根据飞书文档格式进行转换
        飞书文档使用特定的JSON格式，这里返回简化版本
        """
        # 简化处理：将Markdown转换为飞书文档格式
        # 实际实现需要根据飞书API文档进行完整转换
        lines = markdown_content.split('\n')
        elements = []
        
        for line in lines:
            if line.startswith('# '):
                # 一级标题
                elements.append({
                    "type": "title",
                    "text": line[2:]
                })
            elif line.startswith('## '):
                # 二级标题
                elements.append({
                    "type": "heading",
                    "level": 2,
                    "text": line[3:]
                })
            elif line.startswith('### '):
                # 三级标题
                elements.append({
                    "type": "heading",
                    "level": 3,
                    "text": line[4:]
                })
            elif line.strip():
                # 普通段落
                elements.append({
                    "type": "paragraph",
                    "text": line
                })
            else:
                # 空行
                elements.append({
                    "type": "paragraph",
                    "text": ""
                })
        
        # 简化的飞书文档格式
        return json.dumps({
            "title": "AI硬件加速论文日报",
            "body": {
                "blocks": elements
            }
        }, ensure_ascii=False)
    
    def find_or_create_folder(self, folder_name: str) -> Optional[str]:
        """
        查找或创建文件夹
        
        Args:
            folder_name: 文件夹名称
            
        Returns:
            文件夹token，如果失败则返回None
        """
        # 检查缓存
        if folder_name in self.folder_tokens:
            return self.folder_tokens[folder_name]
        
        try:
            # 首先尝试查找现有文件夹
            result = self._make_request('GET', '/drive/v1/files', params={
                'filter': f'name="{folder_name}"',
                'type': 'folder'
            })
            
            if result and result.get('files'):
                folder_token = result['files'][0]['token']
                self.folder_tokens[folder_name] = folder_token
                logger.info("folder_found", name=folder_name, token=folder_token)
                return folder_token
            
            # 如果没有找到，创建新文件夹
            create_data = {
                "name": folder_name,
                "type": "folder"
            }
            
            result = self._make_request('POST', '/drive/v1/files', json=create_data)
            
            if result:
                folder_token = result.get('token')
                self.folder_tokens[folder_name] = folder_token
                logger.info("folder_created", name=folder_name, token=folder_token)
                return folder_token
            else:
                logger.error("failed_to_create_folder", name=folder_name)
                return None
                
        except Exception as e:
            logger.error("folder_operation_failed", name=folder_name, error=str(e))
            return None
    
    def create_daily_digest(self, title: str, content: str, folder: str = None) -> Optional[Dict]:
        """
        创建每日摘要文档
        
        Args:
            title: 文档标题
            content: 文档内容
            folder: 文件夹名称，如果为None则使用配置的文件夹
            
        Returns:
            文档信息
        """
        if folder is None:
            folder = self.document_folder
        
        # 获取或创建文件夹
        folder_token = None
        if folder:
            folder_token = self.find_or_create_folder(folder)
        
        # 创建文档
        document_info = self.create_document(title, content, folder_token)
        
        if document_info:
            logger.info("daily_digest_created", 
                      title=title,
                      folder=folder,
                      document_id=document_info.get('document_id'))
        else:
            logger.error("failed_to_create_daily_digest", title=title)
        
        return document_info
    
    def send_notification(self, message: str, webhook_url: str = None) -> bool:
        """
        发送飞书通知
        
        Args:
            message: 通知消息
            webhook_url: 飞书群机器人webhook URL
            
        Returns:
            是否发送成功
        """
        if not webhook_url:
            # 如果没有提供webhook，尝试从环境变量获取
            webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
        
        if not webhook_url:
            logger.warning("feishu_webhook_not_set")
            return False
        
        try:
            # 飞书群机器人消息格式
            payload = {
                "msg_type": "text",
                "content": {
                    "text": message
                }
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('code') == 0:
                logger.info("feishu_notification_sent", message_length=len(message))
                return True
            else:
                logger.error("failed_to_send_feishu_notification", error=result.get('msg'))
                return False
                
        except Exception as e:
            logger.error("notification_send_failed", error=str(e))
            return False
    
    def update_document(self, document_id: str, content: str) -> bool:
        """
        更新现有文档
        
        Args:
            document_id: 文档ID
            content: 新的文档内容
            
        Returns:
            是否更新成功
        """
        try:
            # 飞书文档更新API
            update_data = {
                "content": self._format_content(content)
            }
            
            result = self._make_request('PUT', f'/drive/v1/files/{document_id}', json=update_data)
            
            if result:
                logger.info("feishu_document_updated", document_id=document_id)
                return True
            else:
                logger.error("failed_to_update_feishu_document", document_id=document_id)
                return False
                
        except Exception as e:
            logger.error("document_update_failed", document_id=document_id, error=str(e))
            return False
    
    def list_documents(self, folder_token: str = None, limit: int = 100) -> List[Dict]:
        """
        列出文档
        
        Args:
            folder_token: 文件夹token，如果为None则列出根目录文档
            limit: 最大返回数量
            
        Returns:
            文档列表
        """
        try:
            params = {
                'folder_token': folder_token or '',
                'page_size': min(limit, 200),
                'type': 'doc'  # 只列出文档
            }
            
            result = self._make_request('GET', '/drive/v1/files', params=params)
            
            if result:
                documents = result.get('files', [])
                logger.info("documents_listed", count=len(documents), folder=folder_token)
                return documents
            else:
                return []
                
        except Exception as e:
            logger.error("failed_to_list_documents", error=str(e))
            return []


# 简化版本：用于测试的模拟客户端
class MockFeishuClient(FeishuClient):
    """模拟飞书客户端，用于测试"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.mock_documents = []
        logger.info("mock_feishu_client_initialized")
    
    def create_document(self, title: str, content: str, folder_token: str = None) -> Optional[Dict]:
        """模拟创建文档"""
        document_id = f"mock_doc_{len(self.mock_documents) + 1}"
        document_info = {
            'document_id': document_id,
            'url': f"https://mock.feishu.cn/docs/{document_id}",
            'title': title,
            'content_preview': content[:100] + "..." if len(content) > 100 else content,
            'created_time': datetime.now().isoformat(),
            'mock': True
        }
        
        self.mock_documents.append(document_info)
        logger.info("mock_document_created", title=title, document_id=document_id)
        
        return document_info
    
    def send_notification(self, message: str, webhook_url: str = None) -> bool:
        """模拟发送通知"""
        logger.info("mock_notification_sent", message=message[:100])
        return True


# 测试函数
if __name__ == "__main__":
    # 测试配置
    config = {
        'app_id': 'test_app_id',
        'app_secret': 'test_app_secret',
        'document_folder': '测试文件夹',
        'document_title': '测试文档 - {date}'
    }
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 使用模拟客户端进行测试
    client = MockFeishuClient(config)
    
    print("测试飞书客户端...")
    
    # 测试创建文档
    test_content = """
    # 测试文档
    
    ## 章节1
    这是测试内容。
    
    ## 章节2
    更多测试内容。
    """
    
    result = client.create_daily_digest(
        title="测试文档标题",
        content=test_content,
        folder="测试文件夹"
    )
    
    if result:
        print(f"\n文档创建成功:")
        print(f"  文档ID: {result.get('document_id')}")
        print(f"  文档标题: {result.get('title')}")
        print(f"  内容预览: {result.get('content_preview', '')}")
    else:
        print("\n文档创建失败")
    
    # 测试发送通知
    success = client.send_notification("测试通知消息")
    print(f"\n通知发送: {'成功' if success else '失败'}")