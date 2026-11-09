# Horta Escolar 3.0 — início rápido

## 1. Administrador

A organização Supabase conectada exibe o e-mail `pedrohenriqueoliveiragms0309@gmail.com`, que foi autorizado provisoriamente como gestor. Se esse não for seu e-mail, altere a entrada na tabela segura `horta_internal.contas_autorizadas` no SQL Editor do projeto antes de cadastrar sua conta.

1. Acesse https://horta-escolar-pedroh-2026.onrender.com
2. Selecione **Administrador → Primeiro acesso? Cadastrar**.
3. Digite o e-mail autorizado e a senha que você escolher; confirme o e-mail recebido, se for solicitado.
4. Retorne à tela **Administrador** e entre.

As senhas são gerenciadas pelo **Supabase Auth**, nunca pelo navegador ou GitHub. Não divulgue a senha de administrador. Senhas sequenciais (como uma sequência de 1 a 12) são previsíveis e não recomendadas.

## 2. Vendedor

Depois de entrar como gestor, abra **Configurações → Ativar conta do vendedor** e defina uma senha. O sistema cria o usuário operacional **`usuario123`** no Supabase Auth. O vendedor entra com usuário `usuario123` e a senha configurada pelo gestor. Uma senha como `12345678` é muito fraca; escolha outra mais segura.

Se o vendedor já tiver sido criado, a função recusará uma segunda criação para evitar redefinição indevida. Para alterar a senha, use **Supabase Dashboard → Authentication → Users**.

## 3. Matriz de acesso

| Recurso | Administrador | Vendedor |
|---|---|---|
| Visualizar estoque e preço | Sim | Sim |
| Registrar vendas | Sim | Sim |
| Ver vendas de toda a equipe | Sim | Não (apenas próprias) |
| Cancelar vendas | Sim | Não |
| Atualizar estoque/preço | Sim | Não |
| Lançar despesas/investimentos | Sim | Não |
| Plantio, colheita, equipe | Sim | Não |
| Exportar Excel e backup | Sim | Não |

As políticas RLS do PostgreSQL também bloqueiam as operações proibidas por API direta. O preço e a baixa de estoque das vendas são calculados no banco por gatilhos SQL, não confiando em valores vindos do navegador. As vendas antigas mantêm o preço aplicado no dia.

## 4. Preço e estoque

- Valor inicial do produto: **R$ 4,00 por pé de alface**, estimativa para um projeto escolar (não é cotação contratual nem preço específico da cidade).
- Referência da pesquisa: https://indice.custoporprato.com.br/products/alface-unidade, amostra de varejo de setembro e outubro de 2026 (R$ 3,98/unidade).
- Estoque inicial: **zero**. O administrador deve registrar o estoque disponível antes das vendas.
- Quando o estoque acabar, o banco rejeita novas vendas; nenhuma venda pode reduzir o estoque abaixo de zero.
- Ao cancelar uma venda, o estoque é devolvido automaticamente.

## 5. Limitações atuais

Não há migração automática de dados locais anteriores sem importar os registros antigos no Supabase. O banco novo está vazio. Os dados previamente salvos no navegador no protótipo 2.0 continuam no aparelho de origem e não aparecem automaticamente na versão 3.0. Para migrá-los é necessário tratar duplicidades e importá-los para o PostgreSQL.

O gerenciamento de senhas e contas usa o Supabase Auth. Para auditoria individual da equipe, o recomendado futuramente é cadastrar uma conta por vendedor, em vez de compartilhar o mesmo login operacional.