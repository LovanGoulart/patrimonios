from flask import Flask, jsonify, request, render_template, redirect, url_for, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path
from datetime import datetime, timedelta
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

BASE = Path(__file__).resolve().parent
app = Flask(__name__, template_folder='templates', static_folder='static')
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
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

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
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    deleted_with_equipment = db.Column(db.Boolean, default=False, nullable=False)

class Historico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(db.Integer, nullable=False, index=True)
    acao = db.Column(db.String(40), nullable=False)
    detalhes = db.Column(db.Text, default='')
    data = db.Column(db.DateTime, default=datetime.utcnow)

def ensure_trash_columns():
    # Migração simples para bancos SQLite existentes.
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    for table, columns in {
        'equipamento': {'deleted_at': 'DATETIME'},
        'manutencao': {'deleted_at': 'DATETIME', 'deleted_with_equipment': 'BOOLEAN DEFAULT 0'}
    }.items():
        existing = {c['name'] for c in inspector.get_columns(table)} if inspector.has_table(table) else set()
        for name, typ in columns.items():
            if name not in existing:
                db.session.execute(db.text(f'ALTER TABLE {table} ADD COLUMN {name} {typ}'))
    db.session.commit()


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
    return redirect(url_for('login'))

@app.route('/sistema')
@login_required
def sistema():
    return render_template('base.html', usuario=session.get('user_name', 'Usuário'), is_admin=session.get('user_email') == 'admin@patrimonio.pro')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('sistema'))
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
            return redirect(url_for('sistema'))
    return render_template('auth.html', mode='login', error=error, values={})

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if 'user_id' in session:
        return redirect(url_for('sistema'))
    error = None
    values = {}
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        confirmar = request.form.get('confirmar_senha', '')
        values = {'nome': nome, 'email': email}
        if len(nome) < 2:
            error = 'Informe seu nome completo.'
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
            return redirect(url_for('sistema'))
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
    return jsonify(equipamentos=[eq_json(e) for e in Equipamento.query.filter(Equipamento.deleted_at.is_(None)).order_by(Equipamento.id.desc()).all()],
                   manutencoes=[maint_json(m) for m in Manutencao.query.filter(Manutencao.deleted_at.is_(None)).join(Equipamento, Manutencao.equipamento_id == Equipamento.id).filter(Equipamento.deleted_at.is_(None)).order_by(Manutencao.id.desc()).all()],
                   historico=[hist_json(h) for h in Historico.query.order_by(Historico.id.desc()).limit(100).all()])

@app.post('/api/equipamentos')
@login_required
def create_eq():
    import json
    d=request.get_json() or {}
    required=['barcode','nome','marca','categoria','local','responsavel']
    if any(not str(d.get(k,'')).strip() for k in required): return jsonify(error='Preencha os campos obrigatórios.'),400
    if Equipamento.query.filter(Equipamento.barcode == d['barcode'].strip(), Equipamento.deleted_at.is_(None)).first(): return jsonify(error='Já existe equipamento com este código.'),409
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
    db.session.add(m); db.session.flush(); db.session.add(Historico(equipamento_id=eid,acao='manutencao',detalhes=json.dumps({'tipo':m.tipo,'tecnico':m.tecnico},ensure_ascii=False))); db.session.commit(); return jsonify(maint_json(m)),201

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
    if not e or e.deleted_at is not None:return jsonify(error='Equipamento não encontrado.'),404
    agora=datetime.utcnow()
    e.deleted_at=agora
    # As manutenções são enviadas para a lixeira junto com o equipamento.
    Manutencao.query.filter_by(equipamento_id=eid).filter(Manutencao.deleted_at.is_(None)).update({
        'deleted_at': agora, 'deleted_with_equipment': True
    }, synchronize_session=False)
    db.session.commit()
    return jsonify(ok=True)

@app.delete('/api/manutencoes/<int:mid>')
@login_required
def delete_maint(mid):
    m=db.session.get(Manutencao,mid)
    if not m or m.deleted_at is not None:return jsonify(error='Manutenção não encontrada.'),404
    m.deleted_at=datetime.utcnow()
    m.deleted_with_equipment=False
    db.session.commit()
    return jsonify(ok=True, equipamentoId=m.equipamento_id)

@app.get('/api/lixeira')
@login_required
def trash():
    equipamentos=Equipamento.query.filter(Equipamento.deleted_at.isnot(None)).order_by(Equipamento.deleted_at.desc()).all()
    manutencoes=Manutencao.query.filter(Manutencao.deleted_at.isnot(None)).order_by(Manutencao.deleted_at.desc()).all()
    return jsonify(
        equipamentos=[dict(**eq_json(e), excluidoEm=e.deleted_at.isoformat() if e.deleted_at else '') for e in equipamentos],
        manutencoes=[dict(**maint_json(m), excluidoEm=m.deleted_at.isoformat() if m.deleted_at else '', excluidoComEquipamento=bool(m.deleted_with_equipment)) for m in manutencoes]
    )

@app.post('/api/lixeira/equipamentos/<int:eid>/restaurar')
@login_required
def restore_eq(eid):
    e=db.session.get(Equipamento,eid)
    if not e or e.deleted_at is None:return jsonify(error='Equipamento não encontrado na lixeira.'),404
    conflito=Equipamento.query.filter(Equipamento.barcode==e.barcode, Equipamento.id!=eid, Equipamento.deleted_at.is_(None)).first()
    if conflito:return jsonify(error=f'Não é possível restaurar: já existe um equipamento ativo com o código {e.barcode}.'),409
    e.deleted_at=None
    # Restaura apenas as manutenções que foram para a lixeira por causa deste equipamento.
    Manutencao.query.filter_by(equipamento_id=eid, deleted_with_equipment=True).update({
        'deleted_at': None, 'deleted_with_equipment': False
    }, synchronize_session=False)
    db.session.commit()
    return jsonify(ok=True)

@app.post('/api/lixeira/manutencoes/<int:mid>/restaurar')
@login_required
def restore_maint(mid):
    m=db.session.get(Manutencao,mid)
    if not m or m.deleted_at is None:return jsonify(error='Manutenção não encontrada na lixeira.'),404
    e=db.session.get(Equipamento,m.equipamento_id)
    if not e or e.deleted_at is not None:return jsonify(error='Restaure o equipamento vinculado antes desta manutenção.'),409
    m.deleted_at=None
    m.deleted_with_equipment=False
    db.session.commit()
    return jsonify(ok=True)

@app.delete('/api/lixeira/equipamentos/<int:eid>')
@login_required
def purge_eq(eid):
    e=db.session.get(Equipamento,eid)
    if not e or e.deleted_at is None:return jsonify(error='Equipamento não encontrado na lixeira.'),404
    Manutencao.query.filter_by(equipamento_id=eid).delete()
    Historico.query.filter_by(equipamento_id=eid).delete()
    db.session.delete(e)
    db.session.commit()
    return jsonify(ok=True)

@app.delete('/api/lixeira/manutencoes/<int:mid>')
@login_required
def purge_maint(mid):
    m=db.session.get(Manutencao,mid)
    if not m or m.deleted_at is None:return jsonify(error='Manutenção não encontrada na lixeira.'),404
    db.session.delete(m)
    db.session.commit()
    return jsonify(ok=True)


@app.get('/api/equipamentos/<int:eid>')
@login_required
def get_eq(eid):
    e=db.session.get(Equipamento,eid)
    if not e or e.deleted_at is not None: return jsonify(error='Não encontrado.'),404
    return jsonify(equipamento=eq_json(e),manutencoes=[maint_json(m) for m in Manutencao.query.filter_by(equipamento_id=eid).filter(Manutencao.deleted_at.is_(None)).all()],historico=[hist_json(h) for h in Historico.query.filter_by(equipamento_id=eid).order_by(Historico.id.desc()).all()])

@app.get('/api/export')
@login_required
def export_csv():
    import csv, io
    out=io.StringIO(); w=csv.writer(out); w.writerow(['Código','Nome','Marca','Modelo','Categoria','Local','Responsável','Status','Data Aquisição','Valor'])
    for e in Equipamento.query.filter(Equipamento.deleted_at.is_(None)).order_by(Equipamento.id).all():w.writerow([e.barcode,e.nome,e.marca,e.modelo,e.categoria,e.local,e.responsavel,e.status,e.data_aquisicao,e.valor])
    return app.response_class('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=patrimonio_equipamentos.csv'})

@app.get('/api/manutencoes/proximas')
@login_required
def manutencoes_proximas():
    from datetime import datetime, timedelta, timedelta
    hoje = datetime.now().date()
    amanha = hoje + timedelta(days=1)
    proximas = []
    for m in Manutencao.query.filter(Manutencao.proxima_manutencao != '', Manutencao.deleted_at.is_(None)).all():
        try:
            data_prox = datetime.strptime(m.proxima_manutencao, '%Y-%m-%d').date()
            if data_prox <= amanha:
                e = db.session.get(Equipamento, m.equipamento_id)
                proximas.append({
                    'id': m.id,
                    'equipamentoId': m.equipamento_id,
                    'equipamentoNome': e.nome if e else 'Equipamento removido',
                    'equipamentoBarcode': e.barcode if e else '',
                    'data': m.data,
                    'proximaManutencao': m.proxima_manutencao,
                    'tecnico': m.tecnico,
                    'tipo': m.tipo,
                    'diasRestantes': (data_prox - hoje).days
                })
        except ValueError:
            continue
    return jsonify(proximas=sorted(proximas, key=lambda x: x['diasRestantes']))

if __name__=='__main__':
    with app.app_context():
        db.create_all()
        ensure_trash_columns()
    app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=True)