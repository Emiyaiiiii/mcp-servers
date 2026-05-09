from mcp.server.fastmcp import FastMCP
import os
import requests
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from src.utils.logger import get_logger

logger = get_logger(__name__)

KNOWLEDGE_BASE_API_URL = "http://10.4.158.35:9621/query/data"

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"

def register_plan_tools(mcp: FastMCP):
    """注册预案相关工具"""

    @mcp.tool()
    async def list_plan_templates() -> dict:
        """
        列出所有可用的预案模板。

        Returns:
            模板列表，每个模板包含name和description
        """
        logger.info(f"调用 list_plan_templates，收到参数: (无)")
        try:
            templates = []
            for f in os.listdir(TEMPLATE_DIR):
                if f.endswith(('.md', '.j2', '.jinja')):
                    templates.append({
                        "name": f,
                        "description": _get_template_description(f)
                    })
            return_value = {"templates": templates}
            logger.debug(f"list_plan_templates 返回结果: {return_value}")
            return return_value
        except Exception as e:
            return_value = {"error": f"获取模板列表时出错: {str(e)}"}
            logger.debug(f"list_plan_templates 返回结果: {return_value}")
            return return_value

    @mcp.tool()
    async def load_plan_template(template_name: str) -> str:
        """
        加载并渲染预案模板。

        Args:
            template_name: 模板文件名。可选值: flood_control.md, reservoir_dispatch.md

        Returns:
            渲染后的模板内容
        """
        logger.info(f"调用 load_plan_template，收到参数: template_name={repr(template_name)}")
        try:
            env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
            template = env.get_template(template_name)
            return_value = template.render()
            logger.debug(f"load_plan_template 返回结果: {repr(return_value)}")
            return return_value
        except TemplateNotFound:
            available = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(('.md', '.j2', '.jinja'))]
            return_value = f"模板 '{template_name}' 不存在。可用模板: {available}"
            logger.debug(f"load_plan_template 返回结果: {repr(return_value)}")
            return return_value
        except Exception as e:
            return_value = f"加载模板时出错: {str(e)}"
            logger.debug(f"load_plan_template 返回结果: {repr(return_value)}")
            return return_value

    @mcp.tool()
    async def query_knowledge_base(query: str, mode: str = "hybrid") -> dict:
        """
        查询防洪知识库。

        Args:
            query: 查询关键词，如: 水库调度, 防洪预演, 预警响应, 应急处置
            mode: 查询模式，可选: local(本地实体关系), global(全局模式), hybrid(混合模式), naive(向量检索), mix(知识图谱+向量)

        Returns:
            查询结果，包含entities(实体), relationships(关系), chunks(文本片段), references(参考文献)
        """
        logger.info(f"调用 query_knowledge_base，收到参数: query={repr(query)}, mode={repr(mode)}")
        
        try:
            payload = {
                "query": query,
                "mode": mode,
                "top_k": 10
            }
            
            response = requests.post(KNOWLEDGE_BASE_API_URL, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("status") == "success":
                data = result.get("data", {})
                metadata = result.get("metadata", {})
                
                entities = data.get("entities", [])
                relationships = data.get("relationships", [])
                chunks = data.get("chunks", [])
                references = data.get("references", [])
                
                summary = []
                if chunks:
                    for chunk in chunks[:3]:
                        content = chunk.get("content", "")[:300]
                        source = chunk.get("file_path", "")
                        summary.append(f"【内容片段】{content}...\n来源: {source}")
                
                if entities:
                    for entity in entities[:3]:
                        name = entity.get("entity_name", "")
                        entity_type = entity.get("entity_type", "")
                        desc = entity.get("description", "")[:200]
                        summary.append(f"【实体】{name} ({entity_type}): {desc}...")
                
                if relationships:
                    for rel in relationships[:3]:
                        src = rel.get("src_id", "")
                        tgt = rel.get("tgt_id", "")
                        desc = rel.get("description", "")[:150]
                        summary.append(f"【关系】{src} -> {tgt}: {desc}...")
                
                return_value = {
                    "success": True,
                    "query": query,
                    "mode": mode,
                    "entities": entities,
                    "relationships": relationships,
                    "chunks": chunks,
                    "references": references,
                    "metadata": metadata,
                    "summary": "\n\n".join(summary) if summary else "未找到相关知识"
                }
                logger.debug(f"query_knowledge_base 返回结果: 成功检索到 {len(entities)} 个实体, {len(relationships)} 个关系, {len(chunks)} 个文本片段")
                return return_value
            
            else:
                error_msg = result.get("message", "查询失败")
                logger.error(f"知识库查询失败: {error_msg}")
                return {"success": False, "error": error_msg, "query": query}
        
        except requests.exceptions.RequestException as e:
            error_msg = f"调用知识库接口失败: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "query": query}


def _get_template_description(template_name: str) -> str:
    """获取模板描述"""
    descriptions = {
        "flood_control.md": "防洪应急预案模板",
        "reservoir_dispatch.md": "水库调度方案模板"
    }
    return descriptions.get(template_name, "预案模板")