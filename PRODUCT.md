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
- Chave configurada uma vez no .env e usada somente no servidor.

## Implementation decisions

Decisões de interface tomadas para esta implementação: visual claro para leitura de transcrições durante o trabalho, controles nativos, teclado e contraste legíveis. Não foram solicitadas referências visuais específicas.
