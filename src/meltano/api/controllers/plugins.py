from itertools import groupby
from flask import request, jsonify, g

from meltano.api.json import freeze_keys
from meltano.core.error import PluginInstallError
from meltano.core.plugin_discovery_service import (
    PluginDiscoveryService,
    PluginNotFoundError,
)
from meltano.core.plugin import PluginType
from meltano.core.project import Project
from meltano.core.project_add_service import ProjectAddService
from meltano.core.config_service import ConfigService
from meltano.core.plugin_install_service import PluginInstallService
from meltano.api.security import api_auth_required
from meltano.api.security.readonly_killswitch import readonly_killswitch
from meltano.api.api_blueprint import APIBlueprint


pluginsBP = APIBlueprint("plugins", __name__)


@pluginsBP.errorhandler(PluginInstallError)
def _handle(ex):
    return (jsonify({"error": True, "code": str(ex)}), 502)


@pluginsBP.route("/all", methods=["GET"])
def all():
    project = Project.find()
    discovery = PluginDiscoveryService(project)
    ordered_plugins = {}

    for type, plugins in groupby(discovery.plugins(), key=lambda p: p.type):
        frozen_plugins = []
        for plugin in plugins:
            froze_plugin = plugin.canonical()
            if "settings" in froze_plugin:
                for setting in froze_plugin["settings"]:
                    if "value" in setting:
                        if isinstance(setting["value"], dict):
                            setting_name = setting["name"]
                            setting["value"] = freeze_keys(setting["value"])
            frozen_plugins.append(froze_plugin)
        ordered_plugins[type] = frozen_plugins

    return jsonify(ordered_plugins)


@pluginsBP.route("/installed", methods=["GET"])
def installed():
    """Returns JSON of all installed plugins

    Fuses the discovery.yml data with meltano.yml data and sorts each type alphabetically by name
    """

    project = Project.find()
    config = ConfigService(project)
    discovery = PluginDiscoveryService(project)
    installed_plugins = {}

    # merge definitions
    for plugin in sorted(config.plugins(), key=lambda x: x.name):
        try:
            definition = discovery.find_plugin(plugin.type, plugin.name)
            merged_plugin_definition = {**definition.canonical(), **plugin.canonical()}
        except PluginNotFoundError:
            merged_plugin_definition = {**plugin.canonical()}

        merged_plugin_definition.pop("settings", None)
        merged_plugin_definition.pop("select", None)

        if not plugin.type in installed_plugins:
            installed_plugins[plugin.type] = []

        installed_plugins[plugin.type].append(merged_plugin_definition)

    return jsonify({**project.meltano.canonical(), "plugins": installed_plugins})


@pluginsBP.route("/add", methods=["POST"])
@readonly_killswitch
def add():
    payload = request.get_json()
    plugin_type = PluginType(payload["plugin_type"])
    plugin_name = payload["name"]

    project = Project.find()
    add_service = ProjectAddService(project)
    plugin = add_service.add(plugin_type, plugin_name)

    return jsonify(plugin.canonical())


@pluginsBP.route("/install/batch", methods=["POST"])
@readonly_killswitch
def install_batch():
    payload = request.get_json()
    plugin_type = PluginType(payload["plugin_type"])
    plugin_name = payload["name"]

    project = Project.find()

    # We use the DiscoveryService rather than the ConfigService because the
    # plugin may not actually be installed yet at this point.
    discovery = PluginDiscoveryService(project)
    plugin = discovery.find_plugin(plugin_type, plugin_name)

    add_service = ProjectAddService(project)
    related_plugins = add_service.add_related(plugin)

    install_service = PluginInstallService(project)
    install_service.install_plugins(related_plugins)

    return jsonify([plugin.canonical() for plugin in related_plugins])


@pluginsBP.route("/install", methods=["POST"])
@readonly_killswitch
def install():
    payload = request.get_json()
    plugin_type = PluginType(payload["plugin_type"])
    plugin_name = payload["name"]

    project = Project.find()

    config_service = ConfigService(project)
    plugin = config_service.find_plugin(plugin_name, plugin_type=plugin_type)

    install_service = PluginInstallService(project)
    install_service.install_plugin(plugin)

    return jsonify(plugin.canonical())
