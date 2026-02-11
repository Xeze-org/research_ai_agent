"""Pydantic request/response models for the LaTeX service."""

from pydantic import BaseModel


class CompilePdfRequest(BaseModel):
    latex_body: str
    title: str


class CompileTexRequest(BaseModel):
    latex_body: str
    title: str


class CompileTexResponse(BaseModel):
    tex_source: str
