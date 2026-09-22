# Transcritor pessoal · Deepgram

Aplicação web local para transcrever **um arquivo por vez** e baixar **TXT, Markdown e JSON**, sem banco, histórico de transcrições ou cadastro de usuários. Apenas as credenciais configuradas pela interface são persistidas em um volume Docker.

## Iniciar no Ubuntu WSL / Docker Desktop

1. Deixe o Docker Desktop aberto no Windows e habilite sua distribuição em **Settings → Resources → WSL Integration**.
2. No terminal Ubuntu:

   ```sh
   git clone https://github.com/halysschreiner/deepgram.git
   cd deepgram
   cp -n .env.example .env
   chmod 600 .env
   nano .env
   ```

3. A chave do [console Deepgram](https://console.deepgram.com/) pode ser configurada pela interface depois de iniciar. Se preferir, preencha `DEEPGRAM_API_KEY` no `.env` como configuração inicial. Nunca coloque a chave em arquivos versionados.
4. Inicie:

   ```sh
   docker compose up -d --build
   ```

5. Abra **http://localhost:8765** no navegador do Windows. Se o encaminhamento de localhost do WSL não funcionar, confira a integração do Docker Desktop com a distribuição. A aplicação aceita somente os hosts listados em `ALLOWED_HOSTS` (padrão: `localhost`, `127.0.0.1`, `::1`).

   Para acessar de outra máquina — por exemplo pelo Tailscale — ajuste as duas variáveis juntas: `BIND_ADDR` com o IP da interface a publicar e `ALLOWED_HOSTS` acrescentando esse IP e o nome MagicDNS. Uma sem a outra resulta em conexão recusada ou em `403`.

## Trocar a API Key pela interface

No cabeçalho, abra **API Key**, cole a nova chave e clique em **Salvar e usar**. A alteração vale imediatamente para as próximas requisições, sem SSH, edição do `.env` ou reinicialização. O saldo é atualizado automaticamente, e o arquivo selecionado e a transcrição exibida são preservados. Transcrições já iniciadas continuam com a chave anterior.

O **ID do projeto** é opcional e serve para consultar o saldo quando a chave acessa vários projetos. Ao trocar de conta, limpe o campo para detecção automática ou informe o novo projeto. Deixar a API Key vazia mantém a chave atual e permite alterar apenas o projeto. A chave atual nunca é exibida no formulário.

A configuração salva fica em `/app/data/credentials.json`, no volume Docker `settings`, com permissão `0600`, e tem prioridade sobre `DEEPGRAM_API_KEY` e `DEEPGRAM_PROJECT_ID` do `.env`. Sobrevive a reinícios e recriações normais do container. `docker compose down -v` remove esse volume e suas credenciais; sem o arquivo salvo, a aplicação volta a usar o `.env`. Alterar somente o `.env` não substitui uma chave já salva pela interface.

Para instalar esta melhoria em uma versão anterior, execute uma vez `docker compose up -d --build` e atualize a página. As trocas seguintes são feitas pela interface.

A indicação **Chave configurada** informa que existe uma credencial salva ou no ambiente. Salvar não valida a chave no provedor nem consome créditos de transcrição; a validade e as permissões são verificadas nas chamadas à Deepgram. Uma falha na consulta de saldo não impede transcrições.

## Usar

1. Selecione ou arraste um arquivo. O limite padrão é 500 MB.
2. Escolha o modelo e o idioma. Padrão: **Nova-3 / Português (Brasil)**.
3. Ative separação de falantes quando houver mais de uma pessoa.
4. Ajuste as opções avançadas, se necessário, e confira a estimativa.
5. Clique em **Transcrever áudio** e mantenha a aba aberta.
6. Revise a prévia. Escolha TXT, Markdown ou JSON e clique em **Baixar arquivo**. Pode baixar os três: **a troca de formato não chama a API novamente**.

O texto é mostrado como texto simples, inclusive no modo Markdown (sem executar HTML). JSON contém a resposta completa da Deepgram, com metadados e palavras quando retornados pela API. Marcas de tempo e rótulos de falantes alteram apenas TXT/MD e podem ser trocados depois de transcrever. Ao desativar ambos, os parágrafos retornados pela API são preservados.

**Limpar**, atualizar ou fechar a aba descarta o resultado do aplicativo. Os arquivos baixados permanecem na pasta de downloads escolhida no navegador.

## Aparência

No cabeçalho, abra **Aparência** para escolher **Claro**, **Escuro** ou **Automático** (padrão, acompanha o sistema). Escolha também a cor de destaque: azul, roxo, rosa, vermelho, laranja, amarelo, verde (padrão) ou grafite.

As preferências ficam salvas neste navegador e são sincronizadas entre abas do mesmo endereço. Trocar tema ou cor preserva o arquivo selecionado e a transcrição. Se o navegador bloquear o armazenamento, a escolha funciona durante a sessão da página.

## Créditos restantes

A faixa **Créditos restantes do projeto** consulta o saldo real informado pela API da Deepgram ao abrir a página, ao terminar uma tentativa de transcrição e ao clicar em **Atualizar saldo**. Mostra o horário da consulta; o provedor pode demorar para refletir o último uso. Não subtrai a estimativa local dos créditos nem presume que o saldo inicial seja US$ 200.

A chave ativa precisa permitir **`project:read`** (descobrir o projeto) e **`billing:read`** (ler os créditos), além das permissões usadas para transcrever. Uma chave pode transcrever normalmente e ainda assim não ter acesso ao saldo.

Se aparecer a mensagem de falta de permissão, crie no console Deepgram uma chave do mesmo projeto com as permissões necessárias, abra **API Key** e salve a nova chave. Os papéis `admin` e `owner` incluem leitura de faturamento; `member` não inclui. Prefira os escopos específicos quando disponíveis. A aplicação não altera permissões na sua conta.

Quando a chave acessa apenas um projeto, ele é identificado automaticamente. Se acessar vários, preencha **ID do projeto** na janela **API Key** com o projeto usado para transcrever. Os saldos de uma mesma moeda são somados dentro desse projeto; moedas diferentes são mostradas separadamente. Falhas de consulta aparecem como **Indisponível**, sem inventar saldo zero, e não bloqueiam os uploads.

## Modelos e opções

- **Nova-3:** recomendado; idioma explícito, detecção do idioma predominante ou alternância entre os dez idiomas do modo multilíngue.
- **Nova-2:** alternativa para comparação. Esta interface não expõe seu modo bilíngue espanhol/inglês.
- Lista selecionada de idiomas compatíveis por modelo (21 no Nova-3 e 20 no Nova-2). Não pretende reproduzir todo o catálogo de idiomas da Deepgram.
- Pontuação, formatação inteligente e parágrafos. Formatação inteligente/parágrafos podem ativar pontuação implicitamente no provedor.
- Separação de falantes: `diarize_model=latest`, `v1` ou `v2`. Os nomes reais dos interlocutores não são identificados.
- Marcas de tempo e pausa entre falas, com `utterances=true` e `utt_split`.
- Canais separados (`multichannel`): cada canal transcrito é cobrado separadamente.
- Termos específicos: um por linha; enviados como parâmetros repetidos `keyterm` no Nova-3 ou `keywords` no Nova-2. Sem pesos. Limite local: 50 termos / 2.000 caracteres; Nova-3 também impõe 500 tokens.
- Substituições: `origem => destino`, uma por linha. Destino vazio remove a expressão.
- Interjeições e filtro de palavrões: esta interface restringe essas opções ao inglês explícito.
- Exclusão do programa de melhoria da Deepgram (`mip_opt_out`), opcional. Pode alterar o preço; confira as condições da conta.

Flux é destinado a streaming conversacional e não aparece neste fluxo de arquivos gravados. Whisper não foi incluído nesta primeira versão. Recursos nativos de resumo/análise não foram incluídos: o objetivo é transcrição, com foco em português.

Formatos aceitos na interface: MP3, WAV, M4A, OGG, OPUS, FLAC, AAC, MP4, WEBM, AIFF/AIF, AMR e WMA. O arquivo precisa conter áudio em codec reconhecido pela Deepgram. Não há conversão local de mídia. O navegador pode não reproduzir alguns formatos; isso não impede o envio.

## Estimativa de custo

Referência pública Pay As You Go consultada em **21/09/2026**, para áudio gravado:

| Opção | US$/minuto |
| --- | ---: |
| Nova-3, idioma único | 0,0043 |
| Nova-3, multilíngue | 0,0052 |
| Termos específicos no Nova-3 | +0,0013 |

A estimativa usa a duração lida pelo navegador; o saldo real é consultado separadamente na faixa de créditos. A estimativa não garante a fatura e não desconta créditos promocionais. Nas combinações sem preço confiável (Nova-2, detecção automática, canais separados, exclusão do programa de melhoria ou duração ilegível), a interface orienta consultar o console. Revise `catalog.py` quando a tabela da Deepgram mudar.

## Dados e acesso

- Por padrão a porta é publicada somente em `127.0.0.1`, sem exposição à rede local. `BIND_ADDR` escolhe a interface: use o IP de uma interface específica (como a do Tailscale) em vez de `0.0.0.0`, que abriria o serviço para toda a LAN. Não é uma aplicação para publicar na internet: não tem login, e quem alcança a porta pode transcrever e trocar a configuração da Deepgram.
- A chave inicial pode vir do ambiente. As credenciais salvas pela interface ficam no volume privado do servidor, em texto simples com acesso restrito ao usuário do aplicativo; proteja também os backups desse volume. O formulário envia a chave ao servidor, que nunca a devolve nas respostas. O aplicativo não a salva em localStorage/sessionStorage nem em logs. Use HTTPS ou um canal privado como Tailscale ao acessar remotamente.
- O áudio **não é bufferizado**: o corpo da requisição é repassado à Deepgram enquanto chega, sem passar por memória nem por `/tmp`. O container usa ~40 MB de RAM tanto para um arquivo de 3 MB quanto para um de 2 GB. Não são criados históricos locais de áudio/transcrição.
- O container roda sem root, com sistema de arquivos somente leitura, exceto `/tmp` e o volume de credenciais em `/app/data`. Áudio e transcrições não são persistidos nesse volume. Logs de acesso HTTP estão desativados; erros internos registram apenas a classe da exceção, sem texto, áudio ou chave.
- O áudio é enviado pela internet à Deepgram. A ausência de histórico neste aplicativo não define a política de retenção do provedor; valem as condições da sua conta e a opção `mip_opt_out` escolhida.
- Uma transcrição por vez, inclusive entre abas. O servidor não repete requisições automaticamente. Após timeout/interrupção, confira o console antes de reenviar: a Deepgram pode já ter processado/cobrado o áudio.

## Configuração

| Variável no `.env` | Padrão | Uso |
| --- | --- | --- |
| `DEEPGRAM_API_KEY` | vazio | Chave inicial; a configuração salva pela interface tem prioridade |
| `DEEPGRAM_PROJECT_ID` | vazio | Projeto inicial opcional; a configuração salva pela interface tem prioridade |
| `PORT` | `8765` | Porta local do navegador |
| `BIND_ADDR` | `127.0.0.1` | Interface onde a porta é publicada |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,::1` | Allowlist exata do header `Host` (barra DNS rebinding). Mantenha `127.0.0.1`: o healthcheck usa esse host |
| `MAX_UPLOAD_MB` | `500` | Limite de upload, entre 1 e 2048 MB. O teto é o da própria Deepgram: 2 GB por arquivo |
| `DEEPGRAM_TIMEOUT_SECONDS` | `1800` | Espera de resposta, entre 30 e 3300 segundos |

O tamanho do arquivo não consome RAM do host, mas a Deepgram devolve `504` quando o **processamento** dela passa de 10 minutos (20 no Whisper) — para áudios muito longos isso, e não o limite de upload, é o que costuma falhar. Extrair só a trilha de áudio (`ffmpeg -i entrada.mp4 -vn -ac 1 -c:a aac -b:a 64k saida.m4a`) reduz o envio em ~30x sem perder qualidade de transcrição. O timeout não é cancelamento garantido no provedor.

## Operação

```sh
docker compose ps
docker compose logs --tail=50
docker compose down
docker compose up -d
```

`restart: unless-stopped` permite reiniciar o serviço junto com o Docker. Após alterações no código, use `docker compose up -d --build`.

## Desenvolvimento e testes

Python + Flask + Gunicorn + Requests, HTML/CSS/JavaScript sem build de frontend. Um worker com quatro threads atende a interface enquanto a chamada da API está em andamento; o lock impede uma segunda transcrição. **Não aumente o número de workers** sem substituir o lock por um mecanismo compartilhado.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
node tests/transcript.test.mjs
```

Teste opcional de navegador (container iniciado):

```sh
.venv/bin/pip install playwright
.venv/bin/playwright install chromium
.venv/bin/python tests/browser_smoke.py
.venv/bin/python tests/browser_settings.py
```

O teste do navegador usa áudio sintético e intercepta a chamada de transcrição; **não consome créditos**. Capturas ficam em `test-results/`, ignorado pelo Git e pelo Docker. É possível usar Chromium existente com `CHROMIUM_EXECUTABLE` e outra URL local com `APP_URL`.

`browser_settings.py` inicia um servidor temporário com credenciais fictícias e armazenamento isolado. Verifica o salvamento real pela interface sem modificar a configuração do container nem chamar a Deepgram. Fora do Docker, o caminho padrão é `data/credentials.json` (ignorado pelo Git); `SETTINGS_FILE` permite escolher outro caminho.

## Versionamento e releases

O projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/) no formato `MAJOR.MINOR.PATCH`. A versão mais recente está em [`VERSION`](VERSION) e as mudanças estão no [`CHANGELOG.md`](CHANGELOG.md). Durante o desenvolvimento, registre mudanças em **Não lançado** e atualize `VERSION` ao preparar a próxima release.

O compromisso de compatibilidade abrange a configuração documentada, o fluxo de transcrição/exportação e os formatos TXT/Markdown gerados pelo aplicativo. O JSON exportado é a resposta do provedor, cujo formato é controlado pela Deepgram.

| Tipo de mudança | Próxima versão a partir de 1.1.0 | Exemplo |
| --- | --- | --- |
| Correção compatível (`PATCH`) | `1.1.1` | Corrigir contraste de um botão no tema escuro |
| Funcionalidade compatível (`MINOR`) | `1.2.0` | Adicionar um novo formato de exportação |
| Mudança incompatível (`MAJOR`) | `2.0.0` | Remover uma configuração documentada sem manter compatibilidade |

As tags Git usam o prefixo `v` e são **anotadas**. Os dois primeiros marcos foram identificados retroativamente, preservando os commits originais:

| Tag | Commit | Conteúdo |
| --- | --- | --- |
| `v1.0.0` | `7c31928` | Aplicação inicial |
| `v1.1.0` | `c9e210a` | Temas e cores de destaque |

Esses commits antecedem a criação de `VERSION` e do changelog; por isso, os arquivos de versionamento não existem ao fazer checkout dessas duas tags. Nas próximas releases, eles devem fazer parte do commit marcado pela tag. Uma tag publicada nunca deve ser movida ou reutilizada.

### Preparar uma próxima versão

1. Escolha o número pelo impacto das mudanças. Commits `feat:` normalmente indicam `MINOR`, `fix:` indica `PATCH` e mudanças incompatíveis indicam `MAJOR`. O processo é manual: mensagens de commit não criam releases automaticamente.
2. Atualize `VERSION` (somente o número, sem `v`) e mova as mudanças de **Não lançado** para uma seção com a nova versão e a data no changelog. Atualize também os links de comparação no final do arquivo.
3. Execute os testes da seção **Desenvolvimento e testes**. Valide `docker compose config --quiet` se alterar o Compose e execute o teste de navegador se alterar a interface.
4. Inclua os arquivos alterados no Git e crie o commit da release, por exemplo `chore(release): 1.1.1`. Confira `git status --short`: a árvore deve estar limpa antes de criar a tag.
5. Crie a tag no commit da release e publique a branch e essa tag:

   ```sh
   release_version=$(cat VERSION)
   git tag -a "v${release_version}" -m "Release v${release_version}"
   git push --atomic origin main "v${release_version}"
   ```

Para publicar as duas tags históricas criadas localmente, use `git push --atomic origin v1.0.0 v1.1.0`. Enviar tags não envia alterações ainda sem commit. Os links históricos do changelog passam a funcionar quando as tags estiverem no GitHub.

Uma **GitHub Release** é opcional: depois de enviar a tag, selecione-a em **Releases → Draft a new release** e copie a seção correspondente do changelog. Criar uma tag não publica uma GitHub Release nem uma imagem Docker automaticamente.

Para consultar as versões locais:

```sh
cat VERSION
git tag --list --sort=-version:refname
git show --no-patch v1.1.0
```

## Referências

- [API de arquivos gravados](https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded)
- [Modelos e idiomas](https://developers.deepgram.com/docs/models-languages-overview)
- [Separação de falantes](https://developers.deepgram.com/docs/diarization)
- [Termos específicos](https://developers.deepgram.com/docs/keyterm)
- [Recursos por idioma](https://developers.deepgram.com/docs/stt-pre-recorded-feature-overview)
- [Preços](https://deepgram.com/pricing)
- [Saldos do projeto](https://developers.deepgram.com/reference/manage/billing/list)
- [Permissões e papéis](https://developers.deepgram.com/guides/deep-dives/working-with-roles)
