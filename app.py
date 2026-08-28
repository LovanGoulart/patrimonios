from flask import Flask, jsonify, request, render_template, redirect, url_for, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path
from datetime import datetime
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

BASE = Path(__file__).resolve().parent
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE / 'patrimonio.db'}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('PATRIMONIO_SECRET_KEY', 'patrimonio-pro-chave-trocar-em-producao')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
db = SQLAlchemy(app)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

class Equipamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(120), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(200), nullable=False)
    marca = db.Column(db.String(120), nullable=False)
    modelo = db.Column(db.String(120), default='')
    serie = db.Column(db.String(120), default='')
    categoria = db.Column(db.String(120), nullable=False)
    local = db.Column(db.String(200), nullable=False)
    responsavel = db.Column(db.String(200), nullable=False)
    data_aquisicao = db.Column(db.String(20), default='')
    valor = db.Column(db.String(40), default='')
    observacoes = db.Column(db.Text, default='')
    status = db.Column(db.String(30), default='ativo', index=True)
    baixa_json = db.Column(db.Text, default='')
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

class Manutencao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(db.Integer, db.ForeignKey('equipamento.id'), nullable=False, index=True)
    tipo = db.Column(db.String(30), nullable=False)
    data = db.Column(db.String(20), nullable=False)
    tecnico = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    custo = db.Column(db.String(40), default='')
    proxima_manutencao = db.Column(db.String(20), default='')
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)

class Historico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(db.Integer, nullable=False, index=True)
    acao = db.Column(db.String(40), nullable=False)
    detalhes = db.Column(db.Text, default='')
    data = db.Column(db.DateTime, default=datetime.utcnow)

def eq_json(e):
    import json
    baixa = json.loads(e.baixa_json) if e.baixa_json else None
    return dict(id=e.id, barcode=e.barcode, nome=e.nome, marca=e.marca, modelo=e.modelo or '', serie=e.serie or '', categoria=e.categoria,
                local=e.local, responsavel=e.responsavel, dataAquisicao=e.data_aquisicao or '', valor=e.valor or '', observacoes=e.observacoes or '', status=e.status, baixa=baixa,
                dataCadastro=e.data_cadastro.isoformat() if e.data_cadastro else '')

def maint_json(m):
    e = db.session.get(Equipamento, m.equipamento_id)
    return dict(id=m.id, equipamentoId=m.equipamento_id, equipamentoNome=e.nome if e else 'Equipamento removido', tipo=m.tipo, data=m.data,
                tecnico=m.tecnico, descricao=m.descricao, custo=m.custo or '', proximaManutencao=m.proxima_manutencao or '')

def hist_json(h):
    import json
    try: detalhes=json.loads(h.detalhes or '{}')
    except Exception: detalhes={}
    return dict(id=h.id, equipamentoId=h.equipamento_id, acao=h.acao, detalhes=detalhes, data=h.data.isoformat() if h.data else '')

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify(error='Não autenticado.', redirect=url_for('login')), 401
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('base_original.html', usuario=session.get('user_name', 'Usuário'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        usuario = Usuario.query.filter_by(email=email).first()
        if not usuario or not usuario.ativo or not check_password_hash(usuario.senha_hash, senha):
            error = 'E-mail ou senha inválidos.'
        else:
            session.clear()
            session['user_id'] = usuario.id
            session['user_name'] = usuario.nome
            session['user_email'] = usuario.email
            return redirect(url_for('index'))
    return render_template('auth.html', mode='login', error=error)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if 'user_id' in session:
        return redirect(url_for('index'))
    error = None
    values = {}
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        confirmar = request.form.get('confirmar_senha', '')
        values = {'nome': nome, 'email': email}
        if len(nome) < 2:
            error = 'Informe seu nome.'
        elif '@' not in email or len(email) < 5:
            error = 'Informe um e-mail válido.'
        elif len(senha) < 6:
            error = 'A senha deve ter pelo menos 6 caracteres.'
        elif senha != confirmar:
            error = 'As senhas não conferem.'
        elif Usuario.query.filter_by(email=email).first():
            error = 'Este e-mail já está cadastrado.'
        else:
            usuario = Usuario(nome=nome, email=email, senha_hash=generate_password_hash(senha))
            db.session.add(usuario)
            db.session.commit()
            session.clear()
            session['user_id'] = usuario.id
            session['user_name'] = usuario.nome
            session['user_email'] = usuario.email
            return redirect(url_for('index'))
    return render_template('auth.html', mode='cadastro', error=error, values=values)

@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.get('/manifest.webmanifest')
def manifest():
    return send_from_directory(app.static_folder, 'manifest.webmanifest')

@app.get('/service-worker.js')
def service_worker():
    return send_from_directory(app.static_folder, 'service-worker.js', mimetype='application/javascript')

@app.get('/api/bootstrap')
@login_required
def bootstrap():
    return jsonify(equipamentos=[eq_json(e) for e in Equipamento.query.order_by(Equipamento.id.desc()).all()],
                   manutencoes=[maint_json(m) for m in Manutencao.query.order_by(Manutencao.id.desc()).all()],
                   historico=[hist_json(h) for h in Historico.query.order_by(Historico.id.desc()).limit(100).all()])

@app.post('/api/equipamentos')
@login_required
def create_eq():
    import json
    d=request.get_json() or {}
    required=['barcode','nome','marca','categoria','local','responsavel']
    if any(not str(d.get(k,'')).strip() for k in required): return jsonify(error='Preencha os campos obrigatórios.'),400
    if Equipamento.query.filter_by(barcode=d['barcode'].strip()).first(): return jsonify(error='Já existe equipamento com este código.'),409
    e=Equipamento(barcode=d['barcode'].strip(),nome=d['nome'].strip(),marca=d['marca'].strip(),modelo=d.get('modelo','').strip(),serie=d.get('serie','').strip(),categoria=d['categoria'],local=d['local'].strip(),responsavel=d['responsavel'].strip(),data_aquisicao=d.get('dataAquisicao',''),valor=d.get('valor',''),observacoes=d.get('observacoes','').strip(),status='ativo')
    db.session.add(e); db.session.flush(); db.session.add(Historico(equipamento_id=e.id,acao='cadastro',detalhes=json.dumps({'nome':e.nome,'barcode':e.barcode},ensure_ascii=False))); db.session.commit()
    return jsonify(eq_json(e)),201

@app.put('/api/equipamentos/<int:eid>')
@login_required
def update_eq(eid):
    e=db.session.get(Equipamento,eid)
    if not e:return jsonify(error='Equipamento não encontrado.'),404
    d=request.get_json() or {}
    for field,key in [('nome','nome'),('marca','marca'),('modelo','modelo'),('serie','serie'),('categoria','categoria'),('local','local'),('responsavel','responsavel'),('data_aquisicao','dataAquisicao'),('valor','valor'),('observacoes','observacoes'),('status','status')]:
        if key in d: setattr(e,field,d[key])
    db.session.commit(); return jsonify(eq_json(e))

@app.post('/api/equipamentos/<int:eid>/manutencoes')
@login_required
def create_maint(eid):
    import json
    e=db.session.get(Equipamento,eid)
    if not e:return jsonify(error='Equipamento não encontrado.'),404
    d=request.get_json() or {}
    if not d.get('data') or not d.get('tecnico','').strip() or not d.get('descricao','').strip():return jsonify(error='Preencha os campos obrigatórios.'),400
    m=Manutencao(equipamento_id=eid,tipo=d.get('tipo','preventiva'),data=d['data'],tecnico=d['tecnico'].strip(),descricao=d['descricao'].strip(),custo=d.get('custo',''),proxima_manutencao=d.get('proximaManutencao',''))
    e.status='manutencao'; db.session.add(m); db.session.flush(); db.session.add(Historico(equipamento_id=eid,acao='manutencao',detalhes=json.dumps({'tipo':m.tipo,'tecnico':m.tecnico},ensure_ascii=False))); db.session.commit(); return jsonify(maint_json(m)),201

@app.post('/api/equipamentos/<int:eid>/baixa')
@login_required
def baixa(eid):
    import json
    e=db.session.get(Equipamento,eid)
    if not e:return jsonify(error='Equipamento não encontrado.'),404
    d=request.get_json() or {}
    if not d.get('motivo') or not d.get('data') or not d.get('responsavel','').strip():return jsonify(error='Preencha os campos obrigatórios.'),400
    e.status='baixado'; e.baixa_json=json.dumps({'motivo':d['motivo'],'data':d['data'],'responsavel':d['responsavel'].strip(),'observacoes':d.get('observacoes','').strip()},ensure_ascii=False)
    db.session.add(Historico(equipamento_id=eid,acao='baixa',detalhes=json.dumps({'motivo':d['motivo'],'responsavel':d['responsavel'].strip()},ensure_ascii=False))); db.session.commit(); return jsonify(eq_json(e))

@app.delete('/api/equipamentos/<int:eid>')
@login_required
def delete_eq(eid):
    e=db.session.get(Equipamento,eid)
    if not e:return jsonify(error='Não encontrado.'),404
    Manutencao.query.filter_by(equipamento_id=eid).delete(); Historico.query.filter_by(equipamento_id=eid).delete(); db.session.delete(e); db.session.commit(); return jsonify(ok=True)

@app.get('/api/equipamentos/<int:eid>')
@login_required
def get_eq(eid):
    e=db.session.get(Equipamento,eid)
    return (jsonify(equipamento=eq_json(e),manutencoes=[maint_json(m) for m in Manutencao.query.filter_by(equipamento_id=eid).all()],historico=[hist_json(h) for h in Historico.query.filter_by(equipamento_id=eid).order_by(Historico.id.desc()).all()]) if e else (jsonify(error='Não encontrado.'),404))

@app.get('/api/export')
@login_required
def export_csv():
    import csv, io
    out=io.StringIO(); w=csv.writer(out); w.writerow(['Código','Nome','Marca','Modelo','Categoria','Local','Responsável','Status','Data Aquisição','Valor'])
    for e in Equipamento.query.order_by(Equipamento.id).all():w.writerow([e.barcode,e.nome,e.marca,e.modelo,e.categoria,e.local,e.responsavel,e.status,e.data_aquisicao,e.valor])
    return app.response_class('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=patrimonio_equipamentos.csv'})

with app.app_context():
    db.create_all()
    if Equipamento.query.count() == 0:
        import json
        now=datetime.utcnow()
        demo=[
            Equipamento(barcode='PAT-2026-001',nome='Notebook Dell Latitude 5420',marca='Dell',modelo='Latitude 5420',serie='SN-DELL-001',categoria='Informática',local='TI - 3º Andar',responsavel='João Silva',data_aquisicao='2023-03-15',valor='4500,00',observacoes='Equipamento principal do setor de TI',status='ativo',data_cadastro=now),
            Equipamento(barcode='PAT-2026-002',nome='Impressora HP LaserJet Pro',marca='HP',modelo='M404dn',serie='SN-HP-002',categoria='Equipamentos de Escritório',local='Recepção',responsavel='Maria Oliveira',data_aquisicao='2023-06-20',valor='1800,00',status='ativo',data_cadastro=now),
            Equipamento(barcode='PAT-2026-003',nome='Monitor LG 27',marca='LG',modelo='27WN600-W',serie='SN-LG-003',categoria='Informática',local='Design',responsavel='Ana Costa',data_aquisicao='2023-09-10',valor='2200,00',status='manutencao',data_cadastro=now),
            Equipamento(barcode='PAT-2026-004',nome='Mesa de Escritório Executiva',marca='Tok&Stok',modelo='Executiva Premium',serie='SN-TK-004',categoria='Móveis',local='Diretoria',responsavel='Carlos Mendes',data_aquisicao='2022-11-05',valor='3200,00',status='baixado',data_cadastro=now,baixa_json=json.dumps({'motivo':'Obsolescência','data':'2026-02-01','responsavel':'Carlos Mendes','observacoes':''},ensure_ascii=False))]
        db.session.add_all(demo); db.session.flush()
        db.session.add_all([Historico(equipamento_id=demo[0].id,acao='cadastro',detalhes=json.dumps({'nome':demo[0].nome,'barcode':demo[0].barcode},ensure_ascii=False)), Historico(equipamento_id=demo[2].id,acao='manutencao',detalhes=json.dumps({'tipo':'corretiva','tecnico':'Lucas Reparos'},ensure_ascii=False)), Historico(equipamento_id=demo[3].id,acao='baixa',detalhes=json.dumps({'motivo':'Obsolescência','responsavel':'Carlos Mendes'},ensure_ascii=False))])
        db.session.add(Manutencao(equipamento_id=demo[2].id,tipo='corretiva',data='2026-02-20',tecnico='Lucas Reparos',descricao='Troca de painel e teste geral',custo='800,00'))
        db.session.commit()

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=True)
