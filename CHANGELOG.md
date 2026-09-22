# Histórico de alterações

As versões seguem [Versionamento Semântico](https://semver.org/lang/pt-BR/).
As datas abaixo correspondem aos commits que estabeleceram cada versão.

## Não lançado

## [1.2.0] — 2026-09-22

### Adicionado

- Botão API Key com formulário para trocar a chave e o projeto de saldo sem reiniciar o container.
- Credenciais persistidas em volume Docker privado, com prioridade sobre a configuração inicial do `.env`.
- Atualização automática do saldo após salvar, preservando arquivo, opções e resultado da transcrição.
- Testes de persistência, proteção da configuração, troca durante requisições e fluxo de navegador.

### Manutenção

- Adicionados `VERSION`, este histórico e o processo documentado de releases.
- Identificadas retroativamente as versões 1.0.0 e 1.1.0 com tags Git anotadas.

## [1.1.0] — 2026-09-22

### Adicionado

- Temas claro, escuro e automático, acompanhando a preferência do sistema.
- Oito cores de destaque selecionáveis no menu Aparência.
- Preferências de aparência persistidas no navegador e sincronizadas entre abas.

## [1.0.0] — 2026-09-22

### Adicionado

- Transcrição de um arquivo por vez com Deepgram Nova-3 ou Nova-2.
- Prévia e exportação em TXT, Markdown e JSON.
- Seleção de idioma, separação de falantes e opções avançadas de transcrição.
- Estimativa de custo e consulta aos créditos restantes do projeto.
- Aplicação local com Docker Compose, upload em streaming e chave mantida no servidor.
- Testes de backend, formatação de transcrições e fluxo de navegador.

[1.2.0]: https://github.com/halysschreiner/deepgram/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/halysschreiner/deepgram/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/halysschreiner/deepgram/tree/v1.0.0
