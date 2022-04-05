#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from time import sleep


class ActionModule(ActionBase):
    def _get_task_var(self, name, default=None):
        """Get templated task variable"""

        if name in self._task_vars:
            ret = self._templar.template(self._task_vars.get(name))
        else:
            ret = default

        return ret

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

    def _wait(self):
        """Wait for resources to become available"""

        self._args = self._task.args

        ids = self._args["ids"]
        retries = self._get_task_var("tower_get_status_retries")
        delay = self._get_task_var("tower_get_status_delay")

        for id in ids:
            ok = False
            attempts = 0
            while not ok and attempts < retries:
                resource_path = "/{type}s/{id}".format(type=self._args["type"],
                                                       id=id)
                action = self._action(args=dict(path=resource_path))
                result = action.run(task_vars=self._task_vars)

                if "json" in result:
                    resource = result["json"]

                    status = resource.get("status", "successful")
                else:
                    status = "failed"

                if status in ["successful", "never updated"]:
                    ok = True
                else:
                    sleep(delay)

                attempts += 1

            if attempts == retries:
                return dict(
                        changed=False,
                        failed=True,
                        msg="Maximum number of attemps exceded for {type} {id}"
                            .format(type=self._args["type"], id=id)
                )
        return dict(changed=False)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        super(ActionModule, self).run(tmp, task_vars)
        self._task_vars = task_vars

        try:
            result = self._wait()
        finally:
            self._remove_tmp_path(self._connection._shell.tmpdir)

        return result
