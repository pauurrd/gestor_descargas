from pydantic import BaseModel, HttpUrl, ConfigDict, Field
from typing import List, Optional, Union, Literal

class AuthBasic(BaseModel):
    tipo: Literal["basic"]
    user: str
    password: str = Field(alias="pass")

class AuthToken(BaseModel):
    tipo: Literal["token"]
    token: str

class Archivo(BaseModel):
    nombre: str
    fuentes: List[HttpUrl]

class RecursoImportacion(BaseModel):
    id_recurso: str
    nombre: Optional[str] = None
    nombre_grupo: Optional[str] = None
    fuentes: Optional[List[HttpUrl]] = None
    archivos: Optional[List[Archivo]] = None
    auth: Optional[Union[AuthBasic, AuthToken]] = None

    # Esto cumple el requisito crítico de eliminar campos no definidos
    model_config = ConfigDict(extra='ignore')