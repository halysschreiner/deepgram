# Transcritor pessoal

## Register

product

## Platform

web

## Users

Pessoas que precisam transcrever arquivos de áudio em uma aplicação local executada com Docker.

## Product Purpose

Transcrever um áudio por vez com a própria conta Deepgram, escolhendo idioma, modelo e opções. Baixar TXT, Markdown e JSON sem guardar histórico.

## Positioning

Uma ferramenta local para transcrever arquivos com uma conta Deepgram.

## Design Principles

- Arquivo, idioma e modelo antes das opções avançadas.
- Gerar todos os downloads a partir da mesma resposta da API.
- Mostrar estados de envio, processamento, falha e conclusão.
- Chave configurável pela interface, persistida no servidor e aplicada nas próximas requisições sem reiniciar. O .env é a configuração inicial opcional.

## Implementation decisions

Temas claro, escuro e automático (padrão, acompanha o sistema), com oito cores de destaque inspiradas nas opções do macOS, incluindo laranja. Verde é a cor padrão. O menu Aparência no cabeçalho salva as preferências no navegador. Controles nativos, navegação por teclado e contraste legível nos dois temas.
