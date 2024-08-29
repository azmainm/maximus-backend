
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timedelta
from . import models, schemas, db
from .db import get_db
from .models import User, Article, favorites
from .utils import verify_password, hash_password
from .schemas import ArticleCreate
from .db import engine
from .models import Base
from fastapi.security import OAuth2PasswordBearer
from typing import List
from .schemas import ArticleResponse  
from sqlalchemy import or_

app = FastAPI()
# router = APIRouter()

# Secret key for JWT encoding/decoding
SECRET_KEY = "bf54aa19e38de06204ba3af3ba99c208fbfb7176aa51eb2022673b0f4bd8cc04" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 scheme to retrieve token from the request header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

origins = [
    "https://maximus-lenb5z531-azmain-morsheds-projects.vercel.app",
    "https://maximus-phi.vercel.app",
    "https://maximus-14heromp1-azmain-morsheds-projects.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("CORS middleware added")



# Define the Pydantic model for the signup data
class SignUpModel(BaseModel):
    full_name: str
    email: str
    username: str
    password: str

# Pydantic model for login data
class LoginModel(BaseModel):
    username: str
    password: str

# Function to create access token (JWT)
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Signup route
@app.post("/signup/")
async def signup(signup_data: SignUpModel, db: Session = Depends(get_db)):
    # Check if the user already exists
    existing_user = db.query(User).filter((User.email == signup_data.email) | (User.username == signup_data.username)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email or username already registered")

    # Hash the password
    hashed_password = hash_password(signup_data.password)
    
    # Create a new user
    new_user = User(
        full_name=signup_data.full_name,
        email=signup_data.email,
        username=signup_data.username,
        hashed_password=hashed_password
    )
    
    # Save the new user to the database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created successfully", "user_id": new_user.id}

# Login route
@app.post("/login/")
async def login(login_data: LoginModel, db: Session = Depends(get_db)):
    # Fetch user from the database
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    
    # Verify the password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid username or password")
    
    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id  
    }



# Route to create an article
@app.post("/createpost/")
async def create_article(article_data: ArticleCreate, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # Extract user information from the token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create a new article object with the user ID and tags
    new_article = Article(
        title=article_data.title,
        tldr=article_data.tldr,
        content=article_data.content,
        user_id=user.id,
        tags=",".join(article_data.tags)  # Join tags as a comma-separated string
    )

    # Save the new article to the database
    db.add(new_article)
    db.commit()
    db.refresh(new_article)

    return {"message": "Article created successfully", "article_id": new_article.id}

@app.get("/article/", response_model=List[ArticleResponse])
async def get_articles(db: Session = Depends(get_db), tags: List[str] = Query(None), search_query: str = None):
    
    # Base query to join articles and users table
    query = db.query(
        Article.id,
        Article.title,
        Article.tldr,
        Article.content,
        Article.tags,
        Article.user_id,  
        User.full_name.label('author_name')
    ).join(User, Article.user_id == User.id)

    # If search query is provided, filter based on title, author, or tags
    if search_query:
        query = query.filter(
            or_(
                Article.title.ilike(f"%{search_query}%"),
                User.full_name.ilike(f"%{search_query}%"),
                Article.tags.ilike(f"%{search_query}%")
            )
        )

    # If tags are provided, filter the articles
    if tags:
        for tag in tags:
            query = query.filter(Article.tags.ilike(f"%{tag}%"))

    # Execute the query and fetch results
    articles = query.all()

    # Convert the query result to a list of dictionaries with the necessary fields
    article_list = [
        {
            "id": article.id,
            "title": article.title,
            "tldr": article.tldr,
            "content": article.content,
            "tags": article.tags.split(','),  # Convert tags from string to list
            "user_id": article.user_id,
            "author_name": article.author_name
        }
        for article in articles
    ]
    
    return article_list


@app.get("/article/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: Session = Depends(get_db)):
    # Join Article and User tables to get author_name and user_id
    article = db.query(
        Article.id,
        Article.title,
        Article.tldr,
        Article.content,
        Article.tags,
        Article.user_id,  
        User.full_name.label("author_name")
    ).join(User, Article.user_id == User.id).filter(Article.id == article_id).first()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Convert the article query result into a dictionary with the necessary fields
    article_data = {
        "id": article.id,
        "title": article.title,
        "tldr": article.tldr,
        "content": article.content,
        "tags": article.tags.split(','),  # Convert tags from string to list
        "user_id": article.user_id,  # Add user_id to the response
        "author_name": article.author_name
    }
    
    return article_data

@app.get("/profile/{user_id}")
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    # Fetch user details
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    
    # Count total articles by this user
    total_articles = db.query(Article).filter(Article.user_id == user_id).count()
    
    # Fetch all articles by this user
    articles = db.query(Article).filter(Article.user_id == user_id).all()
    

    
    return {
        "full_name": user.full_name,
        "email": user.email,
        "username": user.username,
        "total_articles": total_articles,
        "articles": [{"title": article.title, "tldr": article.tldr, "id": article.id} for article in articles],
        
    }


# Endpoint to check if an article is favorited by a user
@app.post("/is_favorited/")
async def is_favorited(data: schemas.FavoriteCheck, db: Session = Depends(get_db)):
    user_id = data.user_id
    article_id = data.article_id

    # Check if the article is favorited by the user
    is_favorited = db.query(favorites).filter(
        favorites.c.user_id == user_id,
        favorites.c.article_id == article_id
    ).first() is not None

    return {"is_favorited": is_favorited}

# Endpoint to add or remove an article from favorites
@app.post("/favorite/")
async def favorite(data: schemas.FavoriteToggle, db: Session = Depends(get_db)):
    user_id = data.user_id
    article_id = data.article_id

    # Check if the article is already favorited by the user
    is_favorited = db.query(favorites).filter(
        favorites.c.user_id == user_id,
        favorites.c.article_id == article_id
    ).first() is not None

    if is_favorited:
        # Remove the article from favorites
        db.query(favorites).filter(
            favorites.c.user_id == user_id,
            favorites.c.article_id == article_id
        ).delete()
    else:
        # Add the article to favorites
        db.execute(
            favorites.insert().values(user_id=user_id, article_id=article_id)
        )

    db.commit()

    return {"message": "Favorite status updated"}

@app.get("/favorite_articles/{user_id}")
def get_favorite_articles(user_id: int, db: Session = Depends(get_db)):
    # Fetch favorite articles for the user
    favorite_articles = db.query(Article).join(favorites).filter(favorites.c.user_id == user_id).all()

    return [{"title": article.title, "tldr": article.tldr, "id": article.id} for article in favorite_articles]

@app.delete("/delete_article/{article_id}")
def delete_article(article_id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # Extract user information from the token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch the article from the database
    article = db.query(Article).filter(Article.id == article_id).first()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    # Check if the user is the author of the article
    if article.user_id != user.id:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this article")

    # Delete the article from the database
    db.delete(article)
    db.commit()

    return {"message": "Article deleted successfully"}


# Create tables on app start
Base.metadata.create_all(bind=engine)

# Run the FastAPI application
if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
    # uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
