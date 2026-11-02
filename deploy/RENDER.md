# Hospedagem do Precision Agenda no Render

Este projeto já inclui `render.yaml` na raiz, preparado para publicar o **site público**, a **API FastAPI** e o **Precision Admin PWA** em um único serviço HTTPS. O domínio público será gerado **depois que o serviço for criado na conta do proprietário**.

## Por que o plano é pago?

O aplicativo existente usa **SQLite** e salva fotos em arquivos locais. O disco do serviço precisa ser persistente para preservar agendamentos e fotos durante redeploys. **A Render não oferece disco persistente em web services gratuitos**. A configuração usa o menor serviço pago definido no Blueprint (`0.5c-512mb`) e disco de 1 GB, com possíveis cobranças adicionais conforme o uso. Preços e condições oficiais: https://render.com/pricing e https://render.com/docs/disks.

> Nunca publique agendamentos reais em uma instância gratuita com SQLite local. Um reinício pode apagar o banco.

## Criar o serviço (na conta Render do proprietário)

1. Abra https://dashboard.render.com/ e faça login. Conecte a conta GitHub que pode acessar `PedroH0309/Barber-Shop-site`.
2. No Render clique **New → Blueprint**, selecione `PedroH0309/Barber-Shop-site`, branch `main` e o arquivo `render.yaml` na raiz.
3. Revise os recursos e os custos antes de confirmar. O Blueprint provisionará:
   - serviço web Python `precision-agenda` (1 instância, plano pago);
   - disco `precision-agenda-data`, **1 GB**, em `/opt/render/project/src/data`;
   - variáveis `AGENDA_DATA_DIR`, `COOKIE_SECURE=1`, `REMINDERS_ENABLED=0`.
4. Autorize a criação do serviço e aguarde o deploy terminar com o status **Live**. Em **Settings → Networking**, copie o endereço HTTPS `https://...onrender.com` gerado para a sua conta.
5. Verifique pelo navegador: `/` (site), `/agendar` (cliente), `/admin` (barbeiro) e `/api/public/config` (teste da API).
6. **Antes de anunciar o endereço**, em **Shell** do serviço Render execute `python manage.py create-admin`. Escolha o usuário e uma senha com pelo menos 12 caracteres. O comando é interativo e cria o administrador **no banco do servidor**. Nunca adicione a senha no GitHub.
7. Faça login em `/admin`. Configure serviços, preços, horários e folgas. Habilite **Publicar agenda** somente quando tudo estiver correto.
8. Faça uma solicitação de teste por `/agendar` e confirme que ela aparece no admin do iPhone, Android e Windows e que o barbeiro consegue aprovar/rejeitar.

## Instalar o painel no celular

- **iPhone:** abra `https://SEU-ENDERECO.onrender.com/admin` no Safari, toque **Compartilhar → Adicionar à Tela de Início**.
- **Android:** abra o mesmo endereço no Chrome, toque **⋮ → Instalar app**.
- **Windows:** abra o painel no Edge/Chrome e utilize **Instalar aplicativo**.

O navegador e a PWA usam a **mesma base de dados remota**. Não é necessário deixar o PC da barbearia ligado. O painel continua protegido por login, sessão e CSRF. Instalar a PWA não substitui autenticação.

## Preservar os agendamentos do Windows (opcional, antes de produzir)

O conteúdo da pasta `data/` do Windows **não está incluído no GitHub** e **não é transferido automaticamente**. Não publique uma nova instalação vazia sobre a agenda em uso sem um plano de migração.

1. Pare o servidor Windows e faça um backup privado da pasta `data/` contendo `agenda.sqlite3` e `uploads/`.
2. Com o novo servidor Render parado ou sem receber reservas, copie o banco e as fotos para o disco persistente do Render usando transferência segura (SSH/SCP, quando disponível). O destino é `/opt/render/project/src/data`.
3. Se um banco novo já contiver reservas, **não** substitua sem conciliação, para evitar perder marcações realizadas.
4. Valide os serviços e horários no admin e faça uma reserva teste antes de liberar o site publicamente.
5. **Nunca** envie `agenda.sqlite3`, a pasta `uploads` com dados sensíveis, tokens ou `.env` ao GitHub público.

Para novas barbearias, é possível começar com o banco novo e configurar os serviços e horários pelo painel. O banco será criado automaticamente na primeira inicialização do serviço.

## Operação e segurança

- Use **exatamente 1 instância e 1 worker** enquanto estiver no SQLite.
- Configure backups próprios e consistentes com a API `sqlite3.Connection.backup()` ou método SQLite equivalente, além dos snapshots do provedor. **Não restaure snapshots de disco à força sobre um banco SQLite ativo**.
- HTTPS, cookies seguros, proteção CSRF e autenticação são pré-requisitos, mas monitoração, limites de tráfego e proteção de dados também são necessários antes de receber clientes reais.
- `REMINDERS_ENABLED=0`: WhatsApp automático continua desativado até configurar a integração oficial.
- Se o deploy falhar, consulte **Logs** do serviço. `ModuleNotFoundError` costuma indicar instalação de dependências incompleta; `unable to open database file` costuma indicar disco ausente ou permissões incorretas.

Documentação oficial: https://render.com/docs/blueprint-spec • https://render.com/docs/disks • https://render.com/docs/deploys
