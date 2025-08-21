// Máscara para CPF
document.addEventListener('DOMContentLoaded', function() {
    const cpfInputs = document.querySelectorAll('.cpf-mask');
    
    cpfInputs.forEach(input => {
        input.addEventListener('input', function() {
            let value = this.value.replace(/\D/g, '');
            
            if (value.length > 11) {
                value = value.slice(0, 11);
            }
            
            if (value.length > 9) {
                value = value.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
            } else if (value.length > 6) {
                value = value.replace(/(\d{3})(\d{3})(\d+)/, '$1.$2.$3');
            } else if (value.length > 3) {
                value = value.replace(/(\d{3})(\d+)/, '$1.$2');
            }
            
            this.value = value;
        });
    });
});

// PDV - Adicionar produto ao carrinho
function adicionarAoCarrinho(produtoId, produtoNome, produtoPreco) {
    const carrinho = JSON.parse(localStorage.getItem('carrinho')) || [];
    const produtoExistente = carrinho.find(item => item.id === produtoId);
    
    if (produtoExistente) {
        produtoExistente.quantidade += 1;
    } else {
        carrinho.push({
            id: produtoId,
            nome: produtoNome,
            preco: produtoPreco,
            quantidade: 1
        });
    }
    
    localStorage.setItem('carrinho', JSON.stringify(carrinho));
    atualizarCarrinho();
}

// PDV - Remover produto do carrinho
function removerDoCarrinho(produtoId) {
    let carrinho = JSON.parse(localStorage.getItem('carrinho')) || [];
    carrinho = carrinho.filter(item => item.id !== produtoId);
    localStorage.setItem('carrinho', JSON.stringify(carrinho));
    atualizarCarrinho();
}

// PDV - Alterar quantidade
function alterarQuantidade(produtoId, alteracao) {
    const carrinho = JSON.parse(localStorage.getItem('carrinho')) || [];
    const produto = carrinho.find(item => item.id === produtoId);
    
    if (produto) {
        produto.quantidade += alteracao;
        
        if (produto.quantidade <= 0) {
            removerDoCarrinho(produtoId);
        } else {
            localStorage.setItem('carrinho', JSON.stringify(carrinho));
            atualizarCarrinho();
        }
    }
}

// PDV - Atualizar exibição do carrinho
function atualizarCarrinho() {
    const carrinho = JSON.parse(localStorage.getItem('carrinho')) || [];
    const carrinhoItems = document.getElementById('carrinho-items');
    const carrinhoTotal = document.getElementById('carrinho-total');
    
    if (carrinhoItems) {
        carrinhoItems.innerHTML = '';
        
        let total = 0;
        
        carrinho.forEach(item => {
            const itemTotal = item.preco * item.quantidade;
            total += itemTotal;
            
            const itemElement = document.createElement('div');
            itemElement.className = 'produto-item';
            itemElement.innerHTML = `
                <div class="produto-info">
                    <div>${item.nome}</div>
                    <div>R$ ${item.preco.toFixed(2)} x ${item.quantidade}</div>
                </div>
                <div class="produto-acoes">
                    <div class="quantidade-btn" onclick="alterarQuantidade(${item.id}, -1)">-</div>
                    <div>${item.quantidade}</div>
                    <div class="quantidade-btn" onclick="alterarQuantidade(${item.id}, 1)">+</div>
                    <button class="btn-danger" onclick="removerDoCarrinho(${item.id})">Remover</button>
                </div>
            `;
            
            carrinhoItems.appendChild(itemElement);
        });
        
        if (carrinhoTotal) {
            carrinhoTotal.textContent = `Total: R$ ${total.toFixed(2)}`;
        }
    }
}

// PDV - Finalizar venda
function finalizarVenda() {
    const carrinho = JSON.parse(localStorage.getItem('carrinho')) || [];
    const cpfCliente = document.getElementById('cpf-cliente')?.value || '';
    
    if (carrinho.length === 0) {
        alert('Adicione produtos ao carrinho antes de finalizar a venda.');
        return;
    }
    
    const total = carrinho.reduce((sum, item) => sum + (item.preco * item.quantidade), 0);
    const data = new Date().toLocaleString('pt-BR');
    
    fetch('/processar_venda', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            produtos: carrinho,
            cpfCliente: cpfCliente,
            total: total,
            data: data
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Venda realizada com sucesso!');
            localStorage.removeItem('carrinho');
            atualizarCarrinho();
            document.getElementById('cpf-cliente').value = '';
        } else {
            alert('Erro ao processar venda.');
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao processar venda.');
    });
}

// Inicializar carrinho quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
    if (window.location.pathname === '/pdv') {
        atualizarCarrinho();
    }
});
// Modal para aumentar estoque
function abrirModalAumentarEstoque(produtoId, produtoNome) {
    document.getElementById('produto_id').value = produtoId;
    document.getElementById('produto_nome').value = produtoNome;
    document.getElementById('modal-estoque').style.display = 'block';
}

// Fechar modal quando clicar no X
document.querySelector('.close').addEventListener('click', function() {
    document.getElementById('modal-estoque').style.display = 'none';
});

// Fechar modal quando clicar fora dele
window.addEventListener('click', function(event) {
    const modal = document.getElementById('modal-estoque');
    if (event.target === modal) {
        modal.style.display = 'none';
    }
});

// Confirmar exclusão de usuário
function confirmarExclusao(event) {
    if (!confirm('Tem certeza que deseja excluir este usuário?')) {
        event.preventDefault();
    }
}
// Header interativo
document.addEventListener('DOMContentLoaded', function() {
    // Destacar item do menu ativo
    const currentPage = window.location.pathname;
    const navLinks = document.querySelectorAll('header nav a');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPage) {
            link.style.background = 'rgba(255, 255, 255, 0.2)';
            link.style.fontWeight = '600';
        }
    });
    
    // Header com efeito de scroll
    const header = document.querySelector('header');
    let lastScroll = 0;
    
    window.addEventListener('scroll', function() {
        const currentScroll = window.pageYOffset;
        
        if (currentScroll > lastScroll && currentScroll > 100) {
            header.style.transform = 'translateY(-100%)';
        } else {
            header.style.transform = 'translateY(0)';
        }
        
        lastScroll = currentScroll;
    });
});
// Fallback para imagem da logo
document.addEventListener('DOMContentLoaded', function() {
    const logoImg = document.querySelector('.logo-img');
    
    if (logoImg) {
        logoImg.onerror = function() {
            this.style.display = 'none';
            // A pseudoclasse :before do CSS já mostra o fallback "TF"
        };
        
        // Verifica se a imagem carregou corretamente
        if (logoImg.complete && logoImg.naturalHeight === 0) {
            logoImg.style.display = 'none';
        }
    }
    
    // Destacar item do menu ativo
    const currentPage = window.location.pathname;
    const navLinks = document.querySelectorAll('header nav a');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPage) {
            link.style.background = 'rgba(255, 255, 255, 0.2)';
            link.style.fontWeight = '600';
        }
    });
    
    // Header com efeito de scroll
    const header = document.querySelector('header');
    let lastScroll = 0;
    
    window.addEventListener('scroll', function() {
        const currentScroll = window.pageYOffset;
        
        if (currentScroll > lastScroll && currentScroll > 100) {
            header.style.transform = 'translateY(-100%)';
        } else {
            header.style.transform = 'translateY(0)';
        }
        
        lastScroll = currentScroll;
    });
});
// Ajuste fino da imagem da logo
document.addEventListener('DOMContentLoaded', function() {
    const logoImg = document.querySelector('.logo-img');
    
    if (logoImg) {
        // Forçar redimensionamento se necessário
        logoImg.onload = function() {
            console.log('Logo carregada com sucesso!');
            // Ajustes manuais se necessário
            this.style.maxWidth = '100%';
            this.style.maxHeight = '100%';
        };
        
        logoImg.onerror = function() {
            this.style.display = 'none';
            console.log('Logo não carregada, usando fallback');
        };
    }
});