"""FastAPI application for the LaTeX compilation service."""

import logging
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from .schemas import CompilePdfRequest, CompileTexRequest, CompileTexResponse
from .latex import compile_latex_to_pdf, build_full_latex_document

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="LaTeX Compilation Service", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/compile-pdf")
async def api_compile_pdf(req: CompilePdfRequest):
    pdf_bytes = compile_latex_to_pdf(req.latex_body, req.title)
    if pdf_bytes is None:
        return JSONResponse(
            status_code=500,
            content={"detail": "PDF compilation failed"},
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=report.pdf"},
    )


@app.post("/api/compile-tex", response_model=CompileTexResponse)
async def api_compile_tex(req: CompileTexRequest):
    tex_source = build_full_latex_document(req.latex_body, req.title)
    return CompileTexResponse(tex_source=tex_source)
