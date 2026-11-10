# Salvo via DM — Capitolo 1: Conquista della rete

> **Pilot live per MeshQuest sul CT 151 (Pisa).**
> I nodi, la topologia e gli attacchi sono **interamente virtuali**.
> Nessun comando cambia firmware, routing, permessi o proprieta' dei nodi
> Meshtastic reali. I crediti Salvo sono distinti dagli XP Exploration.

## Entrata in gioco

Puoi usare il discovery sul canale MeshQuest:

```text
!gateways
!use navacchio
```

Oppure scrivere direttamente in **DM** a Navacchio o Pisa, senza discovery:

```text
!play salvo
Salvo avviato: 6 crediti. !scan esplora, !status profilo.
```

Poi tutti i comandi vanno inviati **nello stesso DM**:

| Comando | Risposta / azione |
| --- | --- |
| `!play salvo` | Nuova partita o riprende una salvata |
| `!help` | Menu contestuale per Salvo |
| `!scan` | Elenca i settori virtuali raggiungibili con indice 1, 2, ... |
| `!hack 1` | Inizia un puzzle per conquistare il settore 1 |
| `!solve 12` | Propone la soluzione del puzzle in corso |
| `!map` | Mostra territori controllati e prossimi settori |
| `!status` | Saldo crediti, nodi conquistati e rendita |
| `!leave salvo` | Sospende la partita senza perdere i progressi |

## Esempio di primo nodo (i numeri del puzzle variano)

```text
Tu:          !play salvo
Navacchio:   Salvo avviato: 6 crediti. !scan esplora, !status profilo.
Tu:          !scan
Navacchio:   Accessibili: 1:Portale. !hack N (2c)
Tu:          !hack 1
Navacchio:   Puzzle Portale: 7+5=? Rispondi !solve N
Tu:          !solve 12
Navacchio:   Portale conquistato! 4c, 1 nodi. !scan
Tu:          !scan
Navacchio:   Accessibili: 1:Relay. !hack N (2c)
```

I puzzle sono mini-giochi di logica, **non hacking di dispositivi**.
Tre risposte errate bloccano nuovi tentativi per 60 secondi; un
puzzle scade dopo 120 secondi. Si pagano 2 crediti solo quando
il nodo viene conquistato, non quando si avvia il puzzle.

## Mappa del Capitolo 1

Topologia inventata, non derivata dai collegamenti RF:

```text
Portale
  └─ Relay
      ├─ Bastione ─┐
      └─ Archivio ─┴─ Torre
                       └─ Nucleo
```

Per attaccare `Torre` devi conquistare prima **sia Bastione sia
Archivio**; `Nucleo` conclude il capitolo. `!scan` mostra
solo i settori già sbloccati e non conquistati.

**Economia:** 6 crediti iniziali; 2 per conquista riuscita;
1 credito al minuto per ciascun nodo controllato; massimo 300
crediti; rendita offline limitata a 24 ore per calcolo.

## Persistenza centrale e compatibilita'

Tutte le sorgenti MeshMonitor nel pilot condividono lo stesso database SQLite
`salvo-radio.db` sul CT 151, nella directory corrente in cui lanci
`python3 -m gateway_agent.channel_discovery`. I progressi
**sopravvivono al riavvio del bot** e al cambio da Navacchio a Pisa,
pur restando per ogni NodeID del giocatore.

Non si installa nulla di Salvo sulle Raspberry Berry e non si apre
un secondo client sulla porta Meshtastic TCP 4403.

```bash
cd /opt/meshquest-radio-pilot
git pull --ff-only

python3 -m gateway_agent.channel_discovery \
  --meshmonitor-url http://192.168.10.39:3001 \
  --allow-http-lan \
  --allowed-player-node-id '!e9a04b31'
```

Nessuna dipendenza Python aggiuntiva per il motore Salvo:
usa il modulo standard `sqlite3`. Mantieni la variabile
`MM_TOKEN` esportata come nel pilot precedente.

La prima lettura dei DM dopo l'avvio ignora i messaggi storici.
Invia quindi **un nuovo** `!play salvo` in DM e prosegui.

## Limiti del pilot

- Non esiste ancora una vera verifica account-to-NodeID: il NodeID radio
  identifica provvisoriamente la partita. Per l'alpha il bot può usare
  `--allowed-player-node-id`. Niente ricompense pubbliche o PvP.
- Questo motore radio è **un sottosistema di playtest sul server centrale**,
  separato dagli endpoint admin-only del prototipo SQLAlchemy Salvo.
  L'integrazione unificata con API, account e database principale
  arriverà prima della beta pubblica.
- Un solo processo bot TX attivo alla volta: i cooldown dei messaggi e
  la de-duplicazione radio sono attualmente in memoria.
- Non c'è ancora un Creature Studio di capitoli Salvo né uno stato
  persistente per la scelta del gateway DM. La partita e i crediti,
  invece, sono persistenti.
