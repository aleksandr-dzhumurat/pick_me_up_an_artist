from fastapi import FastAPI
from pydantic import BaseModel


from src.utils import ContentDB, UserDB

class Action(BaseModel):
    user_token: str
    user_name: str
    item_id: int
    action_type: str

class User(BaseModel):
    user_name: str

content_db = ContentDB()
content_db.init_db()
#
users_db = UserDB()
users_db.init_db()

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    item = content_db.get_content(item_id)
    return {"item": item}

@app.get("/random")
async def random_item():
    item_id = content_db.get_random_content_id()
    return {"item_id": item_id}

@app.post("/action")
async def action(action: Action):
    users_db.push_action(action.user_token, action.item_id, action.action_type)
    return {"result": "ok"}

@app.post("/auth")
async def auth(user: User):
    print(user.dict())
    bearer_token = users_db.create_user(user.user_name)
    return {"Bearer": bearer_token}
