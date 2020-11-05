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
        """Gather necessary info to setup the galaxy credential"""

        self._spec = self._task.args["spec"]

        # Gather target current galaxy credentials

        target_path = \
            "/{target_type}s/{target_id}/".format(
                target_type=self._spec["target_type"],
                target_id=self._spec["target_id"])

        self._galaxy_credentials_path = "{target_path}galaxy_credentials/" \
            .format(target_path=target_path)

        action = self._action(args=dict(path=self._galaxy_credentials_path))
        self._galaxy_credentials = []
        for result in action.run(task_vars=self._task_vars)["json"]:
            self._galaxy_credentials.append(result["id"])

        # Gather target galaxy credential id

        galaxy_credential_search_path = "/credentials/"
        action = self._action(
                    args=dict(path=galaxy_credential_search_path,
                              search=self._spec["name"]))
        search_result = action.run(task_vars=self._task_vars)["json"]

        galaxy_credential_id = None
        for galaxy_credential in search_result:
            if galaxy_credential["name"] == self._spec["name"]:
                galaxy_credential_id = galaxy_credential["id"]

        self._galaxy_credential_id = galaxy_credential_id

    def _setup(self):
        """Setup the galaxy credentials"""

        self._gather()

        current = None
        for galaxy_credential_id in self._galaxy_credentials:
            if galaxy_credential_id == self._galaxy_credential_id:
                current = galaxy_credential_id
                break

        state = self._spec.get("state", "present")
        needs_create = False
        needs_delete = False

        if state == "present" and current is None:
            needs_create = True
        elif state == "absent" and current is not None:
            needs_delete = True

        path = self._galaxy_credentials_path
        fields = dict(id=self._galaxy_credential_id)

        if needs_create:
            method = "POST"

        if needs_delete:
            method = "DELETE"

        changed = False
        if needs_create or needs_delete:
            action = self._action(
                            args=dict(path=path,
                                      method=method,
                                      fields=fields))
            result = action.run(task_vars=self._task_vars)

            if result["status"] not in [200, 201, 202, 203, 204]:
                raise AnsibleError("Failed to setup credential")

            changed = True

        return dict(changed=changed)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        super(ActionModule, self).run(tmp, task_vars)
        self._task_vars = task_vars
        return self._setup()
