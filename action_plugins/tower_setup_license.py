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

    def _get_task_var(self, name, default=None):
        """Get templated task variable"""

        if name in self._task_vars:
            ret = self._templar.template(self._task_vars.get(name))
        else:
            ret = default

        return ret

    def _gather(self):
        """Gather necessary info to setup the license"""

        # Get current license

        self._license_path = "/config/"
        action = self._action(args=dict(path=self._license_path))
        config = action.run(task_vars=self._task_vars)["json"]

        self._current_license = config["license_info"]
        self._new_license = self._get_task_var("tower_license")

    def _setup(self):
        """Setup the license"""

        self._gather()

        for license in [self._current_license, self._new_license]:
            license.pop("grace_period_remaining", None)
            license.pop("time_remaining", None)

        changed = False
        if self._current_license != self._new_license:
            fields = license
            fields["eula_accepted"] = True
            action = self._action(
                        args=dict(path=self._license_path,
                                  method="POST",
                                  fields=fields))
            result = action.run(task_vars=self._task_vars)

            if result["status"] not in [200, 201, 202, 203, 204]:
                raise AnsibleError("Failed to setup license")

            changed = True

        return dict(changed=changed)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        self._task_vars = task_vars
        return self._setup()
