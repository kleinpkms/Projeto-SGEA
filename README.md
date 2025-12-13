# SGEA - Sistema de Gestão de Eventos Acadêmicos

Sistema desenvolvido em Django com API REST para gestão de eventos acadêmicos, inscrições e emissão de certificados.

##  Guia de Instalação

# Pré-requisitos
- Python 3.8 ou superior
- Git (opcional)

1. **Clonar ou baixar o projeto** e acessar a pasta via terminal.

## Pré-requisitos
- Python 3.8 ou superior
- Git (opcional)

## Passos de instalação (ambiente local)

2. Crie e ative o ambiente virtual

```bash
python -m venv venv
# No Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Ou no CMD:
.\venv\Scripts\activate
# No macOS/Linux:
source venv/bin/activate
```

3. Instale as dependências

```bash
pip install -r requirements.txt
```

4. Aplique migrações e crie o banco de dados (SQLite por padrão)

```bash
python manage.py migrate
```

5. Popular o banco com dados iniciais (seeding)

```bash
python seed.py
```

6. Executar o servidor em desenvolvimento

```bash
python manage.py runserver
```

O sistema ficará disponível em http://127.0.0.1:8000/

## API REST

Endpoints principais:
- POST `/api-token-auth/` — Autenticação: enviar `username` e `password` (retorna `token`).
- GET `/api/eventos/` — Listar eventos (autenticação por token).
- POST `/api/inscricoes/` — Criar inscrição do usuário autenticado em um evento.

Autenticação: use o cabeçalho `Authorization: Token <token>` após obter o token.

Limites (Throttling):
- Consulta de Eventos: 20 requisições por dia por usuário (escopo `event-list`).
- Inscrições: 50 requisições por dia por usuário (escopo `inscricao`).

## Testes manuais sugeridos (roteiro rápido)
1. Criar venv e instalar requisitos.
2. Rodar `python manage.py migrate`.
3. Executar `python seed.py` para garantir os usuários iniciais:
   - `organizador@sgea.com` / `Admin@123` (Organizador)
   - `aluno@sgea.com` / `Aluno@123` (Aluno)
   - `professor@sgea.com` / `Professor@123` (Professor)
4. Autenticar via `/api-token-auth/` e testar `GET /api/eventos/` com token.
5. Testar inscrição via `POST /api/inscricoes/` usando o token do usuário aluno.
