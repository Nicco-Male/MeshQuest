# MeshQuest Engine — piattaforma multi-game (proposta)

> **Stato: progettazione, non implementazione.** La repository contiene ancora il prototipo v0.4.0-alpha: API, missioni/XP, Creator Studio preview e gateway in sola lettura. Non esistono ancora discovery radio, giochi esterni, SDK o trasmissioni comandate.

## Decisione di prodotto

MeshQuest diventa un **motore open source per giochi diversi basati su Meshtastic**. Modello **C ibrido**: giochi interni approvati, giochi esterni con API pubbliche, un Core centrale per eventi radio/identità/sessioni, una UI per scoprire e scegliere cosa giocare.

Le Raspberry Pi Zero W **ARMv6 a 32 bit** rimangono gateway leggeri con token verso il server di Pisa. I normali nodi radio non installano MeshQuest. I giochi non possono toccare configurazioni, credenziali, routing o firmware dei nodi reali.

## Game Discovery

Da un dispositivo Meshtastic su canale MeshQuest opt-in, la futura discovery dovrebbe offrire:
- **!servers**: server/gateway MeshQuest che *rispondono* via radio; non garantisce un censimento geografico.
- **!games**: giochi esposti attraverso i gateway raggiungibili.
- **!games LU1**: giochi pubblicati dal server identificato con alias LU1.
- **!info LU1 2** e **!join LU1 2**: informazioni e richiesta di iscrizione al gioco selezionato.

Le risposte devono essere brevi, su richiesta e limitate da quote RF. Un gateway può essere lontano più hop; un gioco è **raggiungibile** solo se il gateway risponde, **giocabile** soltanto se il server ammette la sessione. Account e NodeID verificati per giochi competitivi. Per il primo prototipo un solo Core Pisa, più gateway con liste giochi differenti; la federazione verrà dopo.

## Primo gioco sperimentale: Mesh Dominion (idea di Salvo)

Strategico PvP su una **rete virtuale**: conquisti nodi con puzzle/minigiochi di hacking immaginario, guadagni crediti virtuali, aumenti difese e attacchi, difendi catene e punti strategici. Se un altro giocatore conquista un nodo intermedio, **si interrompe solo il percorso nel gioco**, non il traffico Meshtastic reale.

Il proprietario verificato di un nodo fisico registrato e consenziente può ottenere una meccanica di riconquista virtuale limitata. I nodi di terzi osservati in RF **non** diventano automaticamente obiettivi conquistabili. Primo playtest proposto: 3 partecipanti, circa 12 territori tra nodi opt-in e NPC, 3 minigiochi, usando inizialmente radio simulata.

## Specifiche tecniche complete

- [Architettura, Event Envelope v1 e sicurezza](MULTIGAME_ENGINE.md)
- [Protocollo radio !servers / !games / !join](GAME_DISCOVERY.md)
- [API pubbliche, manifest e SDK Python/TypeScript](GAME_API_SDK.md)
- [Game design Mesh Dominion](GAMES/MESH_DOMINION.md)
- [Piano di migrazione e test Berry 32 bit](MULTIGAME_MIGRATION.md)

Ogni funzionalità elencata in queste specifiche è **da sviluppare** salvo indicazione esplicita di presenza nel codice.
