# Comenzar (Getting started)

> Traducción al español — sigue la versión maestra en inglés [`docs/getting-started.md`](../../getting-started.md)
> Última sincronización: v0.3.0 (2026-04-08)
> **Borrador v0.3** — esta traducción es una versión inicial y puede estar desactualizada respecto al maestro.

Inicio rápido en 5 minutos. Al terminar tendrás un wiki navegable de cada sesión de Claude Code que hayas ejecutado.

## Requisitos previos

- Python ≥ 3.9 (macOS incluye 3.9+ por defecto; la mayoría de distribuciones Linux también)
- `git`
- Algunas sesiones de Claude Code o Codex CLI ya guardadas en el almacén de sesiones por defecto de tu Agent

Eso es todo. Sin `npm`, sin `brew`, sin base de datos, sin cuenta.

## Instalación

### macOS / Linux

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
./setup.sh
```

### Windows

```cmd
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
setup.bat
```

`setup.sh` / `setup.bat` hace lo siguiente de forma idempotente:

1. Instala `markdown` (obligatorio) con `pip install --user`. El resaltado de sintaxis usa highlight.js desde un CDN.
2. Crea los directorios `raw/`, `wiki/` y `site/`
3. Ejecuta `llmwiki adapters` para mostrar qué Agents detectó
4. Hace una ejecución en seco del primer sync para que veas qué se convertiría

## Tres comandos después de la instalación

```bash
./sync.sh        # Ingesta nuevas sesiones del almacén del Agent → raw/sessions/<project>/*.md
./build.sh       # Compila raw/ + wiki/ → site/
./serve.sh       # Sirve site/ en http://127.0.0.1:8765/
```

Abre [http://127.0.0.1:8765/](http://127.0.0.1:8765/) y prueba:

- **⌘K** o **Ctrl+K** — paleta de comandos
- **/** — enfocar la barra de búsqueda
- **g h / g p / g s** — saltar a inicio / proyectos / sesiones
- **j / k** — navegar la tabla de sesiones
- **?** — ayuda de atajos de teclado

## Siguientes pasos

- [Arquitectura](../../architecture.md) — desglose de las 3 capas Karpathy + 8 capas de build
- [Configuración](../../configuration.md) — todas las opciones de ajuste
- [Privacidad](../../privacy.md) — redacción por defecto + `.llmwikiignore` + solo localhost
- [Claude Code adapter](../../adapters/claude-code.md)
- [Obsidian adapter](../../adapters/obsidian.md)
