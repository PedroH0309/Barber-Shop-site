# PRECISION AGENDA — Edição com aprovação manual

> **Hospedagem recomendada: Render.** Para publicar o site e o Precision Admin no mesmo endereço HTTPS, use o Blueprint [`render.yaml`](render.yaml) e o [guia de publicação no Render](deploy/RENDER.md). A configuração requer um serviço pago com disco persistente para preservar o banco SQLite e as fotos. O GitHub contém somente código; publicar o repositório não cria o servidor nem transfere reservas do Windows.


Sistema completo de site + agendamento para **um único barbeiro**, com agenda pública de horários livres e painel administrativo protegido por senha. A reserva **não fica automaticamente confirmada**: é uma **solicitação pendente de aprovação**.

## Fluxo de reserva

1. O cliente acessa **/agendar**, escolhe serviço, valor, foto, dia e um horário disponível.
2. Digita **nome completo** e **telefone com DDD** e envia a solicitação.
3. O sistema grava como **PENDENTE** e já bloqueia o intervalo integral (inclusive sobreposições com serviços longos), mesmo antes da decisão. Duas pessoas não podem solicitar simultaneamente o mesmo horário.
4. O cliente recebe um **link privado de acompanhamento** (`/agendar?reserva=...`). Guarde-o: quem tiver esse link pode consultar os detalhes e status da reserva; ele não inclui nome nem telefone.
5. O barbeiro entra em **/admin**, vê a **fila de pedidos** e escolhe **APROVAR** ou **RECUSAR**. Recusar libera o horário.
6. Após a **aprovação**, o cliente vê a mudança no mesmo link e pode adicionar o corte ao **Google Agenda**, baixar **.ics** para Apple Calendar / Android, ou consultar sua confirmação mais tarde. Um evento salvo no calendário não recebe correções futuras automaticamente.
7. O barbeiro gerencia conclusão, falta ou cancelamento no painel. Cancelar libera o horário. As decisões são registradas internamente em `booking_events`.

O cliente não vê nomes, telefones ou reservas dos demais usuários. A agenda pública retorna **somente os horários disponíveis**. O painel exige login e senha exclusivos.

### Estados da reserva

| Status | Ocupa horário? | Pode adicionar ao calendário? | Significado |
|---|---|---|---|
| Pendente | Sim | Não | Cliente solicitou, aguardando decisão do barbeiro |
| Aprovado | Sim | Sim | Barbeiro aceitou o pedido |
| Confirmado | Sim | Sim | Cliente confirmou presença em um lembrete válido (quando integração ativa), ou barbeiro registrou essa confirmação |
| Recusado | Não | Não | Barbeiro não aceitou; horário liberado |
| Cancelado | Não | Não | Reserva foi cancelada |
| Concluído / Não compareceu | Não | Apenas concluído | Estados finais do atendimento |

**Decisão importante:** o pedido pendente ocupa o horário até o barbeiro decidir; esta versão não expira automaticamente pedidos sem resposta. Por isso o painel deve ser consultado regularmente. Pedidos do dia que já passaram não são exibidos na fila futura, mas continuam acessíveis pelo histórico de agendamentos.

## WhatsApp: tipo ainda desconhecido

**Nenhuma mensagem automática é enviada por padrão.** Preencher o número do barbeiro no admin **não ativa o bot**. Esta versão é independente do tipo de WhatsApp usado (normal, Business App ou Business Platform).

- O painel permite **copiar** um aviso de aprovação ou recusa para o barbeiro enviar **manualmente** no aplicativo que já utiliza. Copiar não envia.
- O cliente pode acompanhar a decisão pelo link privado, mesmo sem WhatsApp.
- A integração automática futura prevista usa a **WhatsApp Business Platform (Cloud API) oficial**, com número e credenciais autorizados, consentimento do cliente, webhook HTTPS válido e modelo de mensagem aprovado.
- O worker de lembretes envia mensagens **somente para reservas já aprovadas ou com presença confirmada**, próximas do atendimento, e **somente quando houver consentimento e configuração ativa**.
- Os botões do template `CONFIRMAR` e `CANCELAR` podem atualizar o agendamento ao receber webhook com assinatura válida e número do cliente correspondente. O envio automático depende de serviço e conta devidamente configurados, não apenas destes arquivos.

Configuração futura (não necessária para executar a agenda):

```env
REMINDERS_ENABLED=1
WA_PHONE_NUMBER_ID=...
WA_ACCESS_TOKEN=...
WA_TEMPLATE_NAME=lembrete_agendamento
WA_VERIFY_TOKEN=...
META_APP_SECRET=...
COOKIE_SECURE=1
```

O template em `pt_BR` deve conter nome, serviço, data, hora e os dois botões de resposta, conforme a implementação em `backend/app.py`. Webhook: `https://SEU_DOMINIO/api/whatsapp/webhook`. Utilize apenas um worker interno para evitar envios duplicados. A plataforma exige aprovação de templates para mensagens iniciadas pela empresa e consentimento adequado; pode haver custos.

## Executar no Windows

1. Instale **Python 3.13 (64 bits)**. O instalador do projeto seleciona explicitamente Python 3.13 para evitar incompatibilidades com bibliotecas nativas.
2. Descompacte este projeto em uma pasta.
3. Abra **INSTALAR_WINDOWS.bat** para instalar dependências e criar usuário/senha do barbeiro. Usuário sugerido: `barbeiro`; **não há senha padrão**. Você define uma senha com no mínimo 12 caracteres. Para redefinir o login a qualquer momento, execute `CONFIGURAR_LOGIN.bat` sem excluir a pasta `data/`.
4. Abra **INICIAR_WINDOWS.bat** para executar o servidor local. Mantenha o terminal aberto.
5. Acesse:
   - Site: http://127.0.0.1:5500/
   - Agendar: http://127.0.0.1:5500/agendar
   - Admin: http://127.0.0.1:5500/admin

Ou no terminal, dentro da pasta:

```bash
py -3.13 -m venv .venv
# Ative o venv: Windows .venv\Scripts\activate / Linux/macOS source .venv/bin/activate
pip install -r requirements.txt
python manage.py create-admin
uvicorn backend.app:app --host 127.0.0.1 --port 5500
```

### Por que os horários não apareciam para os clientes?

O expediente semanal e a **publicação da agenda** são configurações diferentes. Por segurança, novas instalações começam com a agenda despublicada. Mesmo com turnos cadastrados, `/agendar` não mostra horários enquanto a opção **Publicar agenda** estiver desligada.

Para liberar: **Admin → Meus horários → PUBLICAR AGENDA AGORA**, ou **Admin → Configurações → Publicar agenda → Salvar**. O botão da tela de horários só aparece quando existem turnos cadastrados. Depois, o cliente pode clicar em **Atualizar horários** e escolher um dia com expediente.

**Importante:** o GitHub guarda apenas o código. A pasta local `data/`, que contém senha administrativa, SQLite, fotos enviadas e agendamentos de clientes, **não é enviada** ao repositório. O endereço `127.0.0.1` continua privado ao computador; publicar no GitHub não hospeda o backend da agenda.

### Atualização de uma instalação Windows existente

1. Pare o servidor usando `Ctrl + C` e faça backup de `data/`.
2. Baixe o código atualizado do GitHub: **Code → Download ZIP**.
3. Copie os novos arquivos para a instalação atual, mantendo **`data/`** e **`.venv/`** intactos.
4. Rode `\.venv\Scripts\python.exe -m pip install -r requirements.txt`, caso dependências tenham mudado.
5. Reinicie com **INICIAR_WINDOWS.bat** e use **Ctrl + F5** no navegador para atualizar o JavaScript do painel.

O login do barbeiro e as reservas persistem porque permanecem na pasta `data/` original.

### Primeira configuração

A agenda começa **DESPUBLICADA**, com preços e turnos apenas ilustrativos. No painel, revise os serviços, durações, preços, fotos, planos (vitrine, sem cobrança recorrente), expediente, pausas, folgas, endereço e telefone. **Só então marque "Publicar agenda"** em Configurações. Em uma tela anônima, faça um agendamento de teste e aprove manualmente no admin.

### Atualizando uma instalação anterior

Faça **backup** da pasta `data/` antes de substituir os arquivos. O banco SQLite não é incluído nesta distribuição. A migração automática mantém as reservas antigas no estado **APROVADO** (elas eram automaticamente confirmadas na versão anterior) e novas solicitações começam em **PENDENTE**. Não apague o banco se quiser preservar seus dados.

## Exportação de calendários

- **Cliente:** após aprovação, botão Google Agenda ou arquivo `.ics`; antes disso, não pode adicionar ao calendário.
- **Barbeiro:** em Admin → Configurações, link privado de assinatura `.ics`, que inclui **somente agendamentos aprovados/confirmados** (sem pedidos pendentes). O link contém o nome do cliente; trate-o como senha e revogue se vazar. A atualização nos apps depende do serviço de calendário, não é instantânea.

## Segurança e implantação

- Conta única de administrador com senha armazenada usando scrypt com salt, cookie de sessão HttpOnly, CSRF em escritas e proteção de rotas administrativas.
- Bloqueio de intervalo de tempo com transação `BEGIN IMMEDIATE` no SQLite: é revalidado no momento de solicitar ou aprovar.
- Nome e telefone são privados e não aparecem nos endpoints públicos; o link de acompanhamento contém token aleatório de alta entropia (deve ser mantido privado).
- O banco `data/agenda.sqlite3` contém dados pessoais. Ele não deve ir ao GitHub, nem junto do ZIP entregue a clientes.
- O servidor local não pode ser aberto ao público sem hospedagem apropriada. Para produção, use **HTTPS**, backups, limite de requisições no proxy, proteção de credenciais, política de privacidade/LGPD, política de retenção e monitoramento. Cookies exigem `COOKIE_SECURE=1` em HTTPS.
- O sistema foi pensado para **um profissional**; não há multiusuário nem múltiplas agendas.

## Estrutura e testes

```text
backend/app.py         API, SQLite, login, aprovação, webhooks
site/index.html        Site da barbearia
site/agendar.html      Formulário, calendário, acompanhamento privado
site/admin.html        Painel administrativo / fila de pendentes
site/booking.js        Disponibilidade, envio de solicitação e acompanhamento
site/admin.js          Aprovação, recusa, expediente, fotos, planos, serviços
site/*.css             Layout desktop e mobile
manage.py              Criação / atualização de usuário admin
test_system.py         Suíte de testes de integração
INSTALAR_WINDOWS.bat   Instalar no Windows
INICIAR_WINDOWS.bat    Iniciar servidor
```

Executar verificações:

```bash
python test_system.py
node --check site/booking.js
node --check site/admin.js
node --check site/script.js
```

Os testes usam um banco temporário. Teste novamente no navegador real (Safari/Chrome mobile e desktop) antes de uso com clientes. A plataforma ainda não foi auditada como serviço comercial em produção.

## Painel administrativo v2

- **Acesso do barbeiro:** `CONFIGURAR_LOGIN.bat` cria ou redefine usuário/senha sem perder registros. No painel, em Configurações → Acesso do barbeiro, o próprio profissional pode trocar usuário e senha informando a senha atual. Essa ação invalida todas as sessões. Não há senha fixa entregue pelo projeto.
- **Clientes:** diretório privado agrupado por telefone a partir das reservas existentes, com contadores de visitas concluídas, recorrência e próximos horários. Não é um CRM externo.
- **Agendamentos:** pesquisa por nome, telefone e serviço; filtro por status; intervalo de datas; exportação local para CSV apenas de reservas visíveis pelos filtros; histórico auditável de mudanças de status. A exportação contém dados pessoais e deve ser guardada com segurança.
- **Instalador:** força Python 3.13, detecta ambiente virtual antigo e inclui `tzdata` para o horário de São Paulo no Windows. Não apaga banco de dados nem fotos ao recriar o ambiente.

**Atualização para uma instalação já funcionando:** faça backup da pasta `data/`, encerre o servidor, substitua os arquivos de código pelos da nova versão sem substituir ou apagar `data/` e `.env`, instale as novas dependências com `.venv\Scripts\python.exe -m pip install -r requirements.txt` e execute `INICIAR_WINDOWS.bat`. Não rode `INSTALAR_WINDOWS.bat` novamente apenas para atualizar: ele solicitará a redefinição do login.

## Correção de sincronização dos horários (Admin v2.1)

**Problema corrigido:** os turnos eram armazenados com `0=domingo, 1=segunda, ..., 6=sábado`, mas a agenda pública consultava os turnos usando `date.weekday()` do Python, que usa `0=segunda, ..., 6=domingo`. Isso deslocava os dias de atendimento. A consulta pública agora converte para a mesma convenção de domingo=0, **sem alterar os valores já salvos** no banco de dados.

Em **Admin → Meus horários**, agora:

1. Confira a faixa de publicação: se constar **Agenda não publicada**, entre em **Configurações**, marque **Publicar agenda** e clique em **Salvar configurações**.
2. Escolha o dia e o início/fim. Use **Substituir dia** para remover todos os turnos anteriores daquele dia e criar um novo período contínuo. Por exemplo, substituir segunda por 10:00–18:00.
3. Para incluir pausa de almoço, substitua o dia por 09:00–12:00 e depois use **Adicionar turno** para 13:00–18:00. O botão Adicionar não substitui os períodos existentes.
4. Use **Fechar dia** para remover todos os turnos desse dia da semana; o dia continuará fechado mesmo após reiniciar o programa.
5. Abra `/agendar`, selecione um serviço e uma data futura com expediente. Se a página já estava aberta, clique **Atualizar horários** ou recarregue-a.

A agenda respeita a duração do serviço (cortes mais longos podem não caber perto do fim do expediente), intervalo mínimo de antecedência, bloqueios de data e reservas pendentes/aprovadas. Alterar turnos **não cancela reservas existentes**: avalie manualmente os compromissos já confirmados antes de reduzir o expediente.

### Atualização da versão anterior

Faça backup da pasta `data/` (principalmente `agenda.sqlite3` e `uploads/`), feche o servidor (`Ctrl+C` no terminal) e **substitua os arquivos do programa pelos deste ZIP, preservando as pastas `data/` e `.venv/`**. Não execute o instalador se a instalação atual já funciona. Para reiniciar: `INICIAR_WINDOWS.bat`. Os horários existentes não sofrem migração de numeração, pois o erro estava na consulta pública, não na convenção usada no painel.

Teste de regressão: `python test_schedule_sync.py` (com banco temporário isolado, sem tocar nas reservas reais).

## Precision Admin instalável (iOS / Android / Windows)

O painel `/admin` agora é um PWA responsivo: tem manifesto, ícones, navegação móvel e instruções de instalação no iPhone (Safari → Compartilhar → Adicionar à Tela de Início), Android (Chrome → Instalar app) e desktop (Chrome/Edge → Instalar aplicativo).

O sistema continua exigindo autenticação e conexão com a internet: **nenhuma reserva ou resposta privada da API é armazenada offline**. A interface e as operações administrativas compartilham a mesma API e banco de dados do agendamento público. Em produção é necessário HTTPS com domínio próprio; `127.0.0.1` funciona apenas no computador local.

Para publicar site + API + banco com armazenamento persistente, consulte [deploy/README.md](deploy/README.md). O GitHub sozinho não hospeda o backend. Não envie credenciais ou o banco ao GitHub.
