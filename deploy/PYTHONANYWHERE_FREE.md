# Precision Agenda — hospedagem gratuita (PythonAnywhere)

Esta é a opção **sem mensalidade** para demonstrar o Precision Agenda sem deixar o PC da barbearia ligado. Usa o mesmo projeto FastAPI, banco SQLite no armazenamento persistente da conta, PWA do administrador e o subdomínio HTTPS gratuito `SEU_USUARIO.pythonanywhere.com`.

**Limitações oficiais (2026):** conta Beginner gratuita com 1 web app e 1 worker, 512 MiB de armazenamento total, limite de 100 CPU-seconds, e expiração da web app após **1 mês** (precisa renovar no painel da conta). O suporte ASGI/FastAPI na PythonAnywhere é **experimental** e suas condições podem mudar. Esta configuração serve para um piloto de pequena escala; não oferece as garantias de disponibilidade, backups e desempenho esperadas de uma barbearia comercial. A PythonAnywhere não recomenda SQLite para produção.

Fontes:
- https://help.pythonanywhere.com/pages/FreeAccountsFeatures/
- https://help.pythonanywhere.com/pages/ASGICommandLine
- https://help.pythonanywhere.com/pages/KindsOfDatabases
- https://help.pythonanywhere.com/pages/UploadingAndDownloadingFiles

## 1. Abrir a conta gratuita

Entre em https://www.pythonanywhere.com/pricing/ e escolha **Beginner $0/mês**. Não adicione método de pagamento nem selecione upgrade.

Crie a conta, anote o nome de usuário da PythonAnywhere (não é necessariamente seu nome do GitHub), abra **Consoles → Bash**.

## 2. Instalar o projeto

Cole os comandos abaixo no Bash da PythonAnywhere (um por vez, não no seu PC):

```bash
git clone https://github.com/PedroH0309/Barber-Shop-site.git ~/precision-agenda
cd ~/precision-agenda
mkvirtualenv precision-agenda --python=python3.11
pip install --no-cache-dir -r requirements.txt
mkdir -p ~/precision-agenda/data
```

Se `python3.11` não estiver disponível, use a versão Python 3.10+ oferecida pela própria PythonAnywhere; o projeto exige que as versões de dependências do `requirements.txt` sejam compatíveis.

Verifique a importação do backend:

```bash
python -c "from pythonanywhere_entry import app; print(app.title)"
```

Agora crie **o administrador no servidor**; não use senhas do GitHub:

```bash
python manage.py create-admin
```

Informe um nome de usuário e uma senha forte de pelo menos 12 caracteres. **Não publique essa senha em arquivos versionados nem neste chat.**

> Se já existem agendamentos no Windows, NÃO comece a aceitar clientes nessa base vazia sem um plano de migração. Com a aplicação Windows parada, faça backup consistente da pasta `data/`; use o upload privado de arquivos no PythonAnywhere para levar `agenda.sqlite3` e a pasta `uploads/` ao diretório `/home/SEU_USUARIO/precision-agenda/data/`, preservando os caminhos. Não envie dados dos clientes ao GitHub.

## 3. Criar o site HTTPS

A PythonAnywhere usa uma ferramenta própria para instalar sites FastAPI/ASGI, ainda em beta.

1. Em **Account → API token**, crie um token pessoal para uso da ferramenta dentro da conta (não copie o token para o GitHub ou para o ChatGPT).
2. Abra o Bash e rode `pip install --upgrade pythonanywhere`.
3. Substitua **SEU_USUARIO** nos dois lugares abaixo pelo nome exato da conta. **Preserve `\${DOMAIN_SOCKET}` como está** (o sistema fornece seu valor quando inicia o servidor).

```bash
pa website create --domain SEU_USUARIO.pythonanywhere.com --command '/home/SEU_USUARIO/.virtualenvs/precision-agenda/bin/uvicorn --app-dir /home/SEU_USUARIO/precision-agenda --uds ${DOMAIN_SOCKET} pythonanywhere_entry:app'
```

Se sua conta é no sistema europeu, o domínio termina em `.eu.pythonanywhere.com`, com o comando ajustado.

Com o site criado, abra:
- `https://SEU_USUARIO.pythonanywhere.com/` — página da barbearia
- `https://SEU_USUARIO.pythonanywhere.com/agendar` — solicitação de horário
- `https://SEU_USUARIO.pythonanywhere.com/admin` — painel com login

A inicialização usa a entrada `pythonanywhere_entry.py` que força `COOKIE_SECURE=1` e mantém os lembretes WhatsApp desativados por padrão. O banco existente permanece em `~/precision-agenda/data/agenda.sqlite3`.

## 4. Teste obrigatório antes de divulgar

1. Entre no painel com o usuário criado na nuvem.
2. Configure serviços, preços, turnos e folgas.
3. Em Configurações, ative **Publicar agenda** somente depois de conferir os horários.
4. Abra a agenda pública em navegação anônima e solicite um horário de teste.
5. No admin, confirme que a solicitação chegou como **PENDENTE**, aprove-a e verifique o status pelo link privado do cliente.
6. Recarregue o app e confira se a agenda e as configurações persistiram.
7. Abra o painel no iPhone (Safari) ou Android (Chrome) e instale na tela inicial. O PWA precisa de internet.

## 5. Atualizações, manutenção e problemas

Para atualizar o código no PythonAnywhere sem apagar as reservas:

```bash
cd ~/precision-agenda
git pull
pa website reload --domain SEU_USUARIO.pythonanywhere.com
```

**Nunca apague a pasta `data` para atualizar.** Faça backups privados frequentes e teste a restauração. SQLite em modo WAL exige backup consistente (por exemplo, com `sqlite3.Connection.backup()`); não copie apenas o arquivo de banco enquanto há gravações.

Se o site apresentar erro, inspecione o log de erro em `/var/log/SEU_USUARIO.pythonanywhere.com.error.log` pelo Console/Files. Se faltar memória ou armazenamento, confira a cota e remova somente caches/arquivos temporários que você reconheça, nunca reservas ou fotos.

Como a web app gratuita expira após 1 mês, **renove-a regularmente no painel da conta**, conforme os avisos da PythonAnywhere. Se o recurso ASGI não estiver disponível em sua conta gratuita, não force a migração nem pague automaticamente: considere um serviço WSGI compatível ou hospedagem Always Free com disco, sujeito à disponibilidade.

**Não é necessário contratar o Render.** O arquivo `render.yaml` continua no projeto apenas como alternativa futura; não cria despesas sozinho.
