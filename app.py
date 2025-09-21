from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import json
import hashlib
from functools import wraps
from datetime import datetime
import os
from typing import Dict, List, Any
import traceback

app = Flask(__name__)
app.secret_key = 'turma_do_forno_secret_key_2025'

# Função para carregar dados do JSON
def carregar_dados(arquivo: str) -> List[Dict[str, Any]]:
    caminho_arquivo = f'database/{arquivo}.json'
    os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []

# Função para salvar dados no JSON
def salvar_dados(arquivo: str, dados: List[Dict[str, Any]]) -> None:
    caminho_arquivo = f'database/{arquivo}.json'
    os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# Decorator para verificar login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Detectar chamadas AJAX / Fetch e retornar JSON 401
            accepts = request.headers.get('Accept', '')
            is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in accepts

            if is_ajax:
                return jsonify({'success': False, 'message': 'login_required'}), 401

            flash("Faça login para acessar esta página.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator para verificar permissões
def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))

            users = carregar_dados('users')
            user = next((u for u in users if u['id'] == session['user_id']), None)

            # Admin tem acesso a tudo
            if user and user['tipo'] == 'admin':
                return f(*args, **kwargs)
            
            # Cliente só tem acesso à pré-venda
            if user and user['tipo'] == 'cliente':
                if f.__name__ == 'pre_venda':
                    return f(*args, **kwargs)
                else:
                    flash("Acesso restrito. Clientes só podem acessar a área de compras.", "error")
                    return redirect(url_for('pre_venda'))
            
            # Outros usuários verificam permissões específicas
            if user and permission in user.get('permissoes', []):
                return f(*args, **kwargs)
            else:
                flash("Você não tem permissão para acessar esta página.", "error")
                return redirect(url_for('dashboard'))
        return decorated_function
    return decorator

# Context processor para disponibilizar funções nos templates
@app.context_processor
def utility_processor():
    def has_permission(permission):
        if 'user_permissoes' in session:
            return permission in session['user_permissoes']
        return False
    
    def format_currency(value):
        return f"R$ {value:.2f}"
    
    return dict(has_permission=has_permission, now=datetime.now, format_currency=format_currency)

# ============= FUNÇÃO DE MIGRAÇÃO DE STATUS =============

def migrar_status_pedidos():
    """Migra os status antigos dos pedidos para o novo formato"""
    try:
        pedidos = carregar_dados('pedidos')
        
        pedidos_modificados = False
        for pedido in pedidos:
            if 'status' not in pedido or isinstance(pedido['status'], str):
                pedidos_modificados = True
                if pedido.get('status') == 'Entregue':
                    pedido['status'] = {'entregue': True, 'pago': False}
                elif pedido.get('status') == 'Pago':
                    pedido['status'] = {'entregue': False, 'pago': True}
                else:
                    pedido['status'] = {'entregue': False, 'pago': False}
        
        if pedidos_modificados:
            salvar_dados('pedidos', pedidos)
            print("✅ Migração de status concluída com sucesso!")
        else:
            print("✅ Nenhuma migração necessária - status já estão atualizados")
            
    except Exception as e:
        print(f"❌ Erro na migração: {e}")

# ============= ROTA PARA MIGRAÇÃO MANUAL =============

@app.route('/migrar_status')
@login_required
@permission_required('visualizar_relatorios')
def migrar_status():
    """Rota para executar la migração manualmente"""
    try:
        migrar_status_pedidos()
        flash('Migração de status realizada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro na migración: {str(e)}', 'error')
    
    return redirect(url_for('relatorios_vendas_online'))

# ============= ROTAS PRINCIPAIS =============

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
            session['is_admin'] = (user['tipo'] == 'admin')
            
            flash(f"Bem-vindo, {user['nome']}!", "success")
            
            # Redirecionar para dashboard
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

        if any(u['email'] == email for u in users):
            flash("Email já cadastrado", "error")
            return render_template('cadastro_cliente.html', nome=nome, email=email, cpf=cpf, telefone=telefone)

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
            'data_criacao': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
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
    # Se for cliente, redirecionar para pré-venda
    if session.get('user_tipo') == 'cliente':
        return redirect(url_for('pre_venda'))
    
    produtos = carregar_dados('produtos')
    vendas = carregar_dados('vendas')
    users = carregar_dados('users')
    pontos = carregar_dados('pontos')
    pedidos = carregar_dados('pedidos')

    # Estatísticas
    total_vendas = sum(venda['total'] for venda in vendas) if vendas else 0
    total_produtos = len(produtos)
    total_usuarios = len(users)
    produtos_estoque_baixo = [p for p in produtos if p['quantidade'] < p.get('estoque_minimo', 0)]

    return render_template('dashboard.html',
                         produtos=produtos,
                         vendas=vendas,
                         users=users,
                         pontos=pontos,
                         pedidos=pedidos,
                         produtos_estoque_baixo=produtos_estoque_baixo,
                         total_vendas=total_vendas,
                         total_produtos=total_produtos,
                         total_usuarios=total_usuarios)
# ============= GERENCIAMENTO DE USUÁRIOS =============

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

    permissoes_map = {
        'rh': ['visualizar_estoque', 'visualizar_relatorios'],
        'pdv': ['realizar_vendas'],
        'estoquista': ['alterar_estoque'],
        'cadastrador': ['cadastrar_produtos'],
        'cliente': ['fazer_pedidos'],
        'admin': ['gerenciar_usuarios', 'visualizar_estoque', 'alterar_estoque', 'realizar_vendas', 'cadastrar_produtos', 'visualizar_relatorios', 'gerenciar_pre_vendas']
    }

    users = carregar_dados('users')

    if any(u['email'] == email for u in users):
        flash("Email já cadastrado", "error")
        return redirect(url_for('gerenciar_usuarios'))

    novo_user = {
        'id': len(users) + 1,
        'nome': nome,
        'email': email,
        'senha': senha,
        'tipo': tipo,
        'permissoes': permissoes_map.get(tipo, []),
        'data_criacao': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
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

    if user_id == session['user_id']:
        flash("Você não pode excluir sua própria conta.", "error")
        return redirect(url_for('gerenciar_usuarios'))

    admin_principal = next((u for u in users if u['email'] == 'pietro@admin.turma.do.forno'), None)
    if admin_principal and user_id == admin_principal['id']:
        flash("Não é possível excluir o administrador principal.", "error")
        return redirect(url_for('gerenciar_usuarios'))
    
    admin_principal = next((u for u in users if u['email'] == 'francesco@admin.turma.do.forno'), None)
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

# ============= ESTOQUE =============

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
    produto_id = int(request.form.get('produto_id', 0))
    quantidade_adicionar = int(request.form.get('quantidade', 0))
    data_movimentacao = request.form.get('data', datetime.now().strftime('%d/%m/%Y'))

    if produto_id == 0 or quantidade_adicionar == 0:
        flash("Dados inválidos para aumentar estoque.", "error")
        return redirect(url_for('estoque'))

    produtos = carregar_dados('produtos')
    movimentacoes = carregar_dados('movimentacoes')

    produto_encontrado = None
    for produto in produtos:
        if produto['id'] == produto_id:
            produto['quantidade'] += quantidade_adicionar
            produto_encontrado = produto

            # Registrar movimentação
            movimentacoes.append({
                'id': len(movimentacoes) + 1,
                'produto_id': produto_id,
                'produto_nome': produto['nome'],
                'quantidade': quantidade_adicionar,
                'tipo': 'entrada',
                'usuario': session['user_nome'],
                'data': data_movimentacao
            })
            break

    if produto_encontrado:
        salvar_dados('produtos', produtos)
        salvar_dados('movimentacoes', movimentacoes)
        flash(f"Estoque de '{produto_encontrado['nome']}' aumentado em {quantidade_adicionar} unidades.", "success")
    else:
        flash("Produto não encontrado.", "error")
    
    return redirect(url_for('estoque'))

@app.route('/excluir_produto/<int:produto_id>')
@login_required
@permission_required('alterar_estoque')
def excluir_produto(produto_id):
    produtos = carregar_dados('produtos')
    
    produto_removido = next((p for p in produtos if p['id'] == produto_id), None)
    if produto_removido:
        # Registrar movimentação de exclusão
        movimentacoes = carregar_dados('movimentacoes')
        movimentacoes.append({
            'id': len(movimentacoes) + 1,
            'produto_id': produto_id,
            'produto_nome': produto_removido['nome'],
            'quantidade': produto_removido['quantidade'],
            'tipo': 'exclusao',
            'usuario': session['user_nome'],
            'data': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        })
        salvar_dados('movimentacoes', movimentacoes)
        
        # Remover produto
        produtos = [p for p in produtos if p['id'] != produto_id]
        salvar_dados('produtos', produtos)
        
        flash(f"Produto '{produto_removido['nome']}' excluído com sucesso!", "success")
    else:
        flash("Produto não encontrado.", "error")
    
    return redirect(url_for('estoque'))

@app.route('/cadastro_produto', methods=['GET', 'POST'])
@login_required
@permission_required('cadastrar_produtos')
def cadastro_produto():
    if request.method == 'POST':
        nome = request.form['nome']
        preco = float(request.form['preco'])
        quantidade = int(request.form['quantidade'])
        categoria = request.form['categoria']
        estoque_minimo = int(request.form.get('estoque_minimo', 10))

        produtos = carregar_dados('produtos')

        if any(p['nome'].lower() == nome.lower() for p in produtos):
            flash(f"Produto '{nome}' já cadastrado.", "error")
            return render_template('cadastro_produto.html', nome=nome, preco=preco, quantidade=quantidade, categoria=categoria)

        novo_produto = {
            'id': len(produtos) + 1,
            'nome': nome,
            'preco': preco,
            'quantidade': quantidade,
            'categoria': categoria,
            'estoque_minimo': estoque_minimo
        }

        produtos.append(novo_produto)
        salvar_dados('produtos', produtos)

        movimentacoes = carregar_dados('movimentacoes')
        movimentacoes.append({
            'id': len(movimentacoes) + 1,
            'produto_id': novo_produto['id'],
            'produto_nome': novo_produto['nome'],
            'quantidade': quantidade,
            'tipo': 'entrada_inicial',
            'usuario': session['user_nome'],
            'data': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        })
        salvar_dados('movimentacoes', movimentacoes)

        flash(f"Produto '{nome}' cadastrado com sucesso!", "success")
        return redirect(url_for('estoque'))

    return render_template('cadastro_produto.html')

# ============= PDV =============

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
    try:
        data_venda = request.get_json()
        produtos_vendidos = data_venda['produtos']
        cpf_cliente = data_venda.get('cpfCliente', '')
        total = data_venda['total']

        produtos = carregar_dados('produtos')
        movimentacoes = carregar_dados('movimentacoes')

        for pv in produtos_vendidos:
            for produto in produtos:
                if produto['id'] == pv['id']:
                    if produto['quantidade'] >= pv['quantidade']:
                        produto['quantidade'] -= pv['quantidade']
                        movimentacoes.append({
                            'id': len(movimentacoes) + 1,
                            'produto_id': produto['id'],
                            'produto_nome': produto['nome'],
                            'quantidade': pv['quantidade'],
                            'tipo': 'saída',
                            'usuario': session['user_nome'],
                            'data': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                        })
                    else:
                        return jsonify({'success': False, 'message': f"Estoque insuficiente para {produto['nome']}"}), 400
                    break

        vendas = carregar_dados('vendas')
        nova_venda = {
            'id': len(vendas) + 1,
            'data': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'produtos': produtos_vendidos,
            'total': total,
            'vendedor': session['user_nome'],
            'cpf_cliente': cpf_cliente
        }
        vendas.append(nova_venda)

        if cpf_cliente:
            pontos = carregar_dados('pontos')
            cpf_cliente_limpo = cpf_cliente.replace('.', '').replace('-', '')
            cliente_existente = next((p for p in pontos if p['cpf'] == cpf_cliente_limpo), None)

            pontos_ganhos = int(total) // 10

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
        salvar_dados('movimentacoes', movimentacoes)

        return jsonify({'success': True, 'message': 'Venda realizada com sucesso!'})

    except Exception as e:
        print(f"Erro ao processar venda: {str(e)}")
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'}), 500

# ============= PRÉ-VENDAS =============

@app.route('/pre_venda')
@login_required
def pre_venda():
    users = carregar_dados('users')
    user = next((u for u in users if u['id'] == session['user_id']), None)
    
    if user and user['tipo'] != 'admin' and 'fazer_pedidos' not in user.get('permissoes', []):
        flash("Acesso não autorizado.", "error")
        return redirect(url_for('dashboard'))
    
    produtos = carregar_dados('produtos')
    pre_vendas = carregar_dados('pre_vendas')
    
    pre_venda_ativa = None
    for pv in pre_vendas:
        if pv.get('ativa', False):
            try:
                data_inicio = datetime.strptime(pv['data_inicio'], '%d/%m/%Y')
                data_fim = datetime.strptime(pv['data_fim'], '%d/%m/%Y')
                data_atual = datetime.now()
                
                if data_inicio <= data_atual <= data_fim:
                    pre_venda_ativa = pv
                    break
            except:
                continue
    
    return render_template('pre_venda.html', 
                         produtos=produtos, 
                         pre_venda_ativa=pre_venda_ativa)

@app.route('/processar_pedido_cliente', methods=['POST'])
@login_required
def processar_pedido_cliente():
    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400

        # Verificar se há pré-venda ativa com desconto
        pre_vendas = carregar_dados('pre_vendas')
        pre_venda_ativa = None
        for pv in pre_vendas:
            if pv.get('ativa', False):
                try:
                    data_inicio = datetime.strptime(pv['data_inicio'], '%d/%m/%Y')
                    data_fim = datetime.strptime(pv['data_fim'], '%d/%m/%Y')
                    data_atual = datetime.now()
                    
                    if data_inicio <= data_atual <= data_fim:
                        pre_venda_ativa = pv
                        break
                except:
                    continue
        
        # Aplicar desconto se for uma pré-venda
        produtos_com_desconto = []
        desconto = pre_venda_ativa.get('desconto_geral', 0) if pre_venda_ativa and data.get('tipo_pedido') == 'pre_venda' else 0
        
        for produto in data['produtos']:
            preco_original = produto['preco']
            preco_com_desconto = preco_original * (1 - desconto / 100)
            produtos_com_desconto.append({
                'id': produto['id'],
                'nome': produto['nome'],
                'preco': preco_com_desconto,
                'quantidade': produto['quantidade']
            })
        
        # Calcular total com desconto
        total_com_desconto = sum(p['preco'] * p['quantidade'] for p in produtos_com_desconto)

        # 🔹 Carregar lista de pedidos e produtos do JSON
        pedidos = carregar_dados('pedidos')
        produtos = carregar_dados('produtos')
        movimentacoes = carregar_dados('movimentacoes')
        vendas = carregar_dados('vendas')

        # Verificar estoque e reduzir quantidades
        for produto_pedido in data['produtos']:
            produto_id = produto_pedido['id']
            quantidade_pedido = produto_pedido['quantidade']
            
            # Encontrar o produto no estoque
            produto_estoque = next((p for p in produtos if p['id'] == produto_id), None)
            
            if produto_estoque:
                if produto_estoque['quantidade'] >= quantidade_pedido:
                    # Reduzir estoque
                    produto_estoque['quantidade'] -= quantidade_pedido
                    
                    # Registrar movimentação de saída
                    movimentacoes.append({
                        'id': len(movimentacoes) + 1,
                        'produto_id': produto_id,
                        'produto_nome': produto_estoque['nome'],
                        'quantidade': quantidade_pedido,
                        'tipo': 'saída',
                        'usuario': session['user_nome'],
                        'data': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                        'observacao': 'Pedido online - ' + ('Pré-venda' if data.get('tipo_pedido') == 'pre_venda' else 'Compra Imediata')
                    })
                else:
                    return jsonify({
                        'success': False, 
                        'message': f"Estoque insuficiente para {produto_estoque['nome']}. Disponível: {produto_estoque['quantidade']}, Solicitado: {quantidade_pedido}"
                    }), 400
            else:
                return jsonify({
                    'success': False, 
                    'message': f"Produto ID {produto_id} não encontrado no estoque"
                }), 400

        user_id = session['user_id']
        user_nome = session['user_nome']

        # Se for compra imediata, registrar como venda normal
        if data.get('tipo_pedido') == 'imediato':
            # Registrar como venda normal
            nova_venda = {
                'id': len(vendas) + 1,
                'data': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'produtos': produtos_com_desconto,
                'total': total_com_desconto,
                'vendedor': user_nome + ' (Online)',
                'cliente_id': user_id,
                'cliente_nome': user_nome,
                'tipo': 'online'
            }
            vendas.append(nova_venda)
            
            # Também registrar como pedido para histórico
            novo_pedido = {
                'id': len(pedidos) + 1,
                'cliente_id': user_id,
                'cliente_nome': user_nome,
                'produtos': produtos_com_desconto,
                'metodo_pagamento': data['metodo_pagamento'],
                'tipo_pedido': data['tipo_pedido'],
                'total': total_com_desconto,
                'status': {'entregue': True, 'pago': True},
                'data': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'desconto_aplicado': desconto,
                'data_entrega': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'data_pagamento': datetime.now().strftime('%d/%m/%Y %H:%M')
            }
            pedidos.append(novo_pedido)
            
            mensagem_sucesso = 'Compra realizada com sucesso! O estoque foi atualizado.'
            
        else:
            # Se for pré-venda, registrar apenas como pedido
            novo_pedido = {
                'id': len(pedidos) + 1,
                'cliente_id': user_id,
                'cliente_nome': user_nome,
                'produtos': produtos_com_desconto,
                'metodo_pagamento': data['metodo_pagamento'],
                'tipo_pedido': data['tipo_pedido'],
                'total': total_com_desconto,
                'status': {'entregue': False, 'pago': False},
                'data': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'desconto_aplicado': desconto
            }
            pedidos.append(novo_pedido)
            
            mensagem_sucesso = 'Pedido de pré-venda realizado com sucesso! O estoque foi atualizado.'

        # Salvar todos os dados atualizados
        salvar_dados('pedidos', pedidos)
        salvar_dados('produtos', produtos)
        salvar_dados('movimentacoes', movimentacoes)
        salvar_dados('vendas', vendas)

        return jsonify({'success': True, 'message': mensagem_sucesso})

    except Exception as e:
        print(f"❌ Erro ao processar pedido cliente: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/criar_pre_venda', methods=['POST'])
@login_required
@permission_required('gerenciar_pre_vendas')
def criar_pre_venda():
    data_inicio = request.form['data_inicio']
    data_fim = request.form['data_fim']
    desconto_geral = float(request.form.get('desconto_geral', 0))
    
    if not data_inicio or not data_fim:
        flash("Data de início e data de término são obrigatórias.", "error")
        return redirect(url_for('gerenciar_pre_vendas'))
    
    try:
        # Converter para objeto datetime para validação
        data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
        data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d')
        
        # Verificar se data fim é maior que data início
        if data_fim_dt <= data_inicio_dt:
            flash("A data de término deve ser posterior à data de início.", "error")
            return redirect(url_for('gerenciar_pre_vendas'))
            
        # Verificar se data início não é no passado
        if data_inicio_dt < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            flash("A data de início não pode ser no passado.", "error")
            return redirect(url_for('gerenciar_pre_vendas'))
            
    except ValueError:
        flash("Datas inválidas. Use o formato correto.", "error")
        return redirect(url_for('gerenciar_pre_vendas'))
    
    # Converter para formato brasileiro
    data_inicio_br = data_inicio_dt.strftime('%d/%m/%Y')
    data_fim_br = data_fim_dt.strftime('%d/%m/%Y')
    
    pre_vendas = carregar_dados('pre_vendas')
    
    # Desativar todas as pré-vendas existentes
    for pv in pre_vendas:
        pv['ativa'] = False
    
    # Criar nova pré-venda
    nova_pre_venda = {
        'id': len(pre_vendas) + 1,
        'data_inicio': data_inicio_br,
        'data_fim': data_fim_br,
        'desconto_geral': desconto_geral,
        'ativa': True,
        'criada_por': session['user_nome'],
        'data_criacao': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        'pedidos': []
    }
    
    pre_vendas.append(nova_pre_venda)
    salvar_dados('pre_vendas', pre_vendas)
    
    flash(f"Pré-venda criada com sucesso! De {data_inicio_br} a {data_fim_br} com {desconto_geral}% de desconto", "success")
    return redirect(url_for('gerenciar_pre_vendas'))

@app.route('/verificar_estoque', methods=['POST'])
@login_required
def verificar_estoque():
    try:
        data = request.get_json()
        produto_id = data.get('produto_id')
        quantidade = data.get('quantidade', 1)
        
        produtos = carregar_dados('produtos')
        produto = next((p for p in produtos if p['id'] == produto_id), None)
        
        if produto:
            disponivel = produto['quantidade'] >= quantidade
            return jsonify({
                'disponivel': disponivel,
                'estoque_atual': produto['quantidade'],
                'quantidade_solicitada': quantidade
            })
        else:
            return jsonify({'disponivel': False, 'erro': 'Produto não encontrado'}), 404
            
    except Exception as e:
        return jsonify({'disponivel': False, 'erro': str(e)}), 500

@app.route('/gerenciar_pre_vendas')
@login_required
@permission_required('gerenciar_pre_vendas')
def gerenciar_pre_vendas():
    pre_vendas = carregar_dados('pre_vendas')
    # Ordenar por data de criação (mais recente primeiro)
    pre_vendas.sort(key=lambda x: x.get('data_criacao', ''), reverse=True)
    return render_template('gerenciar_pre_vendas.html', pre_vendas=pre_vendas)

@app.route('/desativar_pre_venda/<int:pre_venda_id>', methods=['POST'])
@login_required
@permission_required('gerenciar_pre_vendas')
def desativar_pre_venda(pre_venda_id):
    pre_vendas = carregar_dados('pre_vendas')
    
    for pv in pre_vendas:
        if pv['id'] == pre_venda_id:
            pv['ativa'] = False
            break
    
    salvar_dados('pre_vendas', pre_vendas)
    flash("Pré-venda desativada com sucesso!", "success")
    return redirect(url_for('gerenciar_pre_vendas'))

@app.route('/ativar_pre_venda/<int:pre_venda_id>', methods=['POST'])
@login_required
@permission_required('gerenciar_pre_vendas')
def ativar_pre_venda(pre_venda_id):
    pre_vendas = carregar_dados('pre_vendas')
    
    # Desativar todas as outras pré-vendas primeiro
    for pv in pre_vendas:
        pv['ativa'] = False
    
    # Ativar a pré-venda específica
    for pv in pre_vendas:
        if pv['id'] == pre_venda_id:
            pv['ativa'] = True
            break
    
    salvar_dados('pre_vendas', pre_vendas)
    flash("Pré-venda ativada com sucesso!", "success")
    return redirect(url_for('gerenciar_pre_vendas'))

@app.route('/excluir_pre_venda/<int:pre_venda_id>', methods=['POST'])
@login_required
@permission_required('gerenciar_pre_vendas')
def excluir_pre_venda(pre_venda_id):
    pre_vendas = carregar_dados('pre_vendas')
    pre_vendas = [pv for pv in pre_vendas if pv['id'] != pre_venda_id]
    
    salvar_dados('pre_vendas', pre_vendas)
    flash("Pré-venda excluída com sucesso!", "success")
    return redirect(url_for('gerenciar_pre_vendas'))

# ============= ATUALIZAR STATUS DE PEDIDOS =============

@app.route('/atualizar_status_pedido/<int:pedido_id>', methods=['POST'])
@login_required
@permission_required('visualizar_relatorios')
def atualizar_status_pedido(pedido_id):
    try:
        action = request.form.get('action')
        
        pedidos = carregar_dados('pedidos')
        
        for pedido in pedidos:
            if pedido['id'] == pedido_id:
                # Inicializar status se não existir
                if 'status' not in pedido:
                    pedido['status'] = {'entregue': False, 'pago': False}
                
                # Garantir que status seja um dicionário
                if isinstance(pedido['status'], str):
                    # Converter status antigo para novo formato
                    if pedido['status'] == 'Entregue':
                        pedido['status'] = {'entregue': True, 'pago': False}
                    elif pedido['status'] == 'Pago':
                        pedido['status'] = {'entregue': False, 'pago': True}
                    elif pedido['status'] == 'Pendente':
                        pedido['status'] = {'entregue': False, 'pago': False}
                
                # Atualizar status baseado na ação
                if action == 'toggle_entrega':
                    pedido['status']['entregue'] = not pedido['status']['entregue']
                    if pedido['status']['entregue']:
                        pedido['data_entrega'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                    elif 'data_entrega' in pedido:
                        del pedido['data_entrega']
                
                elif action == 'toggle_pagamento':
                    pedido['status']['pago'] = not pedido['status']['pago']
                    if pedido['status']['pago']:
                        pedido['data_pagamento'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                    elif 'data_pagamento' in pedido:
                        del pedido['data_pagamento']
                
                break
        
        salvar_dados('pedidos', pedidos)
        flash('Status do pedido atualizado com sucesso!', 'success')
        
    except Exception as e:
        flash(f'Erro ao atualizar status: {str(e)}', 'error')
    
    return redirect(url_for('relatorios_vendas_online'))

@app.route('/excluir_pedido/<int:pedido_id>', methods=['POST'])
@login_required
@permission_required('visualizar_relatorios')
def excluir_pedido(pedido_id):
    try:
        pedidos = carregar_dados('pedidos')
        pedidos = [p for p in pedidos if p['id'] != pedido_id]
        salvar_dados('pedidos', pedidos)
        flash('Pedido excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir pedido: {str(e)}', 'error')
    
    return redirect(url_for('relatorios_vendas_online'))

# ============= RELATÓRIOS =============

@app.route('/relatorios')
@login_required
@permission_required('visualizar_relatorios')
def relatorios():
    vendas = carregar_dados('vendas')
    movimentacoes = carregar_dados('movimentacoes')
    pontos = carregar_dados('pontos')
    pedidos = carregar_dados('pedidos')
    
    # Estatísticas
    total_vendas = sum(venda['total'] for venda in vendas) if vendas else 0
    total_pedidos = len(pedidos)
    total_clientes = len([p for p in pontos if p['pontos'] > 0])
    
    return render_template('relatorios.html', 
                         vendas=vendas, 
                         movimentacoes=movimentacoes, 
                         pontos=pontos,
                         pedidos=pedidos,
                         total_vendas=total_vendas,
                         total_pedidos=total_pedidos,
                         total_clientes=total_clientes)

@app.route('/relatorios_vendas_online')
@login_required
@permission_required('visualizar_relatorios')
def relatorios_vendas_online():
    # Executar migração automática ao acessar a página
    migrar_status_pedidos()
    
    pedidos = carregar_dados('pedidos')
    
    # Filtrar apenas pedidos de pré-venda
    pedidos_pre_venda = [p for p in pedidos if p.get('tipo_pedido') == 'pre_venda']
    
    # Calcular totais
    total_pedidos = len(pedidos_pre_venda)
    total_valor = sum(p['total'] for p in pedidos_pre_venda)
    pedidos_entregues = len([p for p in pedidos_pre_venda if p.get('status', {}).get('entregue', False)])
    pedidos_pagos = len([p for p in pedidos_pre_venda if p.get('status', {}).get('pago', False)])
    pedidos_completos = len([p for p in pedidos_pre_venda if p.get('status', {}).get('entregue', False) and p.get('status', {}).get('pago', False)])
    
    return render_template('relatorios_vendas_online.html', 
                         pedidos=pedidos_pre_venda,
                         total_pedidos=total_pedidos,
                         total_valor=total_valor,
                         pedidos_entregues=pedidos_entregues,
                         pedidos_pagos=pedidos_pagos,
                         pedidos_completos=pedidos_completos)

# ============= ROTAS DE DEBUG =============

@app.route('/debug')
def debug():
    """Rota para debug - mostra informações do sistema"""
    return jsonify({
        'session': dict(session),
        'user_authenticated': 'user_id' in session,
        'timestamp': datetime.now().isoformat(),
        'database_files': os.listridir('database') if os.path.exists('database') else []
    })

@app.route('/debug_pedidos')
def debug_pedidos():
    """Rota para debug de pedidos"""
    pedidos = carregar_dados('pedidos')
    return jsonify({
        'total_pedidos': len(pedidos),
        'pedidos': pedidos[-10:] if pedidos else [],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/debug_estoque')
def debug_estoque():
    """Rota para debug do estoque"""
    produtos = carregar_dados('produtos')
    return jsonify([{
        'id': p['id'],
        'nome': p['nome'],
        'quantidade': p['quantidade'],
        'estoque_minimo': p.get('estoque_minimo', 0)
    } for p in produtos])

# ============= INICIALIZAÇÃO =============

def inicializar_dados():
    # Dados iniciais para users
    users_data = carregar_dados('users')
    if not users_data:
        usuarios_iniciais = [
            {
                'id': 1,
                'nome': 'Pietro',
                'email': 'pietro@admin.turma.do.forno',
                'senha': hashlib.sha256('pietro123'.encode()).hexdigest(),
                'tipo': 'admin',
                'permissoes': ['gerenciar_usuarios', 'visualizar_estoque', 'alterar_estoque', 'realizar_vendas', 'cadastrar_produtos', 'visualizar_relatorios', 'gerenciar_pre_vendas'],
                'data_criacao': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            },
            {
                'id': 2,
                'nome': 'Francesco',
                'email': 'francesco@admin.turma.do.forno',
                'senha': hashlib.sha256('francesco123'.encode()).hexdigest(),
                'tipo': 'admin',
                'permissoes': ['gerenciar_usuarios', 'visualizar_estoque', 'alterar_estoque', 'realizar_vendas', 'cadastrar_produtos', 'visualizar_relatorios', 'gerenciar_pre_vendas'],
                'data_criacao': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            }
        ]
        salvar_dados('users', usuarios_iniciais)

    # Dados iniciais para produtos
    produtos_data = carregar_dados('produtos')
    if not produtos_data:
        produtos_iniciais = [
            {'id': 1, 'nome': 'Pão Francês', 'preco': 0.50, 'quantidade': 50, 'categoria': 'Pães', 'estoque_minimo': 10},
            {'id': 2, 'nome': 'Bolo de Chocolate', 'preco': 15.00, 'quantidade': 8, 'categoria': 'Bolos', 'estoque_minimo': 5},
            {'id': 3, 'nome': 'Café', 'preco': 5.00, 'quantidade': 30, 'categoria': 'Bebidas', 'estoque_minimo': 15},
            {'id': 4, 'nome': 'Suco Natural', 'preco': 7.00, 'quantidade': 25, 'categoria': 'Bebidas', 'estoque_minimo': 10},
            {'id': 5, 'nome': 'Croissant', 'preco': 4.50, 'quantidade': 20, 'categoria': 'Salgados', 'estoque_minimo': 8}
        ]
        salvar_dados('produtos', produtos_iniciais)

    # Garantir que os outros arquivos existam
    carregar_dados('vendas')
    carregar_dados('movimentacoes')
    carregar_dados('pontos')
    carregar_dados('pre_vendas')
    carregar_dados('pedidos')

if __name__ == '__main__':
    # Garantir que as pastas existam
    os.makedirs('database', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Inicializar dados
    with app.app_context():
        inicializar_dados()
        # Executar migração na inicialização
        migrar_status_pedidos()
    
    print("="*60)
    print("🚀 Servidor Flask iniciado!")
    print("📊 Dados inicializados")
    print("🔄 Migração de status executada")
    print("🌐 URL: http://localhost:5001")
    print("="*60)
    
    app.run(debug=True, port=5001, host='0.0.0.0')