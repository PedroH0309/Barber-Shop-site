# Publicação do Precision Agenda (site público + Admin PWA)

Este projeto **não vira público por estar no GitHub**. Requer um servidor com IP público, domínio, DNS e HTTPS.

## Implantação simples em uma VPS Linux

1. Escolha servidor Linux com Docker e Docker Compose, disco persistente, backup e um domínio.
2. Crie um registro DNS `A` apontando `agenda.seudominio.com.br` ao IP público da VPS.
3. Clone o repositório na VPS e execute na pasta `deploy`: `cp .env.example .env`; altere `DOMAIN` para seu domínio.
4. Libere as portas TCP 80 e 443 no firewall. Em `deploy/`, execute `docker compose up -d --build`.
5. Crie o usuário administrador somente no servidor (não via site público):
   `docker compose exec -it api python manage.py create-admin`.
6. Acesse `https://seu-dominio/` (site), `/agendar` (clientes) e `/admin` (barbeiro).
7. Antes de publicar a agenda no painel, configure serviços, preços, dias e horários. Faça uma reserva de teste anônima e aprove pelo painel.
8. No iPhone abra `/admin` pelo Safari e use Compartilhar > Adicionar à Tela de Início; Android Chrome: menu > Instalar app; PC Chrome/Edge: instalar app.

O painel no celular exige internet. Solicitações e alterações ficam no servidor, não são armazenadas offline. HTTPS é necessário para instalar a PWA fora de localhost.

## Dados e disponibilidade

- Banco: volume Docker `agenda-data`. **Não** inclua a pasta `data`, arquivos `.env` ou credenciais no repositório.
- SQLite suporta **um único processo** para este produto de um barbeiro. Não configure múltiplos workers ou réplicas. Uma futura arquitetura multi-barbearias exige migração para PostgreSQL, backups e isolamentos por conta.
- Antes de trocar o servidor ou atualizar a aplicação, faça backup consistente do banco. Uma forma segura é usar o utilitário `sqlite3` e seu comando `.backup` dentro da VPS, com permissões restritas. Para backups consistentes, não copie apenas `agenda.sqlite3` enquanto o serviço estiver escrevendo em modo WAL.
- HTTPS e cookies seguros estão habilitados nesta implantação. Proteja o painel com senha forte, aplicação de atualizações, firewall e backups automáticos; considere MFA antes de escalar o produto. API admin continua protegida por sessão e CSRF, mesmo quando a interface `/admin` é acessível na web.
- O código inclui limitação básica de tentativas de login e de novas reservas, mas um ambiente público exige limitação de requisições no proxy/WAF, monitoramento, tratamento de privacidade/LGPD e política de retenção de dados.
- O feed privado `.ics` inclui dados de clientes, **não compartilhe sua URL**.

## WhatsApp

A publicação do site **não ativa mensagens automáticas**. A integração exige credenciais oficiais de WhatsApp Business Platform, consentimento, templates aprovados e webhook configurado em HTTPS. A configuração padrão mantém `REMINDERS_ENABLED=0`.

## Teste local

Em Windows, continue usando `INICIAR_WINDOWS.bat`. A PWA pode ser testada em `http://127.0.0.1:5500/admin` no próprio PC, porém para instalar no celular é necessário publicar com HTTPS (não basta o IP 127.0.0.1 do PC).

