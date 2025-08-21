from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import json
import hashlib
from functools import wraps
from datetime import datetime
import os # Importar o módulo os

app = Flask(__name__)
app.secret_key = 'turma_do_forno_secret_key'

# Função para carregar dados do JSON
def carregar_dados(arquivo):
    caminho_arquivo = f'database/{arquivo}.json'
    # Criar o diretório 'database' se não existir
    os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f: # Adicionar encoding='utf-8'
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Se o arquivo não existir ou estiver vazio/corrompido, retorna uma lista vazia e cria o arquivo
        with open(caminho_arquivo, 'w', encoding='utf-8') as f: # Adicionar encoding='utf-8'
            json.dump([], f, indent=4)
        return []

# Função para salvar dados no JSON
def salvar_dados(arquivo, dados):
    caminho_arquivo = f'database/{arquivo}.json'
    os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True) # Garantir que o diretório exista
    with open(caminho_arquivo, 'w', encoding='utf-8') as f: # Adicionar encoding='utf-8'
        json.dump(dados, f, indent=4)

# Função para inicializar os dados (chamada uma vez no início do app)
def inicializar_dados():
    # Dados iniciais para users
    users_data = carregar_dados('users')
    if not users_data: # Apenas inicializa se o arquivo estiver vazio
        usuarios_iniciais = [
            {
                'id': 1,
                'nome': 'Administrador Principal',
                'email': 'admin@admin.turma.do.forno',
                'senha': hashlib.sha256('admin123'.encode()).hexdigest(),
                'tipo': 'admin',
                'permissoes': ['gerenciar_usuarios', 'visualizar_estoque', 'alterar_estoque', 'realizar_vendas', 'cadastrar_produtos', 'visualizar_relatorios'],
                'data_criacao': datetime.now().strftime('%d/%m/%Y %H:%M')
            }
        ]
        salvar_dados('users', usuarios_iniciais)

    # Dados iniciais para produtos
    produtos_data = carregar_dados('produtos')
    if not produtos_data: # Apenas inicializa se o arquivo estiver vazio
        produtos_iniciais = [
            {'id': 1, 'nome': 'Pão Francês', 'preco': 0.50, 'quantidade': 5, 'categoria': 'Pães', 'estoque_minimo': 10},
            {'id': 2, 'nome': 'Bolo de Chocolate', 'preco': 15.00, 'quantidade': 3, 'categoria': 'Bolos', 'estoque_minimo': 5},
            {'id': 3, 'nome': 'Café', 'preco': 5.00, 'quantidade': 20, 'categoria': 'Bebidas', 'estoque_minimo': 15}
        ]
        salvar_dados('produtos', produtos_iniciais)

    # Garantir que os outros arquivos existam e estejam vazios se não houver dados
    carregar_dados('vendas') # Isso criará o arquivo se não existir
    carregar_dados('movimentacoes')
    carregar_dados('pontos')

# Chamar a função de inicialização quando o aplicativo for carregado
with app.app_context():
    inicializar_dados()

# Decorator para verificar login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator para verificar permissões específicas
def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            users = carregar_dados('users')
            user = next((u for u in users if u['id'] == session['user_id']), None)
            
            if user and permission in user['permissoes']:
                return f(*args, **kwargs)
            else:
                flash("Você não tem permissão para acessar esta página.", "error")
                return redirect(url_for('dashboard')) # Redirecionar para o dashboard ou outra página
        return decorated_function
    return decorator

# Context processor para disponibilizar funções nos templates
@app.context_processor
def utility_processor():
    def has_permission(permission):
        if 'user_permissoes' in session:
            return permission in session['user_permissoes']
        return False
    return dict(has_permission=has_permission, now=datetime.now)

# Rotas
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = hashlib.sha256(request.form['senha'].encode()).hexdigest()
        
        users = carregar_dados('users')
        user = next((u for u in users if u['email'] == email and u['senha'] == senha), None)
        
        if user:
            session['user_id'] = user['id']
            session['user_nome'] = user['nome']
            session['user_email'] = user['email']
            session['user_tipo'] = user['tipo']
            session['user_permissoes'] = user['permissoes']
            # Adicionar is_admin à sessão para uso no template base.html
            session['is_admin'] = (user['tipo'] == 'admin')
            return redirect(url_for('dashboard'))
        else:
            flash("Email ou senha inválidos", "error")
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/cadastro_cliente', methods=['GET', 'POST'])
def cadastro_cliente():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        cpf = request.form['cpf'].replace('.', '').replace('-', '')
        senha = hashlib.sha256(request.form['senha'].encode()).hexdigest()
        telefone = request.form['telefone']
        
        users = carregar_dados('users')
        
        # Verificar se email já existe
        if any(u['email'] == email for u in users):
            flash("Email já cadastrado", "error")
            return render_template('cadastro_cliente.html', nome=nome, email=email, cpf=cpf, telefone=telefone)
        
        # Verificar se CPF já existe
        if any(u.get('cpf') == cpf for u in users):
            flash("CPF já cadastrado", "error")
            return render_template('cadastro_cliente.html', nome=nome, email=email, cpf=cpf, telefone=telefone)
        
        novo_cliente = {
            'id': len(users) + 1,
            'nome': nome,
            'email': email,
            'cpf': cpf,
            'senha': senha,
            'telefone': telefone,
            'tipo': 'cliente',
            'permissoes': ['fazer_pedidos'],
            'data_criacao': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'pontos': 0
        }
        
        users.append(novo_cliente)
        salvar_dados('users', users)
        
        flash('Cadastro realizado com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('cadastro_cliente.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Você foi desconectado.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    produtos = carregar_dados('produtos')
    vendas = carregar_dados('vendas')
    users = carregar_dados('users')
    pontos = carregar_dados('pontos')
    
    # Verificar produtos com estoque baixo (exemplo, pode ser ajustado)
    produtos_estoque_baixo = [p for p in produtos if p['quantidade'] < p.get('estoque_minimo', 0)]
    
    return render_template('dashboard.html', 
                         produtos=produtos, 
                         vendas=vendas, 
                         users=users, 
                         pontos=pontos,
                         produtos_estoque_baixo=produtos_estoque_baixo)

@app.route('/gerenciar_usuarios')
@login_required
@permission_required('gerenciar_usuarios')
def gerenciar_usuarios():
    users = carregar_dados('users')
    return render_template('gerenciar_usuarios.html', users=users)

@app.route('/adicionar_usuario', methods=['POST'])
@login_required
@permission_required('gerenciar_usuarios')
def adicionar_usuario():
    nome = request.form['nome']
    email = request.form['email']
    senha = hashlib.sha256(request.form['senha'].encode()).hexdigest()
    tipo = request.form['tipo']
    
    # Definir permissões baseadas no tipo
    permissoes_map = {
        'rh': ['visualizar_estoque', 'visualizar_relatorios'],
        'pdv': ['realizar_vendas'],
        'estoquista': ['alterar_estoque'],
        'cadastrador': ['cadastrar_produtos'],
        'cliente': ['fazer_pedidos'],
        'admin': ['gerenciar_usuarios', 'visualizar_estoque', 'alterar_estoque', 'realizar_vendas', 'cadastrar_produtos', 'visualizar_relatorios']
    }
    
    users = carregar_dados('users')
    
    # Verificar se email já existe
    if any(u['email'] == email for u in users):
        flash("Email já cadastrado", "error")
        return render_template('gerenciar_usuarios.html', users=users)
    
    novo_user = {
        'id': len(users) + 1,
        'nome': nome,
        'email': email,
        'senha': senha,
        'tipo': tipo,
        'permissoes': permissoes_map.get(tipo, []), # Usar .get para evitar KeyError
        'data_criacao': datetime.now().strftime('%d/%m/%Y %H:%M')
    }
    
    users.append(novo_user)
    salvar_dados('users', users)
    flash(f"Usuário '{nome}' adicionado com sucesso!", "success")
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/excluir_usuario/<int:user_id>')
@login_required
@permission_required('gerenciar_usuarios')
def excluir_usuario(user_id):
    users = carregar_dados('users')
    
    # Não permitir excluir a si mesmo
    if user_id == session['user_id']:
        flash("Você não pode excluir sua própria conta.", "error")
        return redirect(url_for('gerenciar_usuarios'))
    
    # Não permitir excluir o admin principal
    admin_principal = next((u for u in users if u['email'] == 'admin@admin.turma.do.forno'), None)
    if admin_principal and user_id == admin_principal['id']:
        flash("Não é possível excluir o administrador principal.", "error")
        return redirect(url_for('gerenciar_usuarios'))
    
    user_removido = next((u for u in users if u['id'] == user_id), None)
    if user_removido:
        users = [u for u in users if u['id'] != user_id]
        salvar_dados('users', users)
        flash(f"Usuário '{user_removido['nome']}' excluído com sucesso!", "success")
    else:
        flash("Usuário não encontrado.", "error")
    
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/estoque')
@login_required
@permission_required('visualizar_estoque')
def estoque():
    produtos = carregar_dados('produtos')
    return render_template('estoque.html', produtos=produtos)

@app.route('/aumentar_estoque', methods=['POST'])
@login_required
@permission_required('alterar_estoque')
def aumentar_estoque():
    produto_id = int(request.form['produto_id'])
    quantidade_adicionar = int(request.form['quantidade'])
    data_movimentacao = request.form['data'] # Capturar a data do formulário
    
    produtos = carregar_dados('produtos')
    
    produto_encontrado = False
    for produto in produtos:
        if produto['id'] == produto_id:
            produto['quantidade'] += quantidade_adicionar
            produto_encontrado = True
            
            # Registrar movimentação
            movimentacoes = carregar_dados('movimentacoes')
            movimentacoes.append({
                'id': len(movimentacoes) + 1,
                'produto_id': produto_id,
                'produto_nome': produto['nome'],
                'quantidade': quantidade_adicionar,
                'tipo': 'entrada',
                'usuario': session['user_nome'],
                'data': data_movimentacao # Usar a data do formulário
            })
            
            salvar_dados('movimentacoes', movimentacoes)
            break
    
    salvar_dados('produtos', produtos)
    if produto_encontrado:
        flash(f"Estoque de '{produto['nome']}' aumentado em {quantidade_adicionar} unidades.", "success")
    else:
        flash("Produto não encontrado.", "error")
    return redirect(url_for('estoque'))

@app.route('/pdv')
@login_required
@permission_required('realizar_vendas')
def pdv():
    produtos = carregar_dados('produtos')
    return render_template('pdv.html', produtos=produtos)

@app.route('/processar_venda', methods=['POST'])
@login_required
@permission_required('realizar_vendas')
def processar_venda():
    data_venda = request.get_json()
    produtos_vendidos = data_venda['produtos']
    cpf_cliente = data_venda['cpfCliente']
    total = data_venda['total']
    
    # Atualizar estoque e registrar movimentações de saída
    produtos = carregar_dados('produtos')
    movimentacoes = carregar_dados('movimentacoes')
    
    for pv in produtos_vendidos:
        for produto in produtos:
            if produto['id'] == pv['id']:
                if produto['quantidade'] >= pv['quantidade']:
                    produto['quantidade'] -= pv['quantidade']
                    # Registrar movimentação de saída
                    movimentacoes.append({
                        'id': len(movimentacoes) + 1,
                        'produto_id': produto['id'],
                        'produto_nome': produto['nome'],
                        'quantidade': pv['quantidade'],
                        'tipo': 'saída',
                        'usuario': session['user_nome'],
                        'data': datetime.now().strftime('%d/%m/%Y %H:%M')
                    })
                else:
                    # Lidar com estoque insuficiente (opcional: retornar erro para o frontend)
                    print(f"Estoque insuficiente para {produto['nome']}")
                    # Você pode adicionar uma flash message aqui ou retornar um erro JSON
                    return jsonify({'success': False, 'message': f"Estoque insuficiente para {produto['nome']}"}), 400
                break
    
    # Registrar venda
    vendas = carregar_dados('vendas')
    nova_venda = {
        'id': len(vendas) + 1,
        'data': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'produtos': produtos_vendidos,
        'total': total,
        'vendedor': session['user_nome']
    }
    vendas.append(nova_venda)
    
    # Atualizar pontos se houver CPF
    if cpf_cliente:
        pontos = carregar_dados('pontos')
        # Remover formatação do CPF para comparação
        cpf_cliente_limpo = cpf_cliente.replace('.', '').replace('-', '')
        cliente_existente = next((p for p in pontos if p['cpf'] == cpf_cliente_limpo), None)
        
        pontos_ganhos = int(total) // 10  # 1 ponto a cada R$10,00
        
        if cliente_existente:
            cliente_existente['pontos'] += pontos_ganhos
        else:
            pontos.append({
                'cpf': cpf_cliente_limpo,
                'pontos': pontos_ganhos
            })
        
        salvar_dados('pontos', pontos)
    
    salvar_dados('produtos', produtos)
    salvar_dados('vendas', vendas)
    salvar_dados('movimentacoes', movimentacoes) # Salvar movimentações de saída
    
    return jsonify({'success': True, 'message': 'Venda realizada com sucesso!'})

@app.route('/cadastro_produto', methods=['GET', 'POST'])
@login_required
@permission_required('cadastrar_produtos')
def cadastro_produto():
    if request.method == 'POST':
        nome = request.form['nome']
        preco = float(request.form['preco'])
        quantidade = int(request.form['quantidade'])
        categoria = request.form['categoria']
        
        produtos = carregar_dados('produtos')
        
        # Verificar se o produto já existe pelo nome (opcional, mas boa prática)
        if any(p['nome'].lower() == nome.lower() for p in produtos):
            flash(f"Produto '{nome}' já cadastrado.", "error")
            return render_template('cadastro_produto.html', nome=nome, preco=preco, quantidade=quantidade, categoria=categoria)

        novo_produto = {
            'id': len(produtos) + 1,
            'nome': nome,
            'preco': preco,
            'quantidade': quantidade,
            'categoria': categoria,
            'estoque_minimo': 10  # Estoque mínimo padrão
        }
        
        produtos.append(novo_produto)
        salvar_dados('produtos', produtos)
        
        # Registrar movimentação de entrada inicial
        movimentacoes = carregar_dados('movimentacoes')
        movimentacoes.append({
            'id': len(movimentacoes) + 1,
            'produto_id': novo_produto['id'],
            'produto_nome': novo_produto['nome'],
            'quantidade': quantidade,
            'tipo': 'entrada_inicial',
            'usuario': session['user_nome'],
            'data': datetime.now().strftime('%d/%m/%Y %H:%M')
        })
        salvar_dados('movimentacoes', movimentacoes)

        flash(f"Produto '{nome}' cadastrado com sucesso!", "success")
        return redirect(url_for('estoque'))
    
    return render_template('cadastro_produto.html')

@app.route('/relatorios')
@login_required
@permission_required('visualizar_relatorios')
def relatorios():
    vendas = carregar_dados('vendas')
    movimentacoes = carregar_dados('movimentacoes')
    pontos = carregar_dados('pontos')
    return render_template('relatorios.html', vendas=vendas, movimentacoes=movimentacoes, pontos=pontos)

if __name__ == '__main__':
    # A função inicializar_dados já é chamada no escopo global.
    # Este bloco agora serve apenas para iniciar o servidor Flask.
    app.run(debug=True)
