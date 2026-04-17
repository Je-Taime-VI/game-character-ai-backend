from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.chat import CharacterChat
from src.generate_role_permissions import load_org_region_mapping, save_org_region_mapping
from src.permission_tree import (
    build_permission_forest,
    build_region_tree,
    create_raw_folder,
    create_raw_txt_file,
    delete_raw_path,
    flatten_folder_paths,
    list_permission_roles,
    load_role_permission,
    open_raw_txt_in_notepad,
    read_raw_txt_preview,
    save_role_permission,
)
from src.permissions_ui import HTML_PAGE
from src.story_editor import (
    build_world_annotation_library,
    get_editor_page,
    list_world_editor_targets,
    load_editor_document,
    save_editor_document,
    save_world_annotation_entry,
)


app = FastAPI(title="Game Character AI API")
app.mount("/editor-static", StaticFiles(directory=str(Path(__file__).with_name("static"))), name="editor-static")
chat_engine = CharacterChat()


class ChatRequest(BaseModel):
    role_name: str
    message: str
    top_k_lines: int = 8
    top_k_flat: int = 5


class PermissionSaveRequest(BaseModel):
    extra_role_paths: list[str] = []
    extra_world_paths: list[str] = []
    region_overrides: list[str] = []
    allowed_story_paths: list[str] = []
    notes: str = ""


class OrgRegionMappingRequest(BaseModel):
    organization: str
    region_path: str


class RawFolderCreateRequest(BaseModel):
    parent_path: str
    folder_name: str


class RawFileCreateRequest(BaseModel):
    parent_path: str
    file_name: str
    content: str = ""


class RawNotepadOpenRequest(BaseModel):
    path: str


class EditorSaveRequest(BaseModel):
    path: str
    document: dict


class WorldAnnotationCreateRequest(BaseModel):
    target_path: str
    term: str
    definition: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/permissions-ui", response_class=HTMLResponse)
def permissions_ui() -> str:
    return HTML_PAGE


@app.get("/editor", response_class=HTMLResponse)
def story_editor_page() -> str:
    return get_editor_page()


@app.get("/permissions/roles")
def permission_roles() -> list[str]:
    return list_permission_roles()


@app.get("/permissions/tree")
def permission_tree() -> dict:
    return build_permission_forest()


@app.get("/regions/tree")
def regions_tree() -> dict:
    tree = build_region_tree()
    return {
        "tree": tree,
        "paths": flatten_folder_paths(tree),
    }


@app.get("/permissions/file")
def permission_file_preview(path: str) -> dict:
    return read_raw_txt_preview(path)


@app.get("/editor/document")
def editor_document(path: str) -> dict:
    return load_editor_document(path)


@app.get("/editor/annotation-library")
def editor_annotation_library(query: str = "", limit: int = 200) -> dict:
    items = build_world_annotation_library()
    q = query.strip().lower()
    if q:
        items = [item for item in items if q in item["term"].lower()]
    return {"items": items[: max(1, min(limit, 500))]}


@app.get("/editor/world-targets")
def editor_world_targets() -> dict:
    return {"items": list_world_editor_targets()}


@app.post("/editor/world-annotation")
def editor_world_annotation_create(request: WorldAnnotationCreateRequest) -> dict:
    return save_world_annotation_entry(
        target_relative_path=request.target_path,
        term=request.term,
        definition=request.definition,
    )


@app.post("/editor/document")
def editor_document_save(request: EditorSaveRequest) -> dict:
    return save_editor_document(request.path, request.document)


@app.post("/raw/folder")
def raw_folder_create(request: RawFolderCreateRequest) -> dict:
    return create_raw_folder(request.parent_path, request.folder_name)


@app.post("/raw/file")
def raw_file_create(request: RawFileCreateRequest) -> dict:
    return create_raw_txt_file(request.parent_path, request.file_name, content=request.content)


@app.delete("/raw/path")
def raw_path_delete(path: str) -> dict:
    return delete_raw_path(path)


@app.post("/raw/open-notepad")
def raw_open_notepad(request: RawNotepadOpenRequest) -> dict:
    return open_raw_txt_in_notepad(request.path)


@app.get("/permissions/{role_name}")
def permission_detail(role_name: str) -> dict:
    return load_role_permission(role_name)


@app.post("/permissions/{role_name}")
def permission_save(role_name: str, request: PermissionSaveRequest) -> dict:
    path = save_role_permission(role_name, request.model_dump())
    return {"status": "ok", "path": str(path)}


@app.get("/org-mapping")
def org_mapping() -> dict[str, str]:
    return load_org_region_mapping()


@app.post("/org-mapping")
def org_mapping_save(request: OrgRegionMappingRequest) -> dict:
    mapping = load_org_region_mapping()
    organization = request.organization.strip()
    region_path = request.region_path.strip()
    mapping[organization] = region_path
    path = save_org_region_mapping(mapping)
    return {"status": "ok", "path": str(path), "organization": organization, "region_path": region_path}


@app.delete("/org-mapping/{organization}")
def org_mapping_delete(organization: str) -> dict:
    mapping = load_org_region_mapping()
    mapping.pop(organization, None)
    path = save_org_region_mapping(mapping)
    return {"status": "ok", "path": str(path), "organization": organization}


@app.post("/search")
def search(request: ChatRequest) -> dict:
    return chat_engine.search_only(
        role_name=request.role_name,
        query=request.message,
        top_k_lines=request.top_k_lines,
        top_k_flat=request.top_k_flat,
    )


@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    result = chat_engine.chat(
        role_name=request.role_name,
        user_message=request.message,
        top_k_lines=request.top_k_lines,
        top_k_flat=request.top_k_flat,
    )
    return {
        "role_name": result.role_name,
        "user_message": result.user_message,
        "reply": result.reply,
        "prompt": result.prompt,
        "retrieval_results": result.retrieval_results,
        "raw_context": result.raw_context,
    }
