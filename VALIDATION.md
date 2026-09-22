# Validação · 21/09/2026

- Imagem Docker construída com sucesso.
- Container iniciado com healthcheck saudável, porta publicada somente em `127.0.0.1:8765`.
- 14 testes Python passaram: validação de parâmetros, idiomas e modelos; termos repetidos; separação de falantes; upload binário com arquivo acima do limite de spool; fechamento do temporário; tamanho; arquivo vazio/ausente/duplicado; JSON inválido; falta de chave; bloqueio de concorrência; erros e timeout da Deepgram; ausência de repetição automática; proteção de origem/Host; chave não exposta na configuração.
- 7 testes JavaScript passaram: TXT, Markdown, JSON integral, falante zero, marcas de tempo, parágrafos, múltiplos canais, nomes de download, áudio sem fala e estimativa de custo.
- Chromium: configuração sem chave; seleção de áudio sintético; duração local; opções compatíveis por modelo/idioma; transcrição simulada; download de TXT/MD/JSON com uma única chamada; limpar; erro do provedor; descarte ao recarregar; ausência de erros JavaScript.
- Layout inspecionado em desktop e celular; sem overflow horizontal nas larguras 390, 768 e 1024 px.

Os testes automatizados usam respostas simuladas da API. O teste ponta a ponta com a Deepgram requer uma chave no `.env` e um arquivo de áudio. `Chave configurada` não significa que a credencial foi validada pelo provedor.

## Melhoria: saldo de créditos

- 22 testes Python passaram (14 existentes + 8 para saldo): soma decimal por moeda, zero/negativos reais, atualização, seleção do projeto, ausência de chave/token, permissões, respostas inválidas e falhas de rede independentes das transcrições.
- Navegador: saldo simulado carregado, atualização manual e após transcrição, mensagem para falta de permissão e upload habilitado apesar da falha de saldo. Regressão de downloads e layouts desktop/celular passou.

## Melhoria: aparência · 22/09/2026

- 26 testes Python e 7 testes JavaScript passaram; fluxo de navegador existente passou com respostas simuladas, sem consumir créditos.
- Chromium: temas claro, escuro e automático; mudança do sistema em tempo real; preferência manual preservada; oito cores; persistência após recarregar e sincronização entre abas.
- Menu operado por teclado, seleção de cores com setas, fechamento com Escape e retorno do foco. Armazenamento inválido ou bloqueado não impede a interface de funcionar.
- Contraste mínimo medido de 6,19:1 entre os pares verificados de texto/fundo (destaques, botões, texto secundário, avisos e erros), nas 16 combinações de tema e cor.
- Menu dentro da tela e ausência de rolagem horizontal em 320, 390, 650, 768 e 1024 px; capturas de desktop e celular em `test-results/appearance-*.png`.
- Container reconstruído e saudável. Fluxo completo validado no serviço atualizado: troca de tema/cor preservou o arquivo e a transcrição, com download dos três formatos e apenas uma chamada de transcrição simulada.
