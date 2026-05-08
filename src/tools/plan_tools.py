from mcp.server.fastmcp import FastMCP
import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from src.utils.logger import get_logger

logger = get_logger(__name__)

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
            logger.info(f"list_plan_templates 返回结果: {return_value}")
            return return_value
        except Exception as e:
            return_value = {"error": f"获取模板列表时出错: {str(e)}"}
            logger.info(f"list_plan_templates 返回结果: {return_value}")
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
            logger.info(f"load_plan_template 返回结果: {repr(return_value)}")
            return return_value
        except TemplateNotFound:
            available = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(('.md', '.j2', '.jinja'))]
            return_value = f"模板 '{template_name}' 不存在。可用模板: {available}"
            logger.info(f"load_plan_template 返回结果: {repr(return_value)}")
            return return_value
        except Exception as e:
            return_value = f"加载模板时出错: {str(e)}"
            logger.info(f"load_plan_template 返回结果: {repr(return_value)}")
            return return_value

    @mcp.tool()
    async def query_knowledge_base(query: str) -> str:
        """
        查询防洪知识库。

        Args:
            query: 查询关键词。可选: 水库调度, 防洪预演, 预警响应, 应急处置

        Returns:
            查询结果
        """
        logger.info(f"调用 query_knowledge_base，收到参数: query={repr(query)}")
        knowledge = {
            "水库调度": "水库调度应根据上游来水、下游防洪能力和水库蓄水能力综合确定...",
            "防洪预演": "防洪预演是通过数字孪生技术模拟不同洪水情景，评估预案有效性...",
            "预警响应": "根据暴雨洪水预警等级，启动相应级别的应急响应...",
            "应急处置": "发生超标洪水时，应立即启动应急预案，组织抢险救援..."
        }
        for key, value in knowledge.items():
            if key in query:
                return_value = f"【{key}】{value}"
                logger.info(f"query_knowledge_base 返回结果: {repr(return_value)}")
                return return_value
        return_value = f"知识库查询结果: {query} 的相关信息 (示例数据)"
        logger.info(f"query_knowledge_base 返回结果: {repr(return_value)}")
        return return_value


def _get_template_description(template_name: str) -> str:
    """获取模板描述"""
    descriptions = {
        "flood_control.md": "防洪应急预案模板",
        "reservoir_dispatch.md": "水库调度方案模板"
    }
    return descriptions.get(template_name, "预案模板")