import os
import json

from meltano.core.utils import slugify

from .m5o_collection_parser import M5oCollectionParser, M5oCollectionParserTypes
from .m5o_file_parser import MeltanoAnalysisFileParser


class DashboardAlreadyExistsError(Exception):
    """Occurs when a dashboard already exists."""

    def __init__(self, dashboard):
        self.dashboard = dashboard


class DashboardDoesNotExistError(Exception):
    """Occurs when a dashboard does not exist."""

    def __init__(self, dashboard):
        self.dashboard = dashboard


class DashboardsService:
    VERSION = "1.0.0"

    def __init__(self, project):
        self.project = project

    def get_dashboards(self):
        dashboardsParser = M5oCollectionParser(
            self.project.analyze_dir("dashboards"), M5oCollectionParserTypes.Dashboard
        )

        return dashboardsParser.parse()

    def get_dashboard(self, dashboard_id):
        dashboards = self.get_dashboards()
        target_dashboard = [
            dashboard for dashboard in dashboards if dashboard["id"] == dashboard_id
        ]

        return target_dashboard[0]

    def get_dashboard_by_name(self, name):
        dashboards = self.get_dashboards()
        dashboard = next(filter(lambda r: r["name"] == name, dashboards), None)

        return dashboard

    def save_dashboard(self, data, keep_id=False):
        name = data["name"]
        slug = slugify(name)
        file_path = self.project.analyze_dir("dashboards", f"{slug}.dashboard.m5o")

        if os.path.exists(file_path):
            with file_path.open() as f:
                existing_dashboard = json.load(f)
            raise DashboardAlreadyExistsError(existing_dashboard)

        data = MeltanoAnalysisFileParser.fill_base_m5o_dict(
            file_path.relative_to(self.project.root), slug, data, keep_id=keep_id
        )
        data["version"] = DashboardsService.VERSION
        data["description"] = data["description"] or ""
        data["report_ids"] = []

        with file_path.open("w") as f:
            json.dump(data, f)

        return data

    def delete_dashboard(self, data):
        dashboard = self.get_dashboard(data["id"])
        slug = dashboard["slug"]
        file_path = self.project.analyze_dir("dashboards", f"{slug}.dashboard.m5o")
        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            raise DashboardDoesNotExistError(data)

        return data

    def update_dashboard(self, data):
        dashboard = self.get_dashboard(data["dashboard"]["id"])
        slug = dashboard["slug"]

        file_path = self.project.analyze_dir("dashboards", f"{slug}.dashboard.m5o")
        if not os.path.exists(file_path):
            raise DashboardDoesNotExistError(data)

        new_settings = data["new_settings"]
        new_name = new_settings["name"]
        new_slug = slugify(new_name)
        new_file_path = self.project.analyze_dir(
            "dashboards", f"{new_slug}.dashboard.m5o"
        )
        is_same_file = new_slug == slug
        if not is_same_file and os.path.exists(new_file_path):
            with new_file_path.open() as f:
                existing_dashboard = json.load(f)
            raise DashboardAlreadyExistsError(existing_dashboard)

        os.remove(file_path)

        dashboard["slug"] = new_slug
        dashboard["name"] = new_name
        dashboard["description"] = new_settings["description"]
        dashboard["path"] = str(new_file_path.relative_to(self.project.root))

        if set(new_settings["report_ids"]) == set(dashboard["report_ids"]):
            dashboard["report_ids"] = new_settings["report_ids"]

        with new_file_path.open("w") as f:
            json.dump(dashboard, f)

        return dashboard

    def add_report_to_dashboard(self, data):
        dashboard = self.get_dashboard(data["dashboard_id"])

        if data["report_id"] not in dashboard["report_ids"]:
            dashboard["report_ids"].append(data["report_id"])
            file_path = self.project.analyze_dir(
                "dashboards", f"{dashboard['slug']}.dashboard.m5o"
            )
            with file_path.open("w") as f:
                json.dump(dashboard, f)

        return dashboard

    def remove_report_from_dashboard(self, data):
        dashboard = self.get_dashboard(data["dashboard_id"])

        if data["report_id"] in dashboard["report_ids"]:
            dashboard["report_ids"].remove(data["report_id"])
            file_path = self.project.analyze_dir(
                "dashboards", f"{dashboard['slug']}.dashboard.m5o"
            )

            with file_path.open("w") as f:
                json.dump(dashboard, f)

        return dashboard
