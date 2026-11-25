# Plan — Linerator

## Objectif

Un testeur de **get_next_line** (sujet version 14.3), autonome et branchable dans 42pal, avec la même interface que Pushterator : un accueil qui trouve le projet, le run en direct, le rapport, et un visualiseur des lectures. `./linerator ../get_next_line` (ou sans chemin : il cherche le projet).

**Le plan est fini quand** un étudiant lance `./linerator`, choisit sa get_next_line, voit en direct le projet, les lignes pour chaque BUFFER_SIZE, l'entrée standard, les fd invalides, les pannes de malloc et de read, la quantité lue, le bonus et les fuites, peut rejouer les lectures dans le visualiseur, et que 42pal le lance depuis son menu Testers.

## Décisions (2026-11-25)

- **Nom** : Linerator (`~/Desktop/linerator`, plus tard `Blaeste/Linerator` ; rien de créé ni de poussé sans accord). Paquet Python `liner`.
- **Interface** : comme Pushterator (plein écran, `--plain`, `--json` format 1, `--stream`) ; branché dans 42pal une fois testé par l'utilisateur.
- **Extras** : visualiseur des lectures, pannes injectées (chaque malloc à tour de rôle, read() qui renvoie -1), « lire le moins possible », bonus (plusieurs fd, une seule static).
- **Moteur** : get_next_line est une fonction : un programme de test C est compilé avec les fichiers de l'étudiant pour chaque BUFFER_SIZE. Le suivi mémoire vient du moteur de libfterator (blocs collés à une page protégée, quarantaine après free, échecs de malloc) ; read() est intercepté aussi (`ld --wrap`). Linux et WSL seulement, comme libfterator.
- **Aucune get_next_line qui marche dans le dépôt** (comme la libft de référence de libfterator) : les faux programmes des tests passent par stdio (fonctions interdites, donc impossibles à rendre) ; une référence locale éventuelle reste dans `selftest/`, ignoré par git. Aucun sujet de 42 dans le dépôt.
- **Disclaimer** : en bas de l'accueil et à la fin du rapport, « un outil d'aide, pas un oracle ».

## Ce qui est vérifié

| Étape | Contrôles |
|---|---|
| Projet | `get_next_line.c`, `get_next_line_utils.c`, `get_next_line.h` à la racine, le prototype dans le header, compile avec `-Wall -Wextra -Werror` avec et sans `-D BUFFER_SIZE`, pas de libft, pas de variable globale, seules `read`, `malloc` et `free` (pas de `lseek`), la norminette, le README imposé (avec l'explication de l'algorithme) |
| Lignes | des fichiers variés (vide, une ligne avec ou sans `\n`, que des `\n`, lignes longues, dernière ligne sans `\n`, beaucoup de lignes, UTF-8) pour chaque BUFFER_SIZE (1, 2, 3, 5, 10, 42, 100, 1000, 9999, 10000000, et sans `-D`) |
| Entrée standard | les mêmes fichiers lus sur le fd 0 |
| fd | -1, un fd jamais ouvert, un fd fermé entre deux appels : `NULL`, sans crash ni fuite |
| Pannes | chaque malloc échoue à tour de rôle ; read() renvoie -1 au premier appel et en cours de route : `NULL`, sans fuite ni crash |
| Lire peu | les octets lus avant la première ligne rendue : au plus la ligne et un BUFFER_SIZE ; échec si tout le fichier est lu |
| Fuites et mémoire | tout est libéré quand `NULL` est rendu ; lectures et écritures hors des blocs, double free, accès après free |
| Bonus | plusieurs fd lus en alternance ; une seule variable static |
| Cas indéfinis | fichier binaire, BUFFER_SIZE=0 : montrés, non comptés |

## Étapes

Chaque étape en TDD, puis les tests utilisateur.

1. **Squelette** : lanceur, paquet, `vendor/`, langues, `--version`.
2. **Le moteur C** : le programme de test (modes lignes, entrée standard, fd, fd fermé, plusieurs fd, trace), malloc/free/read interceptés, pannes, compte des lectures. *Vérif* : tests avec de faux get_next_line en stdio.
3. **La compilation** par BUFFER_SIZE, sur une copie du projet.
4. **Les cas et le jugement** (lignes attendues calculées en Python).
5. **Le projet** : fichiers, header, compilation, libft, globales, fonctions externes, norme, README, bonus et static.
6. **Le moteur complet, le rapport, JSON, stream.**
7. **Le plein écran** (accueil, run en direct, panneau des BUFFER_SIZE, rapport).
8. **Le visualiseur des lectures.**
9. **Français, README, captures.** 10. **Dans 42pal.**
