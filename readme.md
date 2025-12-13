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
# SGEA - Sistema de Gestão de Eventos Acadêmicos (Fase 2)

Este repositório contém a base para a Fase 2 do SGEA. Os componentes Django foram restaurados como um esqueleto funcional (modelos, API, templates estáticos e scripts de seeding) e a documentação abaixo descreve como configurar, testar e usar o sistema localmente.

## Pré-requisitos
- Python 3.8 ou superior
- Git (opcional)

## Passos de instalação (ambiente local)

1. Crie e ative o ambiente virtual

```bash
python -m venv venv
# No Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Ou no CMD:
.\venv\Scripts\activate
# No macOS/Linux:
source venv/bin/activate
```

2. Instale as dependências

```bash
pip install -r requirements.txt
```

3. Aplique migrações e crie o banco de dados (SQLite por padrão)

```bash
python manage.py migrate
```

4. Popular o banco com dados iniciais (seeding)

```bash
python seed.py
```

5. Executar o servidor em desenvolvimento

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

## Regras de negócio resumidas
- Não é permitido cadastrar eventos com data de início anterior à data atual.
- Todo evento deve ter um professor responsável (`responsavel`).
- Não é permitida inscrição quando o número de vagas do evento for atingido.
- Um usuário não pode se inscrever mais de uma vez no mesmo evento.
- Senhas devem ter no mínimo 8 caracteres (validador padrão do Django está configurado).

## Upload de imagens (banner)
- O campo `banner` aceita arquivos de imagem (`.png`, `.jpg`, `.jpeg`). A validação é feita no model e antes do salvamento.

## E-mail de boas-vindas
- Na criação de um novo usuário, um e-mail de boas-vindas é enviado (no ambiente de desenvolvimento o backend padrão escreve no console).

## Emissão de certificados
- Os templates HTML para certificado foram mantidos; há lógica para renderização e geração via view. Um comando de management pode ser implementado para emissão em lote após término do evento.

## Testes manuais sugeridos (roteiro rápido)
1. Criar venv e instalar requisitos.
2. Rodar `python manage.py migrate`.
3. Executar `python seed.py` para garantir os usuários iniciais:
   - `organizador@sgea.com` / `Admin@123` (Organizador)
   - `aluno@sgea.com` / `Aluno@123` (Aluno)
   - `professor@sgea.com` / `Professor@123` (Professor)
4. Autenticar via `/api-token-auth/` e testar `GET /api/eventos/` com token.
5. Testar inscrição via `POST /api/inscricoes/` usando o token do usuário aluno.
