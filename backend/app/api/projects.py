from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Project, Paper
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut

router = APIRouter()


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            Project,
            func.count(Paper.id).label("paper_count"),
        )
        .outerjoin(Paper, Paper.project_id == Project.id)
        .group_by(Project.id)
        .order_by(Project.created_at.desc())
    )
    result = await db.execute(stmt)
    projects = []
    for row in result.all():
        proj = row[0]
        out = ProjectOut.model_validate(proj)
        out.paper_count = row[1]
        projects.append(out)
    return projects


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(name=data.name, description=data.description)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectOut.model_validate(project)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            Project,
            func.count(Paper.id).label("paper_count"),
        )
        .outerjoin(Paper, Paper.project_id == Project.id)
        .where(Project.id == project_id)
        .group_by(Project.id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    out = ProjectOut.model_validate(row[0])
    out.paper_count = row[1]
    return out


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    await db.flush()
    await db.refresh(project)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
