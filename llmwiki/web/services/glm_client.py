"""ZhipuAI GLM API client via OpenAI-compatible interface."""

from __future__ import annotations

import os
import re as _re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from llmwiki import REPO_ROOT

load_dotenv(REPO_ROOT / ".env")

API_KEY = os.environ.get("ZAI_API_KEY", "")
BASE_URL = os.environ.get("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
MODEL_FLASH = os.environ.get("ZAI_MODEL_FLASH", "deepseek-v4-flash")
MODEL_PRO = os.environ.get("ZAI_MODEL_PRO", "gear-01")

# Kimi K2.5
KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_BASE_URL = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
KIMI_MODEL = os.environ.get("KIMI_MODEL", "kimi-k2-0711")

# DeepSeek
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_MODEL_V3 = os.environ.get("DEEPSEEK_MODEL_V3", "deepseek-chat")

# Provider registry: model_prefix → {api_key, base_url}
_PROVIDERS: dict[str, dict] = {}


def _init_providers():
    global _PROVIDERS
    if API_KEY:
        _PROVIDERS["glm"] = {"api_key": API_KEY, "base_url": BASE_URL}
    if KIMI_API_KEY:
        _PROVIDERS["kimi"] = {"api_key": KIMI_API_KEY, "base_url": KIMI_BASE_URL}
    if DEEPSEEK_API_KEY:
        _PROVIDERS["deepseek"] = {"api_key": DEEPSEEK_API_KEY, "base_url": DEEPSEEK_BASE_URL}

_init_providers()


def _get_client_for_model(model: str) -> tuple[OpenAI, str]:
    """Return (client, actual_model) for the given model name."""
    if model.startswith("kimi"):
        cfg = _PROVIDERS.get("kimi")
        if not cfg:
            raise ValueError("Kimi API key 未配置")
        return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"]), model
    elif model.startswith("deepseek"):
        cfg = _PROVIDERS.get("deepseek")
        if not cfg:
            raise ValueError("DeepSeek API key 未配置")
        # Map frontend model names to actual API model names
        actual_model = DEEPSEEK_MODEL_V3 if model == "deepseek-v3.2" else model
        return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"]), actual_model
    else:
        cfg = _PROVIDERS.get("glm")
        if not cfg:
            raise ValueError("ZAI_API_KEY 未配置")
        return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"]), model

SYSTEM_PROMPT = """你是一个企业内控制度知识库的专业问答助手。用户会提出关于公司管理制度的问题，你必须严格根据下方"知识库上下文"中的内容来回答。

回答格式（必须严格遵守）：
- 全文使用标准 Markdown 格式，禁止使用纯文本
- 用 ## 二级标题划分回答层次（如 ## 结论、## 具体规定、## 操作流程、## 注意事项）
- 用 1. 2. 3. 编号列表表示有序步骤
- 用 - 无序列表罗列并列事项
- 用 **加粗** 突出关键词、金额、部门名称等关键信息
- 用 > 引用块标注原文关键条款
- 每条引用后用 [[页面名]] 标注来源

回答内容要求：
1. 必须基于知识库上下文中的具体内容作答，绝不编造
2. 引用具体的制度条文编号、金额门槛、流程步骤、审批层级等关键数据
3. 结构化组织：先给出明确结论 → 再列出具体步骤或条件（编号列表）→ 最后补充注意事项或例外情况
4. 如果涉及金额门槛，列出具体数字和适用条件
5. 如果涉及审批流程，按顺序列出完整链条
6. 如果知识库中没有足够信息，说明"根据现有知识库，暂未找到相关信息"，并建议查阅哪类制度文件
"""


def get_client() -> OpenAI:
    if not API_KEY:
        raise ValueError("ZAI_API_KEY 未配置，请在 .env 文件中设置")
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def ask(question: str, model: str | None = None, *, wiki_dir: Path | None = None) -> str:
    """Ask a question with wiki context, return full answer."""
    context = build_context(question, wiki_dir=wiki_dir)
    client, actual_model = _get_client_for_model(model or MODEL_FLASH)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\n---\n知识库上下文:\n{context}\n---"},
        {"role": "user", "content": question},
    ]

    resp = client.chat.completions.create(
        model=actual_model,
        messages=messages,
        temperature=0.3,
        max_tokens=3000,
    )
    return resp.choices[0].message.content


def ask_stream(question: str, model: str | None = None, *, wiki_dir: Path | None = None):
    """Stream Q&A response via generator (for SSE)."""
    context = build_context(question, wiki_dir=wiki_dir)
    client, actual_model = _get_client_for_model(model or MODEL_FLASH)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\n---\n知识库上下文:\n{context}\n---"},
        {"role": "user", "content": question},
    ]

    resp = client.chat.completions.create(
        model=actual_model,
        messages=messages,
        temperature=0.3,
        max_tokens=3000,
        stream=True,
    )
    for chunk in resp:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


def _build_context_from_wiki(
    question: str,
    *,
    wiki_dir: Path | None = None,
    search_limit: int = 8,
    max_pages: int = 8,
    per_page_chars: int = 3000,
    total_max_chars: int = 20000,
    include_score: bool = False,
    fallback_to_overview: bool = True,
) -> str:
    """Search wiki and build context string for LLM prompts.

    Parameters control how many pages are searched/read and how much of each
    page is included. Used by both the non-streaming ask path and the agent
    loop preload path — the defaults match the simpler ask path (higher
    recall), while the agent path calls with tighter limits.
    """
    from llmwiki.web.services.wiki_reader import search, read_page

    results = search(question, limit=search_limit, wiki_dir=wiki_dir)

    if not results:
        if fallback_to_overview:
            overview = read_page("overview.md", wiki_dir=wiki_dir)
            if "content" in overview:
                return overview["content"][:total_max_chars]
        return ""

    context_parts = []
    total = 0
    for r in results[:max_pages]:
        page = read_page(r["path"], wiki_dir=wiki_dir)
        if "content" not in page:
            continue
        score_suffix = f", 相关度: {r.get('score', 0):.0f}" if include_score else ""
        header = f"=== {r['title']} (来源: {r['path']}{score_suffix}) ===\n"
        chunk = header + page["content"][:per_page_chars] + "\n\n"
        if total + len(chunk) > total_max_chars:
            break
        context_parts.append(chunk)
        total += len(chunk)

    return "".join(context_parts)


def build_context(question: str, max_chars: int = 20000, *, wiki_dir: Path | None = None) -> str:
    """Search wiki pages and build context string for LLM (non-streaming path)."""
    return _build_context_from_wiki(question, total_max_chars=max_chars, wiki_dir=wiki_dir)


INGEST_PROMPT = """你是一个企业知识库的结构化分析助手。请分析以下制度文档内容，提取知识要素。

严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "summary": "2-3句话概括文档核心内容",
  "key_claims": ["关键要点1", "关键要点2", "关键要点3"],
  "entities": [
    {"name": "实体名称", "type": "organization|department|system", "description": "一句话描述"}
  ],
  "concepts": [
    {"name": "概念名称", "description": "一句话描述"}
  ]
}"""


def extract_knowledge(md_content: str) -> dict:
    """Use GLM to extract entities, concepts, and summary from document content."""
    client = get_client()
    # Truncate to avoid token limit
    content = md_content[:8000]

    resp = client.chat.completions.create(
        model=MODEL_FLASH,
        messages=[
            {"role": "system", "content": INGEST_PROMPT},
            {"role": "user", "content": f"请分析以下文档：\n\n{content}"},
        ],
        temperature=0.1,
        max_tokens=1500,
    )
    text = resp.choices[0].message.content.strip()

    # Parse JSON from response (handle markdown code blocks)
    import json
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    # Find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return {"summary": "", "key_claims": [], "entities": [], "concepts": []}


# ---------------------------------------------------------------------------
# Agent Loop (inspired by claw-code run_turn pattern)
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """你是一个企业内控制度知识库的专业研究助手。你可以使用工具主动搜索和阅读知识库中的文档。

可用工具：
- search_wiki(query): 搜索知识库中的相关页面
- read_wiki_page(path): 阅读某个页面的完整内容

工作方法：
1. 先用 search_wiki 搜索与问题相关的多个关键词，全面了解涉及哪些制度文件
2. 根据搜索结果，尽可能在一次回复中调用多个 read_wiki_page 同时阅读多个相关页面（不要一次只读一个）
3. 如果涉及多个管理制度（如合同管理、采购管理、预算管理等），务必把所有相关制度的页面都读一遍
4. 关注制度之间的交叉引用和关联条款
5. 充分理解后，综合所有制度文件给出完整回答

回答格式（必须严格遵守，这是最高优先级要求）：
- 全文使用标准 Markdown 格式，绝对禁止纯文本输出
- 以 ## 标题（二级标题）划分回答层次，如 ## 结论、## 具体规定、## 操作流程、## 金额门槛、## 注意事项
- 用 1. 2. 3. 编号列表表示有序步骤或优先级
- 用 - 无序列表罗列并列事项
- 用 **加粗** 突出关键词、金额数字、部门名称、制度名称
- 用 > 引用块标注原文关键条款或制度条文
- 每条引用后用 [[页面名]] 标注来源
- 禁止使用"首先/其次/最后"代替编号列表，必须使用数字编号

回答内容要求：
1. 必须基于知识库中的具体内容作答，绝不编造
2. 引用来源时用 [[页面名]] 格式标注
3. 结构化组织：结论 → 具体步骤/条件（编号列表）→ 注意事项
4. 涉及金额门槛时列出具体数字和适用条件
5. 涉及审批流程时按顺序列出完整链条
6. 如果知识库中没有足够信息，说明"根据现有知识库，暂未找到相关信息"
7. **【最高优先级】回答末尾必须追加追问建议**：在完整回答之后，另起一行输出「## 追问建议」，然后换行列 2-3 个基于当前回答内容自然延伸的深入问题（每条一行，格式「- 问题文本」）。例如：
## 追问建议
- 差旅费报销是否有地区差异标准？
- 超过预算的报销如何申请特批？
"""

WIKI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_wiki",
            "description": "搜索知识库中的相关页面，返回匹配的页面列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数，默认10",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_wiki_page",
            "description": "读取指定 wiki 页面的完整内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "页面路径，如 sources/company-docs/xxx.md",
                    }
                },
                "required": ["path"],
            },
        },
    },
]

MAX_AGENT_ITERATIONS = 10


def _execute_wiki_tool(name: str, arguments: dict, *, wiki_dir: Path | None = None) -> str:
    """Execute a wiki tool and return string result."""
    import json as _json
    from llmwiki.web.services.wiki_reader import search, read_page

    if name == "search_wiki":
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)
        results = search(query, limit=limit, wiki_dir=wiki_dir)
        if not results:
            return "未找到相关页面。"
        lines = []
        for r in results:
            lines.append(f"- {r['title']} (路径: {r['path']}, 相关度: {r.get('score', 0):.1f})")
        return "\n".join(lines)

    elif name == "read_wiki_page":
        path = arguments.get("path", "")
        page = read_page(path, wiki_dir=wiki_dir)
        if "content" not in page:
            return f"页面不存在或无法读取: {path}"
        return page["content"][:8000]

    else:
        return f"未知工具: {name}"


def _preload_context(
    question: str,
    max_pages: int = 3,
    max_chars: int = 15000,
    *,
    wiki_dir: Path | None = None,
) -> str:
    """Pre-load top search results into context to save agent iterations."""
    return _build_context_from_wiki(
        question,
        search_limit=10,
        max_pages=max_pages,
        per_page_chars=4000,
        total_max_chars=max_chars,
        include_score=True,
        fallback_to_overview=False,
        wiki_dir=wiki_dir,
    )


def ask_agent(
    question: str,
    model: str | None = None,
    conversation_history: str | None = None,
    *,
    wiki_dir: Path | None = None,
):
    """Agent loop with tool calling — yields SSE JSON events.

    Inspired by claw-code ConversationRuntime::run_turn():
    - Pre-loads top search results into context (saves 2-3 iterations)
    - Multi-turn loop with max_iterations guard
    - Each iteration: LLM decides to call tool or give final answer
    - Tool results fed back into conversation
    - Final answer simulated as chunked stream (no extra API call)
    - Accepts optional conversation_history for follow-up context
    """
    import json

    client, actual_model = _get_client_for_model(model or MODEL_FLASH)

    # Pre-load: search and inject top results into system prompt
    preloaded_context = _preload_context(question, wiki_dir=wiki_dir)

    system_content = AGENT_SYSTEM_PROMPT
    if conversation_history:
        system_content += (
            "\n\n## 当前对话历史（同一话题的追问上下文）\n"
            "以下是你与用户在同一话题下的历史对话，请结合此上下文理解当前问题：\n\n"
            + conversation_history +
            "\n请基于以上对话历史，结合知识库内容回答当前问题。"
        )
    if preloaded_context:
        system_content += f"\n\n以下是初步搜索结果，你可能还需要进一步阅读完整页面：\n{preloaded_context}"

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question},
    ]

    total_iterations = 0
    pages_read = 3  # pre-loaded 3 pages

    for iteration in range(MAX_AGENT_ITERATIONS):
        total_iterations = iteration + 1

        yield json.dumps({
            "type": "thinking",
            "iteration": total_iterations,
            "message": f"完成第{total_iterations}轮搜索",
        }, ensure_ascii=False)

        try:
            resp = client.chat.completions.create(
                model=actual_model,
                messages=messages,
                tools=WIKI_TOOLS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=4096,
            )
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"LLM 调用失败: {e}"}, ensure_ascii=False)
            return

        choice = resp.choices[0]
        assistant_msg = choice.message
        tool_calls = assistant_msg.tool_calls

        if not tool_calls:
            # No tool calls — final answer. Use text directly, no extra API call.
            final_text = (assistant_msg.content or "").strip()
            final_text = _re.sub(r'<｜[^>]*>', '', final_text)
            if not final_text:
                final_text = "抱歉，未能生成有效回答。"

            # Simulate streaming by chunking the text
            full_answer = ""
            chunk_size = 6
            for i in range(0, len(final_text), chunk_size):
                piece = final_text[i:i + chunk_size]
                full_answer += piece
                yield json.dumps({"type": "content", "text": piece}, ensure_ascii=False)

            yield json.dumps({
                "type": "done",
                "iterations": total_iterations,
                "pages_read": pages_read,
                "answer": full_answer,
            }, ensure_ascii=False)
            return

        # --- Process tool calls (execute ONCE, reuse results) ---
        tc_dicts = []
        tool_results = {}  # tc.id -> result text

        for tc in tool_calls:
            tc_dicts.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })

            func_name = tc.function.name
            try:
                func_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                func_args = {}

            # Execute tool ONCE
            result = _execute_wiki_tool(func_name, func_args, wiki_dir=wiki_dir)
            tool_results[tc.id] = result

            if func_name == "read_wiki_page":
                pages_read += 1

            # Emit SSE events
            yield json.dumps({
                "type": "tool_call",
                "tool": func_name,
                "args": func_args,
            }, ensure_ascii=False)
            preview = result[:200].replace("\n", " ")
            result_count = result.count("\n") + 1 if result else 0
            yield json.dumps({
                "type": "tool_result",
                "tool": func_name,
                "count": result_count,
                "preview": preview,
            }, ensure_ascii=False)

        # Append to conversation history (using cached results)
        assistant_dict = {
            "role": "assistant",
            "content": assistant_msg.content,
            "tool_calls": tc_dicts,
        }
        # DeepSeek reasoning models require reasoning_content to be passed back
        if hasattr(assistant_msg, 'reasoning_content') and assistant_msg.reasoning_content:
            assistant_dict["reasoning_content"] = assistant_msg.reasoning_content
        messages.append(assistant_dict)
        for tc in tool_calls:
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_results[tc.id][:8000],
            })

    # Max iterations reached — force a final answer
    yield json.dumps({
        "type": "thinking",
        "iteration": total_iterations,
        "message": "正在生成最终回答...",
    }, ensure_ascii=False)

    messages.append({
        "role": "user",
        "content": "请根据已经获取的信息，直接给出最终回答。不要再使用任何工具。回答末尾必须包含「## 追问建议」段落，列出2-3个可继续追问的问题。",
    })

    try:
        final_resp = client.chat.completions.create(
            model=actual_model,
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
            stream=True,
        )
        full_answer = ""
        for chunk in final_resp:
            delta = chunk.choices[0].delta
            if delta.content:
                text = _re.sub(r'<｜[^>]*>', '', delta.content)
                if text.strip():
                    full_answer += text
                    yield json.dumps({"type": "content", "text": text}, ensure_ascii=False)

        full_answer = _re.sub(r'<｜[^>]*>', '', full_answer)
    except Exception as e:
        full_answer = f"生成最终回答失败: {e}"

    yield json.dumps({
        "type": "done",
        "iterations": total_iterations,
        "pages_read": pages_read,
        "answer": full_answer,
    }, ensure_ascii=False)
