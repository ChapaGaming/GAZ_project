from fastapi import FastAPI, File, UploadFile, HTTPException, staticfiles, Request, Query, Depends, Form
from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship, or_, and_
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.pool import QueuePool
from typing import Annotated
from sqlalchemy import func
import hashlib

#--------------------------#
# venv\Scripts\activate    #
#                          #  
# venv\Scripts\deactivate  #
#--------------------------#

app = FastAPI(debug=True)
# sqlmodel(pydantic)
class UserCatalogeLink(SQLModel, table = True):
    user_id:  int | None = Field(default=None, foreign_key="user.id", primary_key=True)
    product_id:  int | None = Field(default=None, foreign_key="cataloge.id", primary_key=True)

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    FIO: str
    email: str
    password: str
    seller: bool
    baskets: list["Cataloge"] = Relationship(back_populates="willings", link_model=UserCatalogeLink)#в " " так как питон интепритируемый и не увидет такого класса, а sqlalhemy увидит

class Cataloge(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    model: str = Field(index=True)
    color: str
    in_stage: bool
    cost: float
    buyer: str|None
    kind: str
    willings: list[User] = Relationship(back_populates="baskets", link_model=UserCatalogeLink)

# Указываем директорию для шаблонов

templates = Jinja2Templates(directory="templates")
app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")

# работа с SQL
def get_session(): #создание сессии
    with Session(engine) as session:
        yield session

sqlite_file_name = "db/database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False,}
engine = create_engine(sqlite_url, poolclass=QueuePool, pool_size=10, max_overflow=20, pool_recycle=3600, connect_args=connect_args)
SessionDep = Annotated[Session, Depends(get_session)]
# функции связанные с fastapi
def go_login(session,email):
    
    try:
        statement = select(User).where(User.email == email)
        user = len(session.exec(statement).all())
        if user == 1:
            return False
        else:
            return True
    except:
        return True
# функции не связанные с fastapi
def clear_db(db):
    with Session(engine) as session:
        results = session.exec(select(db)).all()
        for result in results:
            session.delete(result)
        session.commit()
def hashing(text):
    return hashlib.sha256(text.encode()).hexdigest()# текст кодируется по сиситеме sha256 и префращфется в 16-ричную систему

def create_db_and_tables():# обнуление/создание таблиц
    global engine
    SQLModel.metadata.create_all(engine)

def lifespan():
    create_db_and_tables()
# обработка запросов
@app.on_event("startup")
def on_start():
    create_db_and_tables()
@app.get("/",response_class=HTMLResponse)
def read_root(request: Request):
    req = {"request": request}
    return templates.TemplateResponse("login.html", req)

@app.post("/")
def read_root(session:SessionDep, request: Request, password: str|None = Form(...), email: str|None = Form(...)):
    hash_e =hashing(email)
    hash_pas = hashing(password)
    statement = select(User).where(User.email == hash_e).where(User.password == hash_pas)
    result = session.exec(statement)
    first = result.first()
    if not (first is None):
        return HTMLResponse(content=f"""<meta http-equiv="refresh" content="0.1; URL='/cataloge?email={hash_e}'" />""")
    return HTMLResponse(content=f'<h1 style = "color: red;">Пользователь не найден</h1>')

@app.get("/register",response_class=HTMLResponse)
def read_root(request: Request):
    req = {"request": request}
    return templates.TemplateResponse("register.html", req)

@app.post("/register",response_class=HTMLResponse)
def read_root(session: SessionDep, request: Request, FIO: str = Form(...), email: str = Form(...), password: str = Form(...), rep_password: str = Form(...)):
    if password == rep_password:
        try:
            hash_e = hashing(email)
            hash_pas = hashing(password)
            user = User(FIO = FIO, email = hash_e, password = hash_pas, basket = None, seller=False)
        except ValidationError as e:
            return e
        except Exception as e:
            return e
        email_query = select(User).where(User.email == hash_e)
        result = session.exec(email_query)
        first = result.first()
        if not (first is None):
            return HTMLResponse(content=f'<h1 style = "color: red;">Пользователь с такой почтой уже есть</h1>')
        session.add(user)
        session.commit()
        session.refresh(user)
        return HTMLResponse(content=f"""<h1 style = "color: green;">Успешно</h1>> <meta http-equiv="refresh" content="2; URL='/'" />""")
    return f'<h1 style = "color: red;">Пароли не совпадают</h1>'

@app.get("/basket/", response_class=HTMLResponse)
def read_root(session: SessionDep, request: Request, email:str|None, searching: str | None = None):
    if go_login(session,email):
        return HTMLResponse(content=f"""<meta http-equiv="refresh" content="0.001; URL='/'" />""")
    req = {
        "request": request,
        "searching":"",
        "email": email,
        "forms": [] # Устанавливаем production по умолчанию пустым списком
    }
    statement = select(User).where(User.email == email)
    user = session.exec(statement).one()
    if searching and searching.strip() and user:
        statement = select(Cataloge).where(Cataloge.model.like(f"%{searching.upper()}%"))
        alls = session.exec(statement).all()
        production = []
        for el in alls:
            if el in user.baskets:
                production.append(el)
        req["forms"] = production
        req["searching"] = searching
    else:
        statement = select(Cataloge)
        production = session.exec(statement).all()
        req["forms"] = user.baskets
    req["len"] = len(production)
    return templates.TemplateResponse("basket.html", req)

@app.get("/cataloge", response_class=HTMLResponse)
async def read_root(request: Request, session: SessionDep, email: str | None = None, searching: str | None = None):
    req = {
        "request": request,
        "email": email,
        "searching":"",
        "production": [] # Устанавливаем production по умолчанию пустым списком
    }
    if go_login(session,email):
        req["seller"] = False
    else:
        statement = select(User).where(User.email == email)
        user = session.exec(statement).one()
        req["seller"] = user.seller

    
    
    if searching and searching.strip():
        statement = select(Cataloge).where(Cataloge.model.like(f"%{searching.upper()}%"))
        production = session.exec(statement).all()
        req["production"] = production
        req["searching"] = searching
    else:
        statement = select(Cataloge)
        production = session.exec(statement).all()
        req["production"] = production
    return templates.TemplateResponse("cataloge.html", req)

@app.post("/cataloge", response_class=HTMLResponse)
def read_root(session: SessionDep,request: Request, email:str|None, buy_form: int = Form(...), searching: str | None = None):
    if go_login(session,email):
        return HTMLResponse(content=f"""<meta http-equiv="refresh" content="0.001; URL='/'" />""")
    id = buy_form
    product = session.get(Cataloge,id)
    scalar = select(User).where(User.email == email)
    result = session.exec(scalar)
    print("Пользаватель добавил объект в ожидание",product)
    if product.in_stage == False:
        return HTMLResponse(content='<h1 style = "color: red;">Уже в диллерском центре</h1>')
    user = result.first()
    if user in product.willings:
        return HTMLResponse(content='<h1 style = "color: red;">вы уже заказали</h1>')
    product.willings.append(user)
    session.add(product)
    session.commit()
    if not searching:
        searching=""
    return HTMLResponse(content=f"""<h1 style = "color: green;">Успешно</h1>> <meta http-equiv="refresh" content="0.5; URL='/cataloge?email={email}&searching={searching}'" />""")

@app.get("/accepter", response_class=HTMLResponse)
async def read_root(request: Request, session: SessionDep, email: str | None = None, searching: str | None = None):
    req = {
        "request": request,
        "email": email,
        "searching":"",
        "production": [] # Устанавливаем production по умолчанию пустым списком
    }
    if go_login(session,email):
        req["seller"] = False
    else:
        statement = select(User).where(User.email == email)
        user = session.exec(statement).one()
        req["seller"] = user.seller

    
    
    if searching and searching.strip():
        statement = select(Cataloge).where(Cataloge.model.like(f"%{searching.upper()}%")|Cataloge.in_stage == True)
        production = session.exec(statement).all()
        req["production"] = production
        req["searching"] = searching
    else:
        statement = select(Cataloge).where(Cataloge.in_stage == True)
        production = session.exec(statement).all()
        req["production"] = production
    return templates.TemplateResponse("accepter.html", req)

@app.post("/accepter", response_class=HTMLResponse)
def read_root(session: SessionDep,FIO_user: Annotated[str, Form()],request: Request, email:str|None, acc_form: Annotated[int, Form()], kind: Annotated[str, Form()],  searching: str | None = None):
    if go_login(session,email):
        return HTMLResponse(content=f"""<meta http-equiv="refresh" content="0.001; URL='/'" />""")
    print(kind)
    id = acc_form
    product = session.get(Cataloge,id)
    scalar = select(User).where(User.FIO == FIO_user)
    user = session.exec(scalar)
    user = user.first()
    print("Продавец одобрил товар:",product,user)
    product.buyer = user.FIO
    product.kind = kind
    session.add(product)
    session.commit()
    if not searching:
        searching=""
    return HTMLResponse(content=f"""<h1 style = "color: green;">Успешно</h1>> <meta http-equiv="refresh" content="0.5; URL='/accepter?email={email}&searching={searching}'" />""")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
