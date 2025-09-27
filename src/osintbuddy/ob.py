#!/usr/bin/env python3
"""OSINTBuddy plugins CLI

This script contains the commands needed to manage an OSINTBuddy Plugins service, which is used by the OSINTBuddy project.

Basic Commands:
    Plugins service command(s):
        `ob start` : Starts the FastAPI microservice (`ctrl+c` to stop the microservice)
        `ob init` : Load the initial osintbuddy entities onto your filesystem
"""
import logging, asyncio, json
from argparse import ArgumentParser
import httpx
from pyfiglet import figlet_format
from termcolor import colored
from pydantic import BaseModel
from osintbuddy import Registry, __version__, load_plugins_fs
from osintbuddy.utils import to_snake_case

APP_INFO = \
"""
____________________________________________________________________
| If you run into any bugs, please file an issue on Github:
| https://github.com/osintbuddy/plugins
|___________________________________________________________________
| OSINTBuddy plugins: v{osintbuddy_version}
| PID: {pid}
""".rstrip()

DEFAULT_ENTITIES = [
    "cse_result.py",
    "cse_search.py",
    "dns.py",
    "google_cache_result.py",
    "google_cache_search.py",
    "google_result.py",
    "google_search.py",
    "ip.py",
    "ip_geolocation.py",
    "subdomain.py",
    "telegram_websearch.py",
    "url.py",
    "username.py",
    "username_profile.py",
    "whois.py",
    "website.py"
]

def get_logger():
    log = logging.getLogger("plugins")
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)s [%(levelname)s] %(message)s')
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    log.addHandler(ch)
    return log

log = get_logger()

def _print_server_details():
    from os import getpid
    print(colored(figlet_format("OSINTBuddy plugins", font='smslant'), color="blue"))
    print(colored(APP_INFO.format(
        osintbuddy_version=__version__,
        pid=getpid(),
    ), color="blue"))
    print(colored("Created by", color="blue"), colored("jerlendds and friends", color="red"))


def start():
    _print_server_details()
    import uvicorn
    uvicorn.run(
        "osintbuddy.server:app",
        host="0.0.0.0",
        loop='asyncio',
        reload=True,
        workers=6,
        port=42562,
        headers=[('server', 'OSINTBuddy')],
        log_level='info'
    )

def load_git_entities():
    import os
    from pathlib import Path
    if not Path("./plugins").is_dir():
        log.info("directory not found, creating ./plugins")
        os.mkdir("./plugins")

    with httpx.Client() as client:
        for entity in DEFAULT_ENTITIES:
            log.info(f"loading osintbuddy entity: {entity}")
            if not Path(f"./plugins/{entity}").exists():
                data = client.get(f"https://raw.githubusercontent.com/osintbuddy/entities/refs/heads/main/{entity}")
                with open(f"./plugins/{entity}", "w") as file:
                    file.write(data.text)
                    file.close()


def init_entities():
    print("____________________________________________________________________")
    log.info("| Loading osintbuddy entities...")
    load_git_entities()
    print("____________________________________________________________________")
    log.info("Initial entities loaded!")


def printjson(value):
    print(json.dumps(value))


def prepare_run(plugins_path: str | None = None):
    import os
    if plugins_path is None:
        plugins_path = os.getcwd() + '/plugins'
    Registry.labels.clear()
    Registry.plugins.clear()
    Registry.ui_labels.clear()
    return load_plugins_fs(plugins_path)


async def run_transform(plugins_path: str, source: str, settings = None, cfg: str | None = None):
    '''
    E.g.
ob run -T '{"action":"transform:entity","entity":{"id":"4c755e2b-45d4-48e8-b8c2-c8ed546334ad","type":"telegram_websearch","data":{"label":"telegram_websearch","query":"jerlendds"},"position":{"x":-947.1913273648004,"y":-183.30472176357043},"transform":"To CSE Search"}}'
    '''
    src = json.loads(source)
    prepare_run(plugins_path)
    entity = src.pop("entity")
    transform_label = entity.pop("transform")
    source_entity_label = entity.get("data").get("label")
    plugin = await Registry.get_entity(source_entity_label)
    if plugin is None:
        # TODO: Create error handling type {"error": "api", "message": "blah blah"}
        print([])
    else:
        if cfg:
            transform_result = await plugin().run_transform(
                transform_type=transform_label,
                entity=entity,
                cfg=cfg
            )
        else:
            transform_result = await plugin().run_transform(
                transform_type=transform_label,
                entity=entity,
            )
        printjson(transform_result)


async def list_transforms(label: str, plugins_path: str | None = None):
    prepare_run(plugins_path)
    plugin = await Registry.get_entity(label)
    if plugin is None:
        return []
    transforms = plugin().transform_labels
    printjson(transforms)
    return transforms


def list_plugins(plugins_path = None):
    plugins = prepare_run(plugins_path)
    loaded_plugins = [to_snake_case(p.label) for p in plugins]
    printjson(loaded_plugins)


class EntityCreate(BaseModel):
    label: str | None = None
    author: str = "Unknown author"
    description: str = "No description found..."
    last_edit: str
    source: str | None


def list_entities(plugins_path = None):
    # dev mode plugins...
    import os, sys
    from datetime import datetime
    prepare_run(plugins_path)
    plugins = []
    for plugin in Registry.plugins.values():
        path = f"{sys.modules[plugin.__module__].__file__}"
        source = open(path, "r").read()
        last_file_edit = datetime.utcfromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
        plugins.append(dict(
            label=plugin.label,
            author=plugin.author,
            description=plugin.description,
            source=source,
            last_edit=last_file_edit,
        ))
    printjson(plugins)


async def get_blueprints(label: str | None = None, plugins_path: str | None = None):
    blueprints = {}
    prepare_run(plugins_path)
    if label is None:
        plugins = [await Registry.get_entity(to_snake_case(label))
                   for label in Registry.labels]
        for entity in plugins:
            blueprint = entity.blueprint()
            blueprints[to_snake_case(blueprint.get('label'))] = blueprint
        printjson(blueprints)
        return blueprints
    plugin = await Registry.get_entity(label)
    blueprint = plugin.blueprint() if plugin else []
    printjson(blueprint)
    return blueprint


commands = {
    "start": start,
    # "plugin create": create_plugin_wizard,
    "init": init_entities,
    "run": run_transform,
    "ls transforms": list_transforms,
    "ls plugins": list_plugins,
    "ls entities": list_entities,
    "blueprints": get_blueprints
}

def main():
    parser = ArgumentParser()
    parser.add_argument('command', type=str, nargs="*", help="[CATEGORY (Optional)] [ACTION]")
    parser.add_argument('-T', '--transform', type=str, nargs="*", help="[CATEGORY (Optional)] [ACTION]")
    parser.add_argument('-P', '--plugins', type=str, nargs="*", help="[CATEGORY (Optional)] [ACTION]")
    parser.add_argument('-L', '--label', type=str, nargs="*", help="[CATEGORY (Optional)] [ACTION]")

    args = parser.parse_args()
    cmd_fn_key = ' '.join(args.command)
    command = commands.get(cmd_fn_key)
    if command is None:
        parser.error("Command not recognized!")

    plugins_path = args.plugins if args.plugins is None else args.plugins[0]
    label = args.label if args.label is None else args.label[0]
    if "run" in cmd_fn_key:
        asyncio.run(command(plugins_path=plugins_path, source=args.transform[0]))
    elif "ls plugins" in cmd_fn_key:
            command(plugins_path=plugins_path)
    elif "ls entities" in cmd_fn_key:
        command(plugins_path=plugins_path)
    elif "ls transforms" in cmd_fn_key:
        asyncio.run(command(label=label, plugins_path=plugins_path))
    elif "blueprints" in cmd_fn_key:
        asyncio.run(command(plugins_path=plugins_path, label=label))
    else:
        command()

if __name__ == '__main__':
    main()
