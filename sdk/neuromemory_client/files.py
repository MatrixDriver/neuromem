"""高层 API：文件系统模块（示例实现）"""

from __future__ import annotations
from typing import List, Dict, Optional, BinaryIO
import httpx
from pathlib import Path


class FilesClient:
    """文件系统客户端 - 高层 API

    管理文档、URL等外部资源。
    """

    def __init__(self, http: httpx.Client):
        self._http = http

    def add_document(
        self,
        user_id: str,
        file_path: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        auto_extract: bool = True,
    ) -> Dict:
        """上传文档

        支持 PDF, Word, Markdown, TXT 等格式。

        Args:
            user_id: 用户 ID
            file_path: 文件路径
            category: 文档分类
            tags: 标签列表
            auto_extract: 是否自动提取文本并生成 embedding

        Returns:
            文档信息

        Example:
            >>> doc = client.files.add_document(
            ...     user_id="user123",
            ...     file_path="/path/to/resume.pdf",
            ...     category="personal",
            ...     tags=["resume", "career"]
            ... )
            >>> print(doc)
            {
                "file_id": "doc_abc123",
                "filename": "resume.pdf",
                "size": 1024000,
                "url": "https://obs.../abc123.pdf",
                "embedding_id": "emb_xyz789"
            }
        """
        file_path_obj = Path(file_path)

        with open(file_path_obj, "rb") as f:
            files = {"file": (file_path_obj.name, f)}
            data = {
                "user_id": user_id,
                "category": category,
                "auto_extract": str(auto_extract).lower(),
            }
            if tags:
                data["tags"] = ",".join(tags)

            resp = self._http.post("/files/documents", files=files, data=data)
            resp.raise_for_status()
            return resp.json()

    def add_text(
        self,
        user_id: str,
        title: str,
        content: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """从文本创建文档

        Args:
            user_id: 用户 ID
            title: 文档标题
            content: 文本内容
            category: 分类
            tags: 标签

        Example:
            >>> doc = client.files.add_text(
            ...     user_id="user123",
            ...     title="Meeting Notes",
            ...     content="今天讨论了 Q2 OKR..."
            ... )
        """
        payload = {
            "user_id": user_id,
            "title": title,
            "content": content,
            "category": category,
            "tags": tags,
        }
        resp = self._http.post("/files/text", json=payload)
        resp.raise_for_status()
        return resp.json()

    def add_url(
        self,
        user_id: str,
        url: str,
        category: str = "web",
        auto_extract: bool = True,
        format: str = "markdown",
    ) -> Dict:
        """添加 URL（自动下载并存储）

        Args:
            user_id: 用户 ID
            url: 网页 URL
            category: 分类
            auto_extract: 是否提取正文
            format: 保存格式 (markdown/pdf/html)

        Returns:
            文档信息

        Example:
            >>> doc = client.files.add_url(
            ...     user_id="user123",
            ...     url="https://example.com/article",
            ...     category="reading"
            ... )
            >>> print(doc)
            {
                "file_id": "url_def456",
                "original_url": "https://example.com/article",
                "title": "Article Title",
                "stored_path": "https://obs.../def456.md",
                "extracted_facts": 5
            }
        """
        payload = {
            "user_id": user_id,
            "url": url,
            "category": category,
            "auto_extract": auto_extract,
            "format": format,
        }
        resp = self._http.post("/files/urls", json=payload)
        resp.raise_for_status()
        return resp.json()

    def list(
        self,
        user_id: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        file_types: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """列出文件

        Args:
            user_id: 用户 ID
            category: 分类过滤
            tags: 标签过滤
            file_types: 文件类型过滤 (pdf/md/txt等)
            limit: 返回数量

        Returns:
            文件列表

        Example:
            >>> files = client.files.list(
            ...     user_id="user123",
            ...     category="work",
            ...     tags=["important"]
            ... )
        """
        params = {"user_id": user_id, "limit": limit}
        if category:
            params["category"] = category
        if tags:
            params["tags"] = ",".join(tags)
        if file_types:
            params["file_types"] = ",".join(file_types)

        resp = self._http.get("/files", params=params)
        resp.raise_for_status()
        return resp.json()["files"]

    def get_content(
        self,
        user_id: str,
        file_id: str,
        format: str = "text",
    ) -> str | bytes:
        """获取文件内容

        Args:
            user_id: 用户 ID
            file_id: 文件 ID
            format: 返回格式 (text/binary)

        Returns:
            文件内容

        Example:
            >>> content = client.files.get_content(
            ...     user_id="user123",
            ...     file_id="doc_abc123"
            ... )
            >>> print(content)
        """
        resp = self._http.get(
            f"/files/{file_id}/content",
            params={"user_id": user_id, "format": format}
        )
        resp.raise_for_status()

        if format == "binary":
            return resp.content
        else:
            return resp.text

    def search(
        self,
        user_id: str,
        query: str,
        file_types: Optional[List[str]] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """搜索文件内容

        Args:
            user_id: 用户 ID
            query: 搜索关键词
            file_types: 文件类型过滤
            category: 分类过滤
            limit: 返回数量

        Returns:
            搜索结果（包含匹配片段）

        Example:
            >>> results = client.files.search(
            ...     user_id="user123",
            ...     query="后端开发经验",
            ...     file_types=["pdf", "md"]
            ... )
            >>> print(results)
            [
                {
                    "file_id": "doc_abc123",
                    "filename": "resume.pdf",
                    "matches": ["3年后端开发经验..."],
                    "score": 0.92
                }
            ]
        """
        payload = {
            "user_id": user_id,
            "query": query,
            "limit": limit,
        }
        if file_types:
            payload["file_types"] = file_types
        if category:
            payload["category"] = category

        resp = self._http.post("/files/search", json=payload)
        resp.raise_for_status()
        return resp.json()["results"]

    def delete(
        self,
        user_id: str,
        file_id: str,
    ) -> bool:
        """删除文件

        Args:
            user_id: 用户 ID
            file_id: 文件 ID

        Returns:
            是否删除成功
        """
        resp = self._http.delete(
            f"/files/{file_id}",
            params={"user_id": user_id}
        )
        resp.raise_for_status()
        return resp.json()["deleted"]

    def get_metadata(
        self,
        user_id: str,
        file_id: str,
    ) -> Dict:
        """获取文件元数据

        Args:
            user_id: 用户 ID
            file_id: 文件 ID

        Returns:
            文件元数据

        Example:
            >>> meta = client.files.get_metadata(
            ...     user_id="user123",
            ...     file_id="doc_abc123"
            ... )
            >>> print(meta)
            {
                "file_id": "doc_abc123",
                "filename": "resume.pdf",
                "size": 1024000,
                "mime_type": "application/pdf",
                "category": "personal",
                "tags": ["resume", "career"],
                "created_at": "2024-01-15T10:00:00",
                "embedding_count": 5
            }
        """
        resp = self._http.get(
            f"/files/{file_id}/metadata",
            params={"user_id": user_id}
        )
        resp.raise_for_status()
        return resp.json()
