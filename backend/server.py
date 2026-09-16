from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import List, Optional
import uuid

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="Racontelle Care API")
api_router = APIRouter(prefix="/api")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


class ResidentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    consent_status: str = "obtained"


class ResidentPatch(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    consent_status: Optional[str] = None
    active: Optional[bool] = None


class ResidentOut(BaseModel):
    id: str
    display_name: str
    consent_status: str
    active: bool
    created_at: str


class QuestionOut(BaseModel):
    id: str
    theme: str
    text: str
    sensitive: bool = False


class CapsuleCreate(BaseModel):
    resident_id: Optional[str] = None
    question_id: Optional[str] = None
    mode: str = "free"
    theme: Optional[str] = None
    title: Optional[str] = None
    duration_sec: int = 0
    recorded_at: str
    audio_uri: Optional[str] = None
    audio_base64: Optional[str] = None


class CapsuleOut(BaseModel):
    id: str
    resident_id: Optional[str] = None
    question_id: Optional[str] = None
    mode: str
    theme: Optional[str] = None
    title: Optional[str] = None
    duration_sec: int
    recorded_at: str
    status: str
    synced: bool = True


QUESTIONS = [
    ("Enfance", "Quel est votre tout premier souvenir ?"),
    ("Enfance", "À quoi ressemblait la maison de votre enfance ?"),
    ("Enfance", "Quel souvenir vous fait encore sourire aujourd’hui ?"),
    ("Famille", "Qui vous faisait le plus rire dans votre famille ?"),
    ("Famille", "Y avait-il une tradition importante chez vous ?"),
    ("Famille", "Quel conseil reçu dans votre famille avez-vous gardé ?"),
    ("École et jeunesse", "Vous souvenez-vous de votre premier jour d’école ?"),
    ("École et jeunesse", "Quel était votre rêve quand vous étiez jeune ?"),
    ("École et jeunesse", "Comment occupiez-vous vos vacances ?"),
    ("Travail", "Quel a été votre premier travail ?"),
    ("Travail", "Quel moment de votre vie professionnelle vous rend fier ?"),
    ("Travail", "Quel conseil donneriez-vous à quelqu’un qui débute aujourd’hui ?"),
    ("Amour et rencontres", "Vous souvenez-vous de votre premier amour ?"),
    ("Amour et rencontres", "Quel beau geste d’amour avez-vous reçu ?"),
    ("Amour et rencontres", "Qu’est-ce qui fait, selon vous, qu’un couple dure ?"),
    ("Cuisine et traditions", "Quel plat vous rappelle le plus votre famille ?"),
    ("Cuisine et traditions", "Quelle recette aimeriez-vous transmettre ?"),
    ("Cuisine et traditions", "Quelle odeur de cuisine vous ramène dans le passé ?"),
    ("Musique et loisirs", "Quelle chanson vous rappelle votre jeunesse ?"),
    ("Musique et loisirs", "Sur quelle musique aimiez-vous danser ?"),
    ("Musique et loisirs", "Quel plaisir simple vous a toujours rendu heureux ?"),
    ("Voyages et lieux", "Quel voyage vous a laissé le plus beau souvenir ?"),
    ("Voyages et lieux", "Quel lieu de votre jeunesse aimeriez-vous revoir ?"),
    ("Voyages et lieux", "À quoi ressemblait votre quartier autrefois ?"),
    ("Moments heureux", "De quoi êtes-vous le plus fier ?"),
    ("Moments heureux", "Quel moment vous a rendu particulièrement heureux ?"),
    ("Moments heureux", "Quel fou rire n’avez-vous jamais oublié ?"),
    ("Transmission", "Quel conseil aimeriez-vous transmettre aux plus jeunes ?"),
    ("Transmission", "Qu’est-ce qui compte vraiment dans la vie selon vous ?"),
    ("Transmission", "Qu’aimeriez-vous que l’on retienne de vous ?"),
]


async def ensure_questions() -> None:
    if await db.questions.count_documents({}):
        return
    await db.questions.insert_many([
        {"id": str(uuid.uuid4()), "theme": theme, "text": text, "sensitive": False, "created_at": now_iso()}
        for theme, text in QUESTIONS
    ])


@app.on_event("startup")
async def startup_seed() -> None:
    await ensure_questions()


@api_router.get("/")
async def root():
    return {"message": "Racontelle Care API", "offline_first": True}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_obj = StatusCheck(**input.model_dump())
    await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    docs = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    return [StatusCheck(**doc) for doc in docs]


@api_router.get("/residents", response_model=List[ResidentOut])
async def get_residents():
    return await db.residents.find({"active": True}, {"_id": 0}).sort("created_at", 1).to_list(10)


@api_router.post("/residents", response_model=ResidentOut)
async def create_resident(input: ResidentCreate):
    if await db.residents.count_documents({"active": True}) >= 10:
        raise HTTPException(status_code=400, detail="Limite de 10 profils atteinte")
    resident = {
        "id": str(uuid.uuid4()),
        "display_name": input.display_name.strip(),
        "consent_status": input.consent_status,
        "active": True,
        "created_at": now_iso(),
    }
    await db.residents.insert_one(resident)
    return resident


@api_router.patch("/residents/{resident_id}", response_model=ResidentOut)
async def update_resident(resident_id: str, input: ResidentPatch):
    changes = input.model_dump(exclude_none=True)
    if "display_name" in changes:
        changes["display_name"] = changes["display_name"].strip()
    doc = await db.residents.find_one_and_update(
        {"id": resident_id}, {"$set": changes}, return_document=True, projection={"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    return doc


@api_router.get("/questions", response_model=List[QuestionOut])
async def get_questions(theme: Optional[str] = Query(default=None), limit: int = Query(default=30, le=100)):
    query = {"sensitive": False}
    if theme and theme != "Tous":
        query["theme"] = theme
    return await db.questions.find(query, {"_id": 0}).limit(limit).to_list(limit)


@api_router.post("/capsules", response_model=CapsuleOut)
async def create_capsule(input: CapsuleCreate):
    if input.resident_id:
        resident = await db.residents.find_one({"id": input.resident_id}, {"_id": 0})
        if not resident:
            raise HTTPException(status_code=404, detail="Profil introuvable")
        if resident.get("consent_status") != "obtained":
            raise HTTPException(status_code=403, detail="Consentement requis")
    capsule = {
        "id": str(uuid.uuid4()),
        **input.model_dump(),
        "status": "assigned" if input.resident_id else "unclassified",
        "synced": True,
        "created_at": now_iso(),
    }
    await db.capsules.insert_one(capsule)
    capsule.pop("_id", None)
    capsule.pop("audio_uri", None)
    capsule.pop("audio_base64", None)
    return capsule


@api_router.get("/residents/{resident_id}/capsules", response_model=List[CapsuleOut])
async def get_resident_capsules(resident_id: str):
    return await db.capsules.find(
        {"resident_id": resident_id}, {"_id": 0, "audio_base64": 0, "audio_uri": 0}
    ).sort("recorded_at", -1).to_list(1000)


@api_router.get("/capsules/unclassified", response_model=List[CapsuleOut])
async def get_unclassified_capsules():
    return await db.capsules.find(
        {"status": "unclassified"}, {"_id": 0, "audio_base64": 0, "audio_uri": 0}
    ).sort("recorded_at", -1).to_list(1000)


@api_router.delete("/capsules/{capsule_id}")
async def delete_capsule(capsule_id: str):
    result = await db.capsules.delete_one({"id": capsule_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    return {"deleted": True}


@api_router.patch("/capsules/{capsule_id}/assign", response_model=CapsuleOut)
async def assign_capsule(capsule_id: str, resident_id: str):
    if not await db.residents.find_one({"id": resident_id}, {"_id": 0}):
        raise HTTPException(status_code=404, detail="Profil introuvable")
    doc = await db.capsules.find_one_and_update(
        {"id": capsule_id},
        {"$set": {"resident_id": resident_id, "status": "assigned", "classified_at": now_iso()}},
        return_document=True,
        projection={"_id": 0, "audio_base64": 0, "audio_uri": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    return doc


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()