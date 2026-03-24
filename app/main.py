from fastapi import FastAPI
from app.core.database import engine
from sqlalchemy import text
from app.api import employee
from app.api import auth


app = FastAPI()
app.include_router(employee.router)
app.include_router(auth.router)

@app.get("/")
def test_db():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return {"database_connection": "successful"}
