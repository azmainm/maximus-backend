from pydantic import BaseModel
from typing import List

class UserCreate(BaseModel):
    full_name: str
    email: str
    username: str
    password: str
    
class UserLogin(BaseModel):
    username: str
    password: str
    userID: int

class ArticleCreate(BaseModel):
    title: str
    tldr: str
    content: str
    tags: List[str]

class ArticleResponse(BaseModel):
    id: int
    title: str
    tldr: str
    content: str
    user_id: int
    author_name: str
    tags: List[str]
    
    class Config:
        orm_mode = True

class FavoriteCheck(BaseModel):
    user_id: int
    article_id: int

class FavoriteToggle(BaseModel):
    user_id: int
    article_id: int

