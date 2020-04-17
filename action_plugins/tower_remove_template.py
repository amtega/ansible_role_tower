#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleError
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
        """Gather necessary info to remove the template"""

        args = self._task.args

        # Gather template id

        template_base_path = "/job_templates/"
        action = self._action(
                    args=dict(path=template_base_path,
                              search=args["name"]))
        search_result = action.run(task_vars=self._task_vars)["json"]

        template_id = None
        for template in search_result:
            if template["name"] == args["name"]:
                project = template["summary_fields"].get("project", None)

                if project is None or project["name"] == args["project"]:
                    template_id = template["id"]
                    break

        if template_id is not None:
            self._template_path = "{template_base_path}{id}/" \
                                 .format(template_base_path=template_base_path,
                                         id=template_id)
        else:
            self._template_path = None

    def _remove(self):
        """Remove the template"""

        self._gather()

        if self._template_path is None:
            return dict(changed=False)

        action = self._action(
                        args=dict(path=self._template_path,
                                  method="DELETE"))
        result = action.run(task_vars=self._task_vars)

        if result["status"] not in [200, 201, 202, 203, 204]:
            raise AnsibleError("Failed to remove template")

        return dict(changed=True)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        self._task_vars = task_vars
        return self._remove()
