# SGEA - Sistema de Gestão de Eventos Acadêmicos (Trabalho 2)

Sistema desenvolvido em Django com API REST para gestão de eventos acadêmicos, inscrições e emissão de certificados.

##  Guia de Instalação

# Pré-requisitos
- Python 3.8 ou superior
- Git (opcional)

1. **Clonar ou baixar o projeto** e acessar a pasta via terminal.

3. **Criar e ativar o ambiente virtual:**
   ```bash
   python -m venv venv
   # No Windows:
   .\venv\Scripts\activate
   # No Linux/Mac:
   source venv/bin/activate

3. **Instalar as dependências:**

    pip install django djangorestframework markdown django-filter pillow

4.**Configurar o Banco de Dados:**

     python manage.py migrate

5. **Popular o Banco com Dados Iniciais (Seeding):**

    python seed.py

Isso criará os usuários: Organizador, Professor e Aluno.

6.**Executar o servidor:**

    python manage.py runserver
    
Acesse: http://127.0.0.1:8000/

## Guia de Testes

1. **Acesso ao Sistema**
    Admin: Acesse /admin

    Login Organizador: organizador@sgea.com | Senha: Admin@123

    Login Aluno: aluno@sgea.com | Senha: Aluno@123

2. **Testando a API REST**
    Acesse os endpoints para verificar a listagem e inscrições:

    Eventos: GET /api/eventos/ (Requer autenticação)

    Inscrições: POST /api/inscricoes/

3. **Funcionalidades Implementadas**
    Cadastro de Eventos com Banner (Upload de Imagens).

    API REST com controle de acesso (Throttling).

    Automação de E-mail de Boas-vindas (Simulado no Terminal).

    Perfis de Acesso (Organizador, Professor, Aluno).