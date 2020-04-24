#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    def _action(self, action="tower_api_rest", args={}):
        """Return a new ansible action"""

        task = self._task.copy()

        for key in args.keys():
            task.args[key] = args[key]

        action = self._shared_loader_obj.action_loader.get(
            action,
            task=task,
            connection=self._connection,
            play_context=self._play_context,
            loader=self._loader,
            templar=self._templar,
            shared_loader_obj=self._shared_loader_obj
        )

        return action

    def _gather(self):
        """Gather resource id"""

        args = self._task.args

        # Gather organization id

        organizations_base_path = "/organizations"
        action = self._action(
                    args=dict(path=organizations_base_path,
                              search=args["organization"]))
        organizations = action.run(task_vars=self._task_vars)["json"]

        organization_id = None
        for organization in organizations:
            if organization["name"] == args["organization"]:
                organization_id = organization["id"]
                break

        if organization_id is None:
            return dict(failed=True,
                        msg="Cannot find resource organization")

        # Gather resource id

        resource_type = args["type"]

        if resource_type == "inventory":
            resource_type = "inventories"
        else:
            resource_type = "{type}s".format(type=resource_type)

        resource_base_path = "/{type}/".format(type=resource_type)
        action = self._action(
                    args=dict(path=resource_base_path,
                              search=args["name"]))
        search_result = action.run(task_vars=self._task_vars)["json"]

        resource_id = None
        for resource in search_result:
            if resource["name"] == args["name"]:
                if "organization" in resource:
                    resource_organization_id = resource["organization"]
                elif "summary_fields" in resource \
                     and "inventory" in resource["summary_fields"]:
                    resource_inventory = \
                                        resource["summary_fields"]["inventory"]
                    resource_organization_id = resource_inventory[
                                                            "organization_id"]
                else:
                    return dict(failed=True,
                                msg="Cannot find resource organization")

                if resource_organization_id == organization_id:
                    resource_id = resource["id"]
                    break

        if resource_id is None:
            return dict(failed=True, msg="Cannot find resource")
        else:
            return dict(changed=False, id=resource_id)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        super(ActionModule, self).run(tmp, task_vars)
        self._task_vars = task_vars
        return self._gather()
