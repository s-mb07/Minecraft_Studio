# Minecraft Studio

**Des méthodes et des skills gratuits et open source pour que Claude crée des modpacks Minecraft avec toi, de l'idée à la release.**

[English](README.md)

Installe ce plugin dans Claude Code et dis-lui *« fais-moi un modpack dark fantasy en 1.21.1 »*. Claude travaille
comme un lead developer. Il pose les questions qui manquent, choisit des mods **existants** qui sortent vraiment
pour ta version, vérifie les dépendances, écrit les quêtes et les scripts d'équilibrage, teste que le pack démarre
et exporte un `.mrpack`. Il travaille seul et ne s'arrête que pour les actions à risque, et rien n'est considéré
comme « fini » sans une preuve fournie par un outil.

> v0.1 : **modpacks** faits avec des mods existants. v0.2 : **tes propres mods** (Fabric / NeoForge 1.21.1, modèles
> Blockbench) et **l'étude de mods existants** (décompilation, explication, réutilisation avec provenance).

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
| `/mc-mod [idée]` | crée ou complète un mod de A à Z (scaffold → code → assets → build → tests) |

Tu peux aussi simplement parler : *« ajoute 20 quêtes pour le chapitre Create »*, *« mon pack crashe, voici le log »*.

## Fonctionnement : 8 étapes, chacune vérifiée automatiquement
1. Brief et direction artistique, 2. sélection des mods (Modrinth), 3. audit des dépendances, 4. quêtes (FTB Quests
ou advancements vanilla), 5. équilibrage (KubeJS / datapacks / configs), 6. resource pack et shaders, 7. boucle de
test et de correction, 8. export.

Les principes :
- **Autonome par défaut.** Le mode Rapide va jusqu'au bout. Le mode Équilibré montre un plan court d'abord, et le mode Guidé pose une seule fois les questions de design importantes.
- **PASS / LOOK / FAIL.** Ce qui n'a pas été mesuré est LOOK (« non vérifié »), jamais PASS.
- **Corrections bornées.** 3 tentatives (ou 10 min) maximum par problème, et la boucle s'arrête si le même crash revient.
- **Mémoire sur disque.** Le dossier `studio/` garde les faits vérifiés, les décisions, les validations et les tests.
- **Respect du travail des autres.** On ne modifie pas les mods tiers, et on ne redistribue rien sans licence.

## Créer des mods (v0.2)
Dis *« fais-moi un mod NeoForge 1.21.1 avec un bloc de cristal et une épée en obsidienne »* ou lance `/mc-mod <idée>`.
Claude part du **template officiel** (Fabric ou NeoForge MDK), écrit le code Java, génère les textures et modélise
dans **Blockbench via MCP**. Il compile ensuite, lance les GameTests et un serveur de dev, corrige seul les erreurs
et te rend le `.jar`.

Il faut Java 21 et Java 25 (le plugin Gradle actuel de Fabric, Loom, a besoin de Java 25 pour tourner). Blockbench
et son plugin MCP sont optionnels. Fabric et NeoForge 1.21.1 sont validés de bout en bout (voir `examples/`).

### Créer une créature (modèle, texture, animation)
Le skill `mc-entity-art` part d'une fiche (os, cubes, matériaux) et génère le modèle GeckoLib, une texture pixel art
(rampes de 4 teintes, lumière du haut), l'occlusion ambiante cuite avec le plugin Baked AO de Blockbench, les
animations (idle, walk, attack, hurt, death) et une planche de rendu 4 vues. `bbmodel_study.py` note le résultat
face à 11 modèles de référence. Exemple validé : `examples/ms-example-entity-neoforge-1.21.1`.

### Étudier un mod existant
Dis *« comment marche le câble d'énergie de ce mod ? »* avec un jar, un dépôt GitHub ou un lien Modrinth, ou
*« copie ce modèle et change ses couleurs »*. Le skill `mc-mod-study` importe le mod dans `studio/references/<id>/`,
le décompile (Vineflower) et l'indexe. Il trace ensuite seulement les classes utiles et étudie les modèles, les
textures, les GUI et les shaders. Puis il crée une version originale ou, si tu le demandes, copie et adapte les
fichiers voulus. La licence s'affiche en une ligne et ne bloque jamais rien. Chaque fichier réutilisé est noté dans
`studio/reuse-log.jsonl`.

**Autonomie.** Claude fait sans demander tout ce qui est local et réversible. Il ne demande confirmation que pour
publier, supprimer quelque chose d'irrécupérable, utiliser un secret, installer un logiciel sur le système ou
accepter l'EULA Minecraft (une seule fois par projet).

## Plateformes
La v0.1 automatise **Modrinth**. Les mods FTB (FTB Quests…) ne sont publiés que sur CurseForge : voir
[docs/platforms.md](plugins/minecraft-studio/docs/platforms.md).

## Contribuer
Toutes les contributions sont les bienvenues : signatures de crash, formats de pack pour les nouvelles versions,
méthodes, traductions. Voir [CONTRIBUTING.md](CONTRIBUTING.md) (en anglais).

## Licence
[MIT](LICENSE). Minecraft est une marque de Mojang/Microsoft. Ce projet n'est pas affilié à Mojang ni à Microsoft.
