from pydantic import BaseModel, HttpUrl, ConfigDict, Field, conlist
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
    fuentes: conlist(HttpUrl, min_length=1)

class RecursoImportacion(BaseModel):
    id_recurso: str
    nombre: Optional[str] = None
    nombre_grupo: Optional[str] = None
    fuentes: Optional[conlist(HttpUrl, min_length=1)] = None
    archivos: Optional[List[Archivo]] = None
    auth: Optional[Union[AuthBasic, AuthToken]] = None


    model_config = ConfigDict(extra='ignore')