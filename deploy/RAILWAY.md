# Publicação no Railway — Precision Agenda

Esta configuração publica o FastAPI e o frontend no **mesmo serviço HTTPS**, mantendo a sessão do administrador no mesmo domínio. `/admin` e todas as rotas `/api/admin/*` continuam protegidas por login; **não** exponha o arquivo `agenda.sqlite3`, o feed privado ICS ou credenciais.

## Preparação da conta (requer autorização do proprietário)

1. No Railway, crie um projeto a partir do GitHub: `PedroH0309/Barber-Shop-site`.
2. Aponte a origem para a raiz do repositório. O arquivo `railway.toml` seleciona `deploy/Dockerfile`. Utilize **um serviço e uma réplica**.
3. Antes de permitir reservas, adicione um **volume persistente** àquele serviço, com caminho de montagem exato `/app/data`. Sem volume, reinicializações ou novas implantações podem perder agendamentos, configurações e fotos.
4. Em Variables do serviço configure:

   `AGENDA_DATA_DIR=/app/data`
   `COOKIE_SECURE=1`
   `REMINDERS_ENABLED=0`
   `RAILWAY_RUN_UID=0`

   O `RAILWAY_RUN_UID=0` é necessário neste empacotamento porque os volumes Railway são montados como root. Não inclua senhas, telefones ou tokens nas variáveis públicas do GitHub.

5. Faça Deploy. Em Settings → Networking → Public Networking, clique em **Generate Domain**. Railway atribui um endereço HTTPS `*.up.railway.app` (não invente esse endereço antes de criar o serviço).
6. Instale o [Railway CLI](https://docs.railway.com/cli), autentique-se (`railway login`) e vincule o projeto (`railway link`). Com o serviço rodando e o volume montado, configure a conta administrativa *dentro do contêiner remoto*:

   `railway ssh -- python manage.py create-admin`

   O comando é interativo e lê uma senha forte sem mostrá-la. **Uma conta criada apenas no seu PC não é transferida automaticamente para o servidor remoto.**
7. Valide `/`, `/agendar`, `/admin`; entre com a conta configurada no servidor, cadastre expedientes e serviços e faça uma reserva de teste ponta a ponta. Publique a agenda somente depois desses testes.
8. No iPhone, Safari → Compartilhar → Adicionar à Tela de Início. No Android, Chrome → Instalar app. No PC, Edge/Chrome → Instalar app. O PWA precisa de internet para agendamentos.

## Migração da instalação Windows existente

O repositório contém **somente o código**, não as reservas reais. A instalação Windows guarda o arquivo `data/agenda.sqlite3` e as fotos em `data/uploads/`. **Não crie contas de produção nem publique horários antigos até decidir se os dados locais precisam ser migrados.**

- Faça backup da pasta `data` com o servidor Windows parado para evitar cópia inconsistente de SQLite em modo WAL.
- A migração deve transferir *somente pelo canal seguro do projeto* o banco e uploads para o volume `/app/data`, mantendo a árvore `uploads/`. Não envie esse backup ao GitHub, nem publique um ZIP com dados de clientes.
- Antes de substituir um banco já em uso no Railway, faça backup do volume e interrompa o aplicativo. Nunca substitua um banco com reservas novas sem conciliação; isso causaria perda de agendamentos.
- Se não houver dados a preservar, crie uma base vazia no servidor e configure tudo pelo admin.

## Operação

- Mantenha **um único processo** Uvicorn e **uma única réplica** com SQLite; dimensionamento horizontal exige migrar para um banco compartilhado, como PostgreSQL, com controle transacional.
- Ative backups automáticos do volume Railway e faça teste periódico de restauração.
- Habilite HTTPS (fornecido pelo domínio Railway), monitore erros e disponibilidade, proteja login e APIs com limite de requisições no proxy e considere MFA antes de escalar o negócio.
- Não habilite `REMINDERS_ENABLED=1` antes de configurar WhatsApp Business Cloud API oficialmente.
- Um domínio próprio é opcional: comece pelo subdomínio HTTPS gerado no Railway e depois configure DNS personalizado se desejar.

## Referências oficiais

- https://docs.railway.com/services
- https://docs.railway.com/networking/domains/working-with-domains
- https://docs.railway.com/volumes
- https://docs.railway.com/cli/ssh
