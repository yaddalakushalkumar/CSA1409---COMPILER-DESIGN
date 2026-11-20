"""
server.py - FastAPI Web Server for Multi-Language Visual Compiler System
Supports compilation and multi-stage analysis for C, Python, Java, and C++.
"""

import os
import glob
from typing import Optional, List, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from compiler import CompilerPipeline

app = FastAPI(
    title="Multi-Language Visual Compiler System API",
    description="Multi-Stage Source Code Analysis for C, Python, Java, and C++",
    version="2.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = CompilerPipeline()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")


class CompileRequest(BaseModel):
    code: str
    language: Optional[str] = "c"
    execute: Optional[bool] = True
    inputs: Optional[List[Any]] = []


@app.post("/api/compile")
def api_compile(req: CompileRequest):
    try:
        result = pipeline.compile(
            source_code=req.code,
            language=req.language or "c",
            execute=req.execute,
            inputs=req.inputs
        )
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/samples")
def api_list_samples(lang: Optional[str] = Query(None)):
    """Lists available sample programs, optionally filtered by language."""
    target_dir = os.path.join(SAMPLES_DIR, lang) if lang and os.path.exists(os.path.join(SAMPLES_DIR, lang)) else SAMPLES_DIR

    samples = []
    # Search root samples and subfolder samples
    patterns = ["*.clite", "*.c", "*.py", "*.java", "*.cpp"]
    files = []
    if lang and os.path.exists(os.path.join(SAMPLES_DIR, lang)):
        for pat in patterns:
            files.extend(glob.glob(os.path.join(SAMPLES_DIR, lang, pat)))
    else:
        for pat in patterns:
            files.extend(glob.glob(os.path.join(SAMPLES_DIR, "**", pat), recursive=True))

    for path in sorted(files):
        rel_path = os.path.relpath(path, SAMPLES_DIR).replace("\\", "/")
        filename = os.path.basename(path)
        title = filename
        try:
            with open(path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("//") or first_line.startswith("#"):
                    title = first_line.lstrip("/# ").strip()
        except Exception:
            pass

        # Detect language
        ext = os.path.splitext(filename)[1].lower()
        l_name = "c"
        if ext in (".py",):
            l_name = "python"
        elif ext in (".java",):
            l_name = "java"
        elif ext in (".cpp", ".hpp", ".cc"):
            l_name = "cpp"
        elif ext in (".c", ".clite", ".h"):
            l_name = "c"

        samples.append({
            "path": rel_path,
            "filename": filename,
            "title": title,
            "language": l_name
        })
    return samples


@app.get("/api/samples/{filepath:path}")
def api_get_sample(filepath: str):
    path = os.path.join(SAMPLES_DIR, filepath)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Sample not found")
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    return {"path": filepath, "code": code}


if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Compiler backend ready."}


if __name__ == "__main__":
    import uvicorn
    print("[*] Starting Multi-Language Visual Compiler System on http://localhost:8000 ...")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
