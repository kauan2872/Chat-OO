from flask import Flask, Response, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import UserMixin, LoginManager, login_user, logout_user, current_user
from functools import wraps
from abc import ABC, abstractmethod
from openai import OpenAI

app = Flask(__name__)
app.config.from_pyfile('config.py')
login = LoginManager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
client = OpenAI(api_key = '')

def perguntar(prompt):
    response = client.chat.completions.create(
    model="gpt-3.5-turbo-0125",
    response_format={ "type": "text" },
    messages=[
         {"role": "system", "content": "Responda fingindo ser professor de matemática, caso a pergunta não tenha a ver com a matéria, fale que não sabe e que é para perguntar para outro professor."},
         {"role": "user", "content": prompt}
          ]
    )
    return response.choices[0].message.content



@login.user_loader
def get_user(user_id):
    return Usuario.query.filter_by(id=user_id).first()

class Usuario(db.Model, UserMixin):  
    __tablename__ = "usuario"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String, unique=True)
    senha = db.Column(db.String)

def login_required_view(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function


class Command(ABC):
    @abstractmethod
    def execute(self):
        pass

class EnviarMensagemCommand(Command):
    def __init__(self, chat, nome, mensagem):
        self.chat = chat
        self.nome = nome
        self.mensagem = mensagem

    def execute(self):
        self.chat.adicionar_mensagem(self.nome, self.mensagem)

class AtualizarPerfilCommand(Command):
    def __init__(self, usuario, nova_senha):
        self.usuario = usuario
        self.nova_senha = nova_senha

    def execute(self):
        self.usuario.senha = self.nova_senha
        db.session.commit()

class DeletarPerfilCommand(Command):
    def __init__(self, usuario):
        self.usuario = usuario

    def execute(self):
        db.session.delete(self.usuario)
        db.session.commit()

class Chat:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Chat, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'mensagens'):
            self.mensagens = []

    def adicionar_mensagem(self, nome, mensagem):
        nova_mensagem = {"nome": nome, "mensagem": mensagem}
        self.mensagens.append(nova_mensagem)

    def enviar_mensagem(self, nome, mensagem):  
        command = EnviarMensagemCommand(self, nome, mensagem)  
        command.execute()

    def atualizar_perfil(self, usuario_id, nova_senha):
        usuario = Usuario.query.get(usuario_id)
        if usuario:
            command = AtualizarPerfilCommand(usuario, nova_senha)
            command.execute()

    def deletar_perfil(self, usuario_id):
        usuario = Usuario.query.get(usuario_id)
        if usuario:
            command = DeletarPerfilCommand(usuario)
            command.execute()

chat_instance = Chat()

############################### V I E W S ###################################

@app.route("/")
def index():
    return Response(render_template("login.html"), 200)

@app.route("/registro/")
def registro():
    return Response(render_template("registro.html"), 200)

@app.route("/validaRegistro/", methods=["POST"])
def validaRegistro():
    usuario = Usuario.query.filter_by(nome=request.form['nome']).first()
    if usuario is None:
        novo = Usuario(nome=request.form['nome'], senha=request.form['senha'])
        db.session.add(novo)
        db.session.commit()
        print("Deu certo")
        return redirect("/")
    else:
        print("Deu errado")
        return redirect('/registro/')

@app.route("/validaLogin/", methods=["POST"])
def validaLogin():
    usuario = Usuario.query.filter_by(nome=request.form["nome"]).first()
    if usuario is not None:
        if usuario.senha == request.form["senha"]:
            login_user(usuario)
            return redirect("/chat/")
    return redirect('/')

@app.route("/chat/")
@login_required_view
def chat():
    return Response(render_template("chat.html", mensagens=chat_instance.mensagens), 200)

@app.route("/enviar/", methods=["POST"])
@login_required_view
def enviar():
    chat2 = Chat()
    texto = request.form["mensagem"].lower()

    if "professor" in texto:
        chat_instance.enviar_mensagem(current_user.nome, request.form["mensagem"])
        chat_instance.enviar_mensagem("Professor Matemática", perguntar(request.form['mensagem']))
        return redirect("/chat/")
    
    chat2.enviar_mensagem(current_user.nome, request.form["mensagem"])  
    return redirect("/chat/")

@app.route("/atualizaUsuario/", methods=["POST"])
@login_required_view
def atualizaUsuario():
    chat_instance.atualizar_perfil(current_user.id, request.form['nova_senha'])
    return redirect("/chat/")

@app.route("/deletaUsuario/", methods=["POST"])
@login_required_view
def deletaUsuario():
    chat_instance.deletar_perfil(current_user.id)
    logout_user()
    return redirect("/")

@app.route('/logout/', methods=["POST"])
@login_required_view
def logout():
    logout_user()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
