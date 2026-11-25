# Minecraft Studio

**Des méthodes et des skills gratuits et open source pour que Claude crée des modpacks Minecraft avec toi, de l'idée à la release.**

[English](README.md)

Installe ce plugin dans Claude Code et dis-lui *« fais-moi un modpack dark fantasy en 1.21.1 »*. Claude travaille
comme un lead developer. Il pose les questions qui manquent, choisit des mods **existants** qui sortent vraiment
pour ta version, vérifie les dépendances, écrit les quêtes et les scripts d'équilibrage, teste que le pack démarre
et exporte un `.mrpack`. Chaque étape attend ta validation, et rien n'est considéré comme « fini » sans une preuve
fournie par un outil.

> La v0.1 couvre les **modpacks faits avec des mods existants**. La création de mods Java viendra plus tard
> (en attendant, `/mc-setup` peut installer des skills de modding externes).

## Installation
Dans Claude Code :
```
/plugin marketplace add s-mb07/Minecraft_Studio
/plugin install minecraft-studio@minecraft-studio
```
Il faut Python 3.9+. Java n'est nécessaire que pour le test de démarrage serveur. Prism Launcher est conseillé
pour les tests côté client.

## Utilisation
| Commande | Rôle |
|---|---|
| `/mc-new [dossier] [idée]` | pose les questions du brief et crée l'espace de travail |
| `/mc-setup` | installe des skills / serveurs MCP tiers vérifiés (en demandant d'abord) |
| `/mc-audit` | lance toutes les vérifications et donne un score de santé |
| `/mc-release 1.0.0` | construit le `.mrpack` (+ server pack), les crédits et le changelog |

Tu peux aussi simplement parler : *« ajoute 20 quêtes pour le chapitre Create »*, *« mon pack crashe, voici le log »*.

## Fonctionnement : 8 étapes, chacune avec sa validation
1. Brief et direction artistique, 2. sélection des mods (Modrinth), 3. audit des dépendances, 4. quêtes (FTB Quests
ou advancements vanilla), 5. équilibrage (KubeJS / datapacks / configs), 6. resource pack et shaders, 7. boucle de
test et de correction, 8. export.

Les principes :
- **Plan → validation → action.** Claude propose le plan de chaque étape et attend ton accord.
- **PASS / LOOK / FAIL.** Ce qui n'a pas été mesuré est LOOK (« non vérifié »), jamais PASS.
- **Corrections bornées.** 5 tentatives maximum par problème, et la boucle s'arrête si le même crash revient.
- **Mémoire sur disque.** Le dossier `studio/` garde les faits vérifiés, les décisions, les validations et les tests.
- **Respect du travail des autres.** On ne modifie pas les mods tiers, et on ne redistribue rien sans licence.

## Plateformes
La v0.1 automatise **Modrinth**. Les mods FTB (FTB Quests…) ne sont publiés que sur CurseForge : voir
[docs/platforms.md](plugins/minecraft-studio/docs/platforms.md).

## Contribuer
Toutes les contributions sont les bienvenues : signatures de crash, formats de pack pour les nouvelles versions,
méthodes, traductions. Voir [CONTRIBUTING.md](CONTRIBUTING.md) (en anglais).

## Licence
[MIT](LICENSE). Minecraft est une marque de Mojang/Microsoft. Ce projet n'est pas affilié à Mojang ni à Microsoft.
