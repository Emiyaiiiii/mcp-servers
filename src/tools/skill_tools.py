import os
from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from src.utils.logger import get_logger

logger = get_logger(__name__)

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "skills")


def _get_skill_files(skill_name: str) -> list[str]:
    """递归获取 skill 目录下所有文件（相对路径）"""
    skill_dir = os.path.join(SKILLS_DIR, skill_name)
    if not os.path.isdir(skill_dir):
        return []
    files = []
    for root, dirs, filenames in os.walk(skill_dir):
        for f in sorted(filenames):
            rel_path = os.path.relpath(os.path.join(root, f), skill_dir)
            files.append(rel_path)
    return files


def _get_available_skills() -> list[dict]:
    """扫描 skills 目录，返回可用 skill 列表"""
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills
    for name in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, name)
        skill_file = os.path.join(skill_dir, "SKILL.md")
        if os.path.isdir(skill_dir) and os.path.isfile(skill_file):
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    content = f.read()
                title = name
                lines = content.strip().split("\n")
                if lines[0].startswith("---"):
                    for line in lines[1:]:
                        if line.startswith("title:"):
                            title = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
                elif content.startswith("#"):
                    title = content.split("\n")[0].lstrip("#").strip()
                skills.append({
                    "name": name,
                    "title": title,
                    "description": content[:200].replace("\n", " ").strip(),
                    "files": _get_skill_files(name),
                })
            except Exception as e:
                logger.warning(f"读取 skill {name} 失败: {e}")
    return skills


def register_skill_tools(mcp: FastMCP):
    """注册 Skill 读取工具"""
    available_skills = _get_available_skills()
    skill_names = ", ".join(s["name"] for s in available_skills)

    # 构建每个 skill 及其文件的描述
    skill_descriptions = []
    for s in available_skills:
        files_str = ", ".join(s["files"])
        skill_descriptions.append(f"  - {s['name']}: {s['title']} — 文件: {files_str}")

    skill_blocks = "\n".join(skill_descriptions)

    @mcp.tool(name="get_skill", auth=require_scopes("skill"))
    async def get_skill(skill_name: str, file_path: str = "SKILL.md") -> str:
        """获取 Skill 目录下的指定文件内容。

默认读取 SKILL.md（包含 AI 助手执行特定任务的完整指令），
也可通过 file_path 参数读取 skill 目录下的其他引用文件或脚本。

可用 Skills 及其文件:
{skill_blocks}

Args:
    skill_name: Skill 名称
    file_path: 文件路径（相对 skill 目录），默认 "SKILL.md"
"""
        # 安全检查：防止路径穿越
        clean_name = os.path.basename(os.path.normpath(skill_name))
        clean_path = os.path.normpath(file_path)
        if clean_path.startswith("..") or os.path.isabs(clean_path):
            return f"无效的文件路径: {file_path}"

        full_path = os.path.join(SKILLS_DIR, clean_name, clean_path)
        # 确保文件在 skills 目录内
        real_path = os.path.realpath(full_path)
        if not real_path.startswith(os.path.realpath(SKILLS_DIR)):
            return f"无效的文件路径: {file_path}"

        if not os.path.isfile(real_path):
            if clean_path == "SKILL.md":
                available = [d for d in os.listdir(SKILLS_DIR)
                             if os.path.isdir(os.path.join(SKILLS_DIR, d))
                             and os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md"))]
                return f"Skill '{skill_name}' 不存在。可用 Skills: {', '.join(sorted(available))}"
            return f"文件 '{file_path}' 不存在于 skill '{skill_name}' 中。可用文件: {', '.join(_get_skill_files(clean_name))}"

        try:
            with open(real_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"读取文件失败: {e}"

    logger.info(f"Skill 工具已注册，{len(available_skills)} 个可用 Skills: {skill_names}")