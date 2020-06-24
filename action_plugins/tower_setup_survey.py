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
        """Gather necessary info to setup the survey"""

        self._spec = self._task.args["spec"]

        # Gather target object survey spec

        self._target_survey_spec_path = \
            "/{target_type}s/{target_id}/survey_spec/".format(
                target_type=self._spec["target_type"],
                target_id=self._spec["target_id"])
        action = self._action(args=dict(path=self._target_survey_spec_path))
        self._survey_spec = action.run(task_vars=self._task_vars)["json"]

    def _setup(self):
        """Setup the survey"""

        self._gather()

        changed = False
        if self._survey_spec != self._spec["survey_spec"]:
            action = self._action(
                            args=dict(path=self._target_survey_spec_path,
                                      method="POST",
                                      fields=self._spec["survey_spec"]))
            result = action.run(task_vars=self._task_vars)

            if "status" not in result.keys() \
               or result["status"] not in [200, 201, 202, 203, 204]:
                raise AnsibleError("Failed to setup survey: {m}"
                                   .format(m=result.get("msg", "")))

            changed = True

        return dict(changed=changed)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        super(ActionModule, self).run(tmp, task_vars)
        self._task_vars = task_vars
        return self._setup()
