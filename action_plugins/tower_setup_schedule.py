#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    _fields_names = ["rrule", "extra_data", "enabled"]

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
        """Gather necessary info to setup the schedule"""

        self._spec = self._task.args["spec"]

        # Gather schedules
        self._schedules_path = \
            "/{target_type}s/{target_id}/schedules/".format(
                target_type=self._spec["target_type"],
                target_id=self._spec["target_id"])
        action = self._action(args=dict(path=self._schedules_path))
        self._schedules = action.run(task_vars=self._task_vars)["json"]

    def _needs_update(self, schedule):
        """Determine if a schedule needs update."""

        update = False
        desired = self._spec
        for field_name in self._fields_names:
            schedule_value = schedule.get(field_name, None)
            desired_value = desired.get(field_name, None)
            if desired_value != schedule_value:
                update = True
                break

        return update

    def _setup(self):
        """Setup the schedule"""

        self._gather()

        current = None
        for schedule in self._schedules:
            if schedule["name"] == self._spec["name"]:
                current = schedule
                break

        state = self._spec.get("state", "present")
        needs_create = False
        needs_update = False
        needs_delete = False

        if state == "present" and current is None:
            needs_create = True
        elif state == "present" and self._needs_update(current):
            needs_update = True
        elif state == "absent" and current is not None:
            needs_delete = True

        if needs_create:
            path = self._schedules_path
            method = "POST"

        if needs_update or needs_delete:
            path = "/schedules/{id}/".format(id=current["id"])
            if needs_update:
                method = "PATCH"
            else:
                method = "DELETE"

        fields = dict()
        if needs_create or needs_update:
            fields = dict(name=self._spec["name"],
                          rrule=self._spec["rrule"],
                          extra_data=self._spec.get("extra_data", {}),
                          enabled=self._spec.get("enabled", True))

        changed = False
        if needs_create or needs_update or needs_delete:
            action = self._action(
                            args=dict(path=path,
                                      method=method,
                                      fields=fields))
            result = action.run(task_vars=self._task_vars)

            if result["status"] not in [200, 201, 202, 203, 204]:
                raise AnsibleError("Failed to setup schedule")

            changed = True

        return dict(changed=changed)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        super(ActionModule, self).run(tmp, task_vars)
        self._task_vars = task_vars
        return self._setup()
