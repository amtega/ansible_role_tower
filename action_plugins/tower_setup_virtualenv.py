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
        """Gather necessary info to setup the virtualenv"""

        self._spec = self._task.args["spec"]

        self._target_path = \
            "/{target_type}s/{target_id}/".format(
                target_type=self._spec["target_type"],
                target_id=self._spec["target_id"])
        action = self._action(args=dict(path=self._target_path))
        target = action.run(task_vars=self._task_vars)["json"]

        self._virtualenv = target.get("custom_virtualenv", None)

    def _setup(self):
        """Setup the virtualenv"""

        self._gather()

        changed = False
        if self._virtualenv != self._spec["virtualenv"]:
            fields = dict(custom_virtualenv=self._spec["virtualenv"])
            action = self._action(
                        args=dict(path=self._target_path,
                                  method="PATCH",
                                  fields=fields))
            result = action.run(task_vars=self._task_vars)

            if result["status"] not in [200, 201, 202, 203, 204]:
                raise AnsibleError("Failed to setup virtualenv")

            changed = True

        return dict(changed=changed)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        super(ActionModule, self).run(tmp, task_vars)
        self._task_vars = task_vars

        try:
            result =self._setup()
        finally:
            self._remove_tmp_path(self._connection._shell.tmpdir)

        return result
