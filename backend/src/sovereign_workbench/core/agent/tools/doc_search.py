"""Local knowledge-base search tool (RAG)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sovereign_workbench.core.agent.tools.base import Tool, ToolContext, ToolResult


class SearchDocumentsArgs(BaseModel):
    query: str = Field(description="Natural-language query against the local knowledge base.")
    top_k: int = Field(default=5, ge=1, le=20)


class SearchDocumentsTool(Tool):
    name = "search_documents"
    description = (
        "Search the organisation's local manuals, SOPs and past documents. Returns "
        "excerpts with citations to the source file and page."
    )
    args_schema = SearchDocumentsArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, SearchDocumentsArgs)
        try:
            from sovereign_workbench.core.rag.retriever import get_retriever

            chunks = get_retriever().search(args.query, top_k=args.top_k)
        except Exception as exc:
            return ToolResult(ok=False, error=f"retrieval failed: {exc}")
        if not chunks:
            return ToolResult(ok=True, output="(no matching documents)", data={"results": []})
        lines = []
        citations = []
        for chunk in chunks:
            cite = chunk.citation
            lines.append(f"[{cite.filename}{f' p.{cite.page}' if cite.page else ''}] {chunk.text}")
            citations.append(cite.model_dump(mode="json"))
        return ToolResult(
            ok=True,
            output="\n\n".join(lines),
            data={"citations": citations, "count": len(chunks)},
        )
