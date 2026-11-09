# MeshQuest · Come si gioca

> **Lingue:** [English (documentazione principale)](GAMEPLAY.md) · Italiano (questa pagina) · [Altre traduzioni](TRANSLATIONS.md)

**Stato:** la v0.2.0-alpha include la progressione simulata, tre missioni, capitoli narrativi e un profilo giocatore consultabile dal sito. **L'adapter radio Meshtastic reale, i comandi `!checkin`, la registrazione autonoma degli utenti e il traceroute automatico non sono ancora implementati.**

## Una sessione di gioco — comportamento previsto

1. Il giocatore configura il canale secondario `MeshQuest` e collega il proprio NodeID all'account Web (verifica da realizzare).
2. Esplora con un normale dispositivo Meshtastic. La posizione GPS non è obbligatoria.
3. Invia `!checkin` per richiedere la misura di un percorso attraverso la rete radio; il gateway deve risultare raggiungibile via LoRa, non soltanto tramite MQTT/Internet.
4. Il gateway esegue un **nuovo traceroute**, conserva distinti percorso di andata e ritorno e trasmette l'osservazione al server di Pisa tramite HTTPS autenticato.
5. Il server scarta i duplicati, assegna 50 XP per ogni **nuovo avamposto identificato e approvato** sul ritorno, aggiorna missioni e livelli e, in futuro, risponde via radio.

I normali avamposti sono relay Meshtastic e **non richiedono un computer, Internet né il canale MeshQuest**. Un relay privo della chiave del canale può inoltrare, ma nel traceroute potrebbe risultare un hop sconosciuto: non possiamo attribuirgli con certezza un NodeID né assegnargli una conquista individuale. La misura traceroute è diversa dal percorso seguito dal precedente messaggio di gioco e la tratta andata può differire dal ritorno.

## Le prime missioni

| Missione | Obiettivo | Ricompensa |
|---|---|---|
| Primo Eco | Scoprire un primo avamposto identificato e approvato | 50 XP della scoperta |
| Il Cartografo | Scoprire due avamposti diversi | Capitolo II |
| L'Archivio Perduto | Scoprire tre avamposti diversi | Capitolo III |

Ogni avamposto unico valido vale 50 XP, **una sola volta per giocatore**. Lo sblocco delle missioni non aggiunge XP, per non premiare più volte lo stesso evento. Gli hop sconosciuti e i nodi non approvati non danno punti. Le soglie iniziali dei livelli sono 0, 100, 250, 450 e 700 XP. Le classifiche implementate sono totale e mese corrente; le stagioni vere arriveranno più avanti.

## Prova subito il gioco simulato — senza trasmettere in radio

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install '.[test]'
python scripts/demo_game.py --lang it
python -m pytest -q
```

La simulazione utilizza il vero backend, un database temporaneo, tre avamposti inventati e tre osservazioni sintetiche. Mostra XP, missioni e livelli; cancella il database temporaneo alla fine. **Non è un test di copertura RF.**

Avviando `python -m meshquest` puoi consultare `/` per classifica e missioni, `/api/v1/game/rules?lang=it` per le regole e `/api/v1/players/<NodeID>/profile?lang=it` per il profilo di un giocatore già registrato nel database locale.

**Limitazione di sicurezza:** il token autentica il gateway che invia l'osservazione, non garantisce da solo la veridicità del percorso radio. Prima di una classifica pubblica reale servono verifica della proprietà dei nodi, limiti alle richieste, revoca token e test hardware.
