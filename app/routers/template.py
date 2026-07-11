from datetime import datetime, timezone
from typing import List
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, status
from jinja2 import Template

from app.core.database import get_database
from app.routers.auth import get_current_user
from app.schemas.template import (
    TemplateCreate,
    TemplateRenderRequest,
    TemplateRenderResponse,
    TemplateResponse,
    TemplateUpdate,
)

router = APIRouter(prefix="/templates", tags=["templates"])


def render_prompt_body(body: str, variables: dict) -> str:
    """Render the body using Jinja2 with provided variables."""
    try:
        t = Template(body)
        return t.render(**variables)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Template rendering failed: {str(e)}"
        )


def _doc_to_response(doc: dict) -> TemplateResponse:
    """Convert raw MongoDB template doc to TemplateResponse schema."""
    return TemplateResponse(
        id=str(doc.get("_id", "")),
        owner_id=doc["owner_id"],
        name=doc["name"],
        body=doc["body"],
        is_deleted=doc.get("is_deleted", False),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"]
    )


@router.post("", response_model=TemplateResponse, summary="Create a new prompt template")
async def create_template(
    body: TemplateCreate,
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    owner_id_str = str(current_user["_id"])
    now = datetime.now(timezone.utc)
    
    doc = {
        "owner_id": owner_id_str,
        "name": body.name,
        "body": body.body,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now
    }
    
    res = await db.prompt_templates.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _doc_to_response(doc)


@router.get("", response_model=List[TemplateResponse], summary="List all templates for current user")
async def list_templates(
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    owner_id_str = str(current_user["_id"])
    cursor = db.prompt_templates.find({"owner_id": owner_id_str, "is_deleted": False})
    docs = await cursor.to_list(length=100)
    return [_doc_to_response(d) for d in docs]


@router.get("/{id}", response_model=TemplateResponse, summary="Retrieve a single template")
async def get_template(
    id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Template not found")
        
    template = await db.prompt_templates.find_one({"_id": ObjectId(id), "is_deleted": False})
    owner_id_str = str(current_user["_id"])
    
    if not template or template["owner_id"] != owner_id_str:
        raise HTTPException(status_code=404, detail="Template not found")
        
    return _doc_to_response(template)


@router.put("/{id}", response_model=TemplateResponse, summary="Update an existing template")
async def update_template(
    id: str,
    body: TemplateUpdate,
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Template not found")

    owner_id_str = str(current_user["_id"])
    template = await db.prompt_templates.find_one({"_id": ObjectId(id), "is_deleted": False})
    
    if not template or template["owner_id"] != owner_id_str:
        raise HTTPException(status_code=404, detail="Template not found")

    update_doc = {}
    if body.name is not None:
        update_doc["name"] = body.name
    if body.body is not None:
        update_doc["body"] = body.body

    if update_doc:
        update_doc["updated_at"] = datetime.now(timezone.utc)
        await db.prompt_templates.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_doc}
        )
        # update original doc for response returning
        template.update(update_doc)

    return _doc_to_response(template)


@router.delete("/{id}", summary="Soft-delete a template")
async def delete_template(
    id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Template not found")

    owner_id_str = str(current_user["_id"])
    template = await db.prompt_templates.find_one({"_id": ObjectId(id), "is_deleted": False})
    
    if not template or template["owner_id"] != owner_id_str:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.prompt_templates.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"is_deleted": True, "updated_at": datetime.now(timezone.utc)}}
    )
    return {"message": "Template soft-deleted successfully"}


@router.post("/{id}/render", response_model=TemplateRenderResponse, summary="Render template with variable substitution")
async def render_template_endpoint(
    id: str,
    body: TemplateRenderRequest,
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=404, detail="Template not found")

    owner_id_str = str(current_user["_id"])
    template = await db.prompt_templates.find_one({"_id": ObjectId(id), "is_deleted": False})
    
    if not template or template["owner_id"] != owner_id_str:
        raise HTTPException(status_code=404, detail="Template not found")

    rendered_content = render_prompt_body(template["body"], body.variables)
    return TemplateRenderResponse(rendered=rendered_content)
